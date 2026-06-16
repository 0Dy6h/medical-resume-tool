from __future__ import annotations

import os
import threading
from typing import Annotated

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request, Response, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from app.schemas import (
    AnalyticsSummary,
    AuthOut,
    CrawlRunCreate,
    CrawlRunOut,
    ExportFormat,
    InstitutionOut,
    JobDetailOut,
    JobListOut,
    LoginPayload,
    ProfileImportOut,
    ProfilePayload,
    RegisterPayload,
    ReportCreate,
    ReportOut,
    ResumeDraftCreate,
    ResumeDraftOut,
    ResumeDraftUpdate,
)
from app.services.analytics import analytics_summary, generate_report
from app.services.auth import hash_password, make_token, verify_password, verify_token
from app.services.crawler import execute_crawl_run
from app.services.database import DatabaseEngine, create_engine, init_db
from app.services.exporter import export_docx, export_pdf
from app.services.profile_import import ProfileImportError, build_profile_contract, extract_profile_text
from app.services.repositories import (
    create_crawl_run,
    create_user,
    get_crawl_run,
    get_institutions_by_ids,
    get_job,
    get_profile,
    get_resume_draft,
    get_user_by_id,
    get_user_by_username,
    list_institutions,
    list_jobs,
    save_profile,
    update_resume_draft_sections,
    create_resume_draft as persist_resume_draft,
)
from app.services.resume import PROFILE_COLLECTIONS, generate_resume_draft


DEFAULT_DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./data/app.db")


def create_app(database_url: str | None = None) -> FastAPI:
    app = FastAPI(title="医疗岗位情报与真实简历定制工具", version="0.1.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    engine = create_engine(database_url or DEFAULT_DATABASE_URL)
    app.state.engine = engine
    init_db(engine)

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.post("/api/auth/register", response_model=AuthOut, status_code=201)
    def register(payload: RegisterPayload, engine: Annotated[DatabaseEngine, Depends(get_engine)]) -> dict:
        password_hash, password_salt = hash_password(payload.password)
        try:
            user = create_user(engine, payload.username, password_hash, password_salt)
        except ValueError:
            raise HTTPException(status_code=400, detail="用户名已被占用") from None
        return {"token": make_token(user["id"], user["username"]), "username": user["username"]}

    @app.post("/api/auth/login", response_model=AuthOut)
    def login(payload: LoginPayload, engine: Annotated[DatabaseEngine, Depends(get_engine)]) -> dict:
        user = get_user_by_username(engine, payload.username)
        if user is None or not verify_password(payload.password, user["password_hash"], user["password_salt"]):
            raise HTTPException(status_code=401, detail="用户名或密码错误")
        return {"token": make_token(user["id"], user["username"]), "username": user["username"]}

    @app.get("/api/auth/me")
    def me(user: Annotated[dict, Depends(get_current_user)]) -> dict:
        return {"username": user["username"]}

    @app.get("/api/institutions", response_model=list[InstitutionOut])
    def institutions(engine: Annotated[DatabaseEngine, Depends(get_engine)]) -> list[dict]:
        return list_institutions(engine)

    @app.post("/api/crawl-runs", response_model=CrawlRunOut, status_code=201)
    def start_crawl(payload: CrawlRunCreate, engine: Annotated[DatabaseEngine, Depends(get_engine)]) -> dict:
        from app.config import config
        institutions_to_crawl = get_institutions_by_ids(engine, payload.institution_ids)
        if not institutions_to_crawl:
            raise HTTPException(status_code=404, detail="没有找到可抓取的机构")
        run_id = create_crawl_run(engine, [item["id"] for item in institutions_to_crawl])
        thread = threading.Thread(
            target=execute_crawl_run,
            args=(engine, run_id, institutions_to_crawl, config.crawl_delay_seconds),
            daemon=True,
        )
        thread.start()
        return get_crawl_run(engine, run_id)

    @app.get("/api/crawl-runs/{run_id}", response_model=CrawlRunOut)
    def crawl_run(run_id: int, engine: Annotated[DatabaseEngine, Depends(get_engine)]) -> dict:
        try:
            return get_crawl_run(engine, run_id)
        except KeyError:
            raise HTTPException(status_code=404, detail="抓取任务不存在") from None

    @app.get("/api/jobs", response_model=JobListOut)
    def jobs(
        engine: Annotated[DatabaseEngine, Depends(get_engine)],
        keyword: str | None = None,
        institution_id: int | None = None,
        region: str | None = None,
        job_category: str | None = None,
        education: str | None = None,
        institution_type: str | None = None,
        tag: str | None = None,
        limit: Annotated[int, Query(ge=1, le=500)] = 100,
        offset: Annotated[int, Query(ge=0)] = 0,
    ) -> dict:
        return list_jobs(
            engine,
            {
                "keyword": keyword,
                "institution_id": institution_id,
                "region": region,
                "job_category": job_category,
                "education": education,
                "institution_type": institution_type,
                "tag": tag,
                "limit": limit,
                "offset": offset,
            },
        )

    @app.get("/api/jobs/{job_id}", response_model=JobDetailOut)
    def job_detail(job_id: int, engine: Annotated[DatabaseEngine, Depends(get_engine)]) -> dict:
        try:
            job = get_job(engine, job_id)
        except KeyError:
            raise HTTPException(status_code=404, detail="岗位不存在") from None
        return {
            **job,
            "raw_snapshot": {
                "source_url": job["source_url"],
                "source_text_hash": job["source_text_hash"],
                "fetched_at": job["fetched_at"],
                "raw_text": job["raw_text"],
            },
        }

    @app.get("/api/analytics/summary", response_model=AnalyticsSummary)
    def summary(
        engine: Annotated[DatabaseEngine, Depends(get_engine)],
        region: str | None = None,
        job_category: str | None = None,
        institution_type: str | None = None,
    ) -> dict:
        return analytics_summary(
            engine,
            {
                "region": region,
                "job_category": job_category,
                "institution_type": institution_type,
            },
        )

    @app.post("/api/reports", response_model=ReportOut, status_code=201)
    def reports(payload: ReportCreate, engine: Annotated[DatabaseEngine, Depends(get_engine)]) -> dict:
        return generate_report(engine, payload.title, payload.filters)

    @app.get("/api/profile")
    def profile(
        engine: Annotated[DatabaseEngine, Depends(get_engine)],
        user: Annotated[dict, Depends(get_current_user)],
    ) -> dict:
        return get_profile(engine, user["id"])

    @app.put("/api/profile")
    def put_profile(
        payload: ProfilePayload,
        engine: Annotated[DatabaseEngine, Depends(get_engine)],
        user: Annotated[dict, Depends(get_current_user)],
    ) -> dict:
        return save_profile(engine, user["id"], payload.model_dump())

    @app.post("/api/profile/import", response_model=ProfileImportOut)
    async def import_profile(
        user: Annotated[dict, Depends(get_current_user)],
        file: UploadFile,
    ) -> dict:
        content = await file.read()
        try:
            extraction = extract_profile_text(file.filename or "", content)
        except ProfileImportError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from None
        contract = build_profile_contract(extraction.lines, extraction.warnings)
        return contract.to_dict()

    @app.post("/api/resume-drafts", response_model=ResumeDraftOut, status_code=201)
    def resume_drafts(
        payload: ResumeDraftCreate,
        engine: Annotated[DatabaseEngine, Depends(get_engine)],
        user: Annotated[dict, Depends(get_current_user)],
    ) -> dict:
        try:
            job = get_job(engine, payload.job_id)
        except KeyError:
            raise HTTPException(status_code=404, detail="岗位不存在") from None
        profile_data = get_profile(engine, user["id"])
        if not any(profile_data.get(collection) for collection in PROFILE_COLLECTIONS):
            raise HTTPException(status_code=400, detail="请先填写或导入履历内容")
        draft = generate_resume_draft(profile_data, job)
        return persist_resume_draft(
            engine,
            user["id"],
            payload.job_id,
            draft["title"],
            draft["sections"],
            draft["evidence"],
            draft["gaps"],
        )

    @app.get("/api/resume-drafts/{draft_id}", response_model=ResumeDraftOut)
    def resume_draft(
        draft_id: int,
        engine: Annotated[DatabaseEngine, Depends(get_engine)],
        user: Annotated[dict, Depends(get_current_user)],
    ) -> dict:
        try:
            return get_resume_draft(engine, user["id"], draft_id)
        except KeyError:
            raise HTTPException(status_code=404, detail="简历草稿不存在") from None

    @app.put("/api/resume-drafts/{draft_id}", response_model=ResumeDraftOut)
    def put_resume_draft(
        draft_id: int,
        payload: ResumeDraftUpdate,
        engine: Annotated[DatabaseEngine, Depends(get_engine)],
        user: Annotated[dict, Depends(get_current_user)],
    ) -> dict:
        try:
            return update_resume_draft_sections(engine, user["id"], draft_id, payload.sections)
        except KeyError:
            raise HTTPException(status_code=404, detail="简历草稿不存在") from None

    @app.post("/api/resume-drafts/{draft_id}/export")
    def export_resume(
        draft_id: int,
        engine: Annotated[DatabaseEngine, Depends(get_engine)],
        user: Annotated[dict, Depends(get_current_user)],
        format: Annotated[ExportFormat, Query()] = "docx",
    ) -> Response:
        try:
            draft = get_resume_draft(engine, user["id"], draft_id)
        except KeyError:
            raise HTTPException(status_code=404, detail="简历草稿不存在") from None
        if format == "docx":
            return Response(
                content=export_docx(draft),
                media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                headers={"Content-Disposition": f'attachment; filename="resume-{draft_id}.docx"'},
            )
        return Response(
            content=export_pdf(draft),
            media_type="application/pdf",
            headers={"Content-Disposition": f'attachment; filename="resume-{draft_id}.pdf"'},
        )

    return app


def get_engine(request: Request) -> DatabaseEngine:
    return request.app.state.engine


def get_current_user(
    engine: Annotated[DatabaseEngine, Depends(get_engine)],
    authorization: Annotated[str | None, Header()] = None,
) -> dict:
    token = None
    if authorization and authorization.lower().startswith("bearer "):
        token = authorization[7:].strip()
    payload = verify_token(token)
    if payload is None:
        raise HTTPException(status_code=401, detail="请先登录")
    user = get_user_by_id(engine, int(payload["uid"]))
    if user is None:
        raise HTTPException(status_code=401, detail="账号不存在或已失效")
    return user


app = create_app()
