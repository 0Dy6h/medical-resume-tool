from __future__ import annotations

import asyncio
import os
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, Query, Request, Response
from fastapi.middleware.cors import CORSMiddleware

from app.schemas import (
    AnalyticsSummary,
    CrawlRunCreate,
    CrawlRunOut,
    ExportFormat,
    InstitutionOut,
    JobDetailOut,
    JobListOut,
    ProfilePayload,
    ReportCreate,
    ReportOut,
    ResumeDraftCreate,
    ResumeDraftOut,
    ResumeDraftUpdate,
)
from app.services.analytics import analytics_summary, generate_report
from app.services.crawler import crawl_institution
from app.services.database import DatabaseEngine, create_engine, init_db
from app.services.exporter import export_docx, export_pdf
from app.services.repositories import (
    complete_crawl_run,
    create_crawl_run,
    get_crawl_run,
    get_institutions_by_ids,
    get_job,
    get_profile,
    get_resume_draft,
    list_institutions,
    list_jobs,
    mark_institution,
    save_profile,
    update_resume_draft_sections,
    upsert_job,
    create_resume_draft as persist_resume_draft,
)
from app.services.resume import generate_resume_draft


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

    @app.get("/api/institutions", response_model=list[InstitutionOut])
    def institutions(engine: Annotated[DatabaseEngine, Depends(get_engine)]) -> list[dict]:
        return list_institutions(engine)

    @app.post("/api/crawl-runs", response_model=CrawlRunOut, status_code=201)
    async def start_crawl(payload: CrawlRunCreate, engine: Annotated[DatabaseEngine, Depends(get_engine)]) -> dict:
        from app.config import config
        institutions_to_crawl = get_institutions_by_ids(engine, payload.institution_ids)
        if not institutions_to_crawl:
            raise HTTPException(status_code=404, detail="没有找到可抓取的机构")
        run_id = create_crawl_run(engine, [item["id"] for item in institutions_to_crawl])
        success_count = 0
        failure_count = 0
        errors = []
        delay = config.crawl_delay_seconds
        for index, institution in enumerate(institutions_to_crawl):
            try:
                parsed_jobs = await crawl_institution(institution)
                for parsed in parsed_jobs:
                    upsert_job(engine, institution, parsed)
                    success_count += 1
                mark_institution(engine, institution["id"], "success")
            except Exception as exc:  # pragma: no cover - exact network failures vary.
                failure_count += 1
                message = str(exc)
                errors.append({"institution_id": institution["id"], "institution": institution["name"], "error": message})
                mark_institution(engine, institution["id"], "failed", message)
            if delay and index < len(institutions_to_crawl) - 1:
                await asyncio.sleep(delay)
        return complete_crawl_run(
            engine,
            run_id,
            success_count=success_count,
            failure_count=failure_count,
            errors=errors,
        )

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
    def profile(engine: Annotated[DatabaseEngine, Depends(get_engine)]) -> dict:
        return get_profile(engine)

    @app.put("/api/profile")
    def put_profile(payload: ProfilePayload, engine: Annotated[DatabaseEngine, Depends(get_engine)]) -> dict:
        return save_profile(engine, payload.model_dump())

    @app.post("/api/resume-drafts", response_model=ResumeDraftOut, status_code=201)
    def resume_drafts(payload: ResumeDraftCreate, engine: Annotated[DatabaseEngine, Depends(get_engine)]) -> dict:
        try:
            job = get_job(engine, payload.job_id)
        except KeyError:
            raise HTTPException(status_code=404, detail="岗位不存在") from None
        profile_data = get_profile(engine)
        if not profile_data.get("basic"):
            raise HTTPException(status_code=400, detail="请先填写结构化履历")
        draft = generate_resume_draft(profile_data, job)
        return persist_resume_draft(
            engine,
            payload.job_id,
            draft["title"],
            draft["sections"],
            draft["evidence"],
            draft["gaps"],
        )

    @app.get("/api/resume-drafts/{draft_id}", response_model=ResumeDraftOut)
    def resume_draft(draft_id: int, engine: Annotated[DatabaseEngine, Depends(get_engine)]) -> dict:
        try:
            return get_resume_draft(engine, draft_id)
        except KeyError:
            raise HTTPException(status_code=404, detail="简历草稿不存在") from None

    @app.put("/api/resume-drafts/{draft_id}", response_model=ResumeDraftOut)
    def put_resume_draft(draft_id: int, payload: ResumeDraftUpdate, engine: Annotated[DatabaseEngine, Depends(get_engine)]) -> dict:
        try:
            return update_resume_draft_sections(engine, draft_id, payload.sections)
        except KeyError:
            raise HTTPException(status_code=404, detail="简历草稿不存在") from None

    @app.post("/api/resume-drafts/{draft_id}/export")
    def export_resume(
        draft_id: int,
        engine: Annotated[DatabaseEngine, Depends(get_engine)],
        format: Annotated[ExportFormat, Query()] = "docx",
    ) -> Response:
        try:
            draft = get_resume_draft(engine, draft_id)
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


app = create_app()
