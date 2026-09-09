from __future__ import annotations

import logging
import os
import threading
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Annotated

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request, Response, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from app.schemas import (
    AnalyticsSummary,
    AuthOut,
    CrawlRunCreate,
    CrawlRunOut,
    ExportMode,
    ExportFormat,
    InstitutionOut,
    JobDetailOut,
    JobListOut,
    JobStatusOut,
    JobStatusPayload,
    LoginPayload,
    NotificationOut,
    Profile,
    ProfileImportOut,
    ProfilePayload,
    RegisterPayload,
    ReportCreate,
    ReportOut,
    ResumeDraftCreate,
    ResumeDraftOut,
    ResumeDraftSummaryOut,
    ResumeDraftUpdate,
    SubscriptionCreate,
    SubscriptionOut,
    SubscriptionScanOut,
)
from app.services.analytics import analytics_summary, generate_report
from app.services.auth import hash_password, make_token, verify_password, verify_token
from app.services.crawler import execute_crawl_run, release_crawl_slot, try_acquire_crawl_slot
from app.services.database import DatabaseEngine, create_engine, init_db
from app.services.exporter import (
    build_export_filename,
    collect_unlinked_items,
    content_disposition_header,
    export_docx,
    export_pdf,
)
from app.services.profile_import import ProfileImportError, build_profile_contract, extract_profile_text
from app.services.repositories import (
    count_new_jobs_for_subscription,
    count_total_jobs_in_institutions,
    count_total_matching_jobs,
    count_unread_notifications,
    create_crawl_run,
    create_subscription,
    create_user,
    delete_job_status,
    delete_subscription,
    filter_active_institution_ids,
    get_crawl_run,
    get_institutions_by_ids,
    get_institutions_status,
    get_job,
    get_profile,
    get_resume_draft,
    get_subscription,
    get_user_by_id,
    get_user_by_username,
    has_matching_jobs_last_30d,
    list_crawl_runs,
    list_institutions,
    list_job_snapshots,
    list_jobs,
    list_notifications,
    list_subscriptions,
    mark_all_notifications_read,
    mark_notification_read,
    mark_subscription_read,
    list_resume_drafts_by_user,
    list_resume_drafts,
    save_profile,
    scan_subscriptions,
    update_resume_draft_sections,
    upsert_job_status,
    create_resume_draft as persist_resume_draft,
)
from app.services.profile_checks import check_profile_overlaps, count_field_references
from app.services.resume import (
    PROFILE_COLLECTIONS,
    analyze_job_match,
    attach_job_matches,
    flatten_profile_facts,
    generate_resume_draft,
    is_total_mismatch,
    match_profile_to_job,
)
from app.services.scheduler import DailyScheduler

logger = logging.getLogger(__name__)

DEFAULT_DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./data/app.db")


def create_app(database_url: str | None = None) -> FastAPI:
    from app.config import config

    engine = create_engine(database_url or DEFAULT_DATABASE_URL)
    init_db(engine)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        scheduler = DailyScheduler(
            engine,
            hour=config.subscription_scan_hour,
            minute=config.subscription_scan_minute,
            enabled=config.subscription_scan_enabled,
            auto_crawl=config.auto_crawl_enabled,
            crawl_delay=config.crawl_delay_seconds,
        )
        app.state.scheduler = scheduler
        scheduler.start()
        try:
            yield
        finally:
            scheduler.stop()

    app = FastAPI(title="医疗岗位情报与真实简历定制工具", version="0.1.0", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.state.engine = engine

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
        from app.services.seeds import BLOCKED_REASONS
        items = list_institutions(engine)
        for item in items:
            if item["enabled"]:
                item["blocked_reason"] = None
            else:
                item["blocked_reason"] = BLOCKED_REASONS.get(item["id"], "尚未适配该站点，暂未启用")
        return items

    @app.get("/api/institutions/health")
    def institutions_health(
        engine: Annotated[DatabaseEngine, Depends(get_engine)],
        user: Annotated[dict, Depends(get_current_user)],
    ) -> dict:
        """B1 数据健康视图：连续失败达到阈值的机构进入 review 状态，可一键重跑。"""
        from app.services.repositories import FAILURE_REVIEW_THRESHOLD

        items = list_institutions(engine)
        unhealthy = [
            {
                "id": item["id"],
                "name": item["name"],
                "crawl_strategy": item["crawl_strategy"],
                "enabled": item["enabled"],
                "last_status": item["last_status"],
                "last_error": item["last_error"],
                "consecutive_failures": item.get("consecutive_failures", 0),
            }
            for item in items
            if item.get("consecutive_failures", 0) >= FAILURE_REVIEW_THRESHOLD
        ]
        return {
            "threshold": FAILURE_REVIEW_THRESHOLD,
            "review_count": len(unhealthy),
            "institutions": unhealthy,
        }

    @app.post("/api/institutions/{institution_id}/recrawl", response_model=CrawlRunOut, status_code=201)
    def recrawl_institution(
        institution_id: int,
        engine: Annotated[DatabaseEngine, Depends(get_engine)],
        user: Annotated[dict, Depends(get_current_user)],
    ) -> dict:
        """B1 一键重跑：对单个机构立即触发一次抓取（与手动抓取同样的单飞约束）。"""
        from app.config import config
        from app.services.crawler import release_crawl_slot, try_acquire_crawl_slot

        institutions_to_crawl = get_institutions_by_ids(engine, [institution_id])
        if not institutions_to_crawl or not institutions_to_crawl[0]["enabled"]:
            raise HTTPException(status_code=400, detail="该机构不存在或尚未适配，无法抓取")
        if not try_acquire_crawl_slot():
            raise HTTPException(status_code=409, detail="已有抓取任务在进行中，请等待完成后再试")

        run_id = create_crawl_run(engine, [institution_id], trigger="manual")

        def _crawl_then_scan() -> None:
            try:
                execute_crawl_run(
                    engine, run_id, institutions_to_crawl, config.crawl_delay_seconds
                )
            finally:
                release_crawl_slot()
                scan_subscriptions(engine, datetime.now(timezone.utc))

        threading.Thread(target=_crawl_then_scan, daemon=True).start()
        return get_crawl_run(engine, run_id)

    @app.post("/api/crawl-runs", response_model=CrawlRunOut, status_code=201)
    def start_crawl(
        payload: CrawlRunCreate,
        engine: Annotated[DatabaseEngine, Depends(get_engine)],
        user: Annotated[dict, Depends(get_current_user)],
    ) -> dict:
        from app.config import config
        from app.services.seeds import BLOCKED_REASONS
        if payload.institution_ids is not None and not payload.institution_ids:
            raise HTTPException(status_code=422, detail="请至少选择一个机构再启动抓取")
        institutions_to_crawl = get_institutions_by_ids(engine, payload.institution_ids)
        if not institutions_to_crawl:
            raise HTTPException(status_code=404, detail="没有找到可抓取的机构")

        # Guard: filter out disabled (not adapted) institutions
        adapted_institutions = [inst for inst in institutions_to_crawl if inst["enabled"]]
        skipped_institutions = [inst for inst in institutions_to_crawl if not inst["enabled"]]

        if skipped_institutions and not adapted_institutions:
            raise HTTPException(status_code=400, detail="所选机构均尚未适配，无法抓取")

        if skipped_institutions:
            for inst in skipped_institutions:
                reason = BLOCKED_REASONS.get(inst["id"], "尚未适配该站点，暂未启用")
                logger.info(
                    "Skipping disabled institution id=%s name=%s reason=%s",
                    inst["id"], inst["name"], reason,
                )

        # 单飞：手动与自动抓取互斥，避免并发跑批互相干扰或重复入库。
        if not try_acquire_crawl_slot():
            raise HTTPException(status_code=409, detail="已有抓取任务在进行中，请等待完成后再启动")

        run_id = create_crawl_run(engine, [item["id"] for item in adapted_institutions], trigger="manual")

        def _crawl_then_scan() -> None:
            try:
                execute_crawl_run(
                    engine, run_id, adapted_institutions, config.crawl_delay_seconds
                )
            finally:
                release_crawl_slot()
                scan_subscriptions(engine, datetime.now(timezone.utc))

        thread = threading.Thread(target=_crawl_then_scan, daemon=True)
        thread.start()
        return get_crawl_run(engine, run_id)

    @app.get("/api/crawl-runs", response_model=list[CrawlRunOut])
    def crawl_runs(
        engine: Annotated[DatabaseEngine, Depends(get_engine)],
        limit: Annotated[int, Query(ge=1, le=100)] = 10,
    ) -> list[dict]:
        return list_crawl_runs(engine, limit)

    @app.get("/api/crawl-runs/{run_id}", response_model=CrawlRunOut)
    def crawl_run(run_id: int, engine: Annotated[DatabaseEngine, Depends(get_engine)]) -> dict:
        try:
            return get_crawl_run(engine, run_id)
        except KeyError:
            raise HTTPException(status_code=404, detail="抓取任务不存在") from None

    @app.get("/api/jobs", response_model=JobListOut)
    def jobs(
        engine: Annotated[DatabaseEngine, Depends(get_engine)],
        user: Annotated[dict | None, Depends(get_optional_user)] = None,
        keyword: str | None = None,
        institution_id: int | None = None,
        region: str | None = None,
        job_category: str | None = None,
        education: str | None = None,
        institution_type: str | None = None,
        tag: str | None = None,
        trust: Annotated[str, Query(pattern="^(real|placeholder|fixture|disabled|all)$")] = "all",
        fresh_days: Annotated[int | None, Query(ge=1, le=3650)] = None,
        limit: Annotated[int, Query(ge=1, le=500)] = 100,
        offset: Annotated[int, Query(ge=0)] = 0,
    ) -> dict:
        result = list_jobs(
            engine,
            {
                "keyword": keyword,
                "institution_id": institution_id,
                "region": region,
                "job_category": job_category,
                "education": education,
                "institution_type": institution_type,
                "tag": tag,
                "trust": None if trust == "all" else trust,
                "fresh_days": fresh_days,
                "limit": limit,
                "offset": offset,
            },
            user_id=user["id"] if user else None,
        )
        result["items"] = attach_job_matches(engine, result["items"], user["id"] if user else None)
        return result

    @app.get("/api/jobs/{job_id}", response_model=JobDetailOut)
    def job_detail(
        job_id: int,
        engine: Annotated[DatabaseEngine, Depends(get_engine)],
        user: Annotated[dict | None, Depends(get_optional_user)] = None,
    ) -> dict:
        try:
            job = get_job(engine, job_id, user_id=user["id"] if user else None)
        except KeyError:
            raise HTTPException(status_code=404, detail="岗位不存在") from None
        match_analysis = None
        if user:
            try:
                prof = get_profile(engine, user["id"])
                if not prof.is_empty:
                    match_analysis = analyze_job_match(prof, job)
            except KeyError:
                pass
        return {
            **job,
            "raw_snapshot": {
                "source_url": job["source_url"],
                "source_text_hash": job["source_text_hash"],
                "fetched_at": job["fetched_at"],
                "raw_text": job["raw_text"],
            },
            "history": list_job_snapshots(engine, job_id),
            "match_analysis": match_analysis,
        }

    @app.put("/api/jobs/{job_id}/status", response_model=JobStatusOut)
    def put_job_status(
        job_id: int,
        payload: JobStatusPayload,
        engine: Annotated[DatabaseEngine, Depends(get_engine)],
        user: Annotated[dict, Depends(get_current_user)],
    ) -> dict:
        try:
            return upsert_job_status(
                engine,
                user["id"],
                job_id,
                status=payload.status,
                note=payload.note,
                deadline=payload.deadline.isoformat() if payload.deadline else None,
            )
        except KeyError:
            raise HTTPException(status_code=404, detail="岗位不存在") from None

    @app.delete("/api/jobs/{job_id}/status", status_code=204)
    def clear_job_status(
        job_id: int,
        engine: Annotated[DatabaseEngine, Depends(get_engine)],
        user: Annotated[dict, Depends(get_current_user)],
    ) -> Response:
        try:
            get_job(engine, job_id)
        except KeyError:
            raise HTTPException(status_code=404, detail="岗位不存在") from None
        delete_job_status(engine, user["id"], job_id)
        return Response(status_code=204)

    @app.get("/api/analytics/summary", response_model=AnalyticsSummary)
    def summary(
        engine: Annotated[DatabaseEngine, Depends(get_engine)],
        region: str | None = None,
        job_category: str | None = None,
        institution_type: str | None = None,
        trust: Annotated[str, Query(pattern="^(real|placeholder|fixture|disabled|all)$")] = "all",
    ) -> dict:
        return analytics_summary(
            engine,
            {
                "region": region,
                "job_category": job_category,
                "institution_type": institution_type,
                "trust": None if trust == "all" else trust,
            },
        )

    @app.post("/api/reports", response_model=ReportOut, status_code=201)
    def reports(
        payload: ReportCreate,
        engine: Annotated[DatabaseEngine, Depends(get_engine)],
        user: Annotated[dict, Depends(get_current_user)],
    ) -> dict:
        return generate_report(engine, payload.title, payload.filters)

    @app.get("/api/profile")
    def profile(
        engine: Annotated[DatabaseEngine, Depends(get_engine)],
        user: Annotated[dict, Depends(get_current_user)],
    ) -> dict:
        profile_data = get_profile(engine, user["id"])
        return profile_data.model_dump()

    @app.put("/api/profile")
    def put_profile(
        payload: ProfilePayload,
        engine: Annotated[DatabaseEngine, Depends(get_engine)],
        user: Annotated[dict, Depends(get_current_user)],
    ) -> dict:
        profile = payload.to_profile()
        return save_profile(engine, user["id"], profile)

    @app.get("/api/profile/field-references")
    def field_references(
        field_id: str,
        engine: Annotated[DatabaseEngine, Depends(get_engine)],
        user: Annotated[dict, Depends(get_current_user)],
    ) -> dict:
        drafts = list_resume_drafts_by_user(engine, user["id"])
        return count_field_references(drafts, field_id)

    @app.post("/api/profile/check-overlap")
    def check_overlap(
        payload: ProfilePayload,
        user: Annotated[dict, Depends(get_current_user)],
    ) -> dict:
        return check_profile_overlaps(payload.to_profile().model_dump())

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

    @app.get("/api/resume-drafts", response_model=list[ResumeDraftSummaryOut])
    def list_user_resume_drafts(
        engine: Annotated[DatabaseEngine, Depends(get_engine)],
        user: Annotated[dict, Depends(get_current_user)],
        job_id: Annotated[int | None, Query()] = None,
    ) -> list[dict]:
        drafts = list_resume_drafts(engine, user["id"], job_id)
        return [
            {
                "id": d["id"],
                "job_id": d["job_id"],
                "title": d["title"],
                "status": _compute_draft_status(d),
                "created_at": d["created_at"],
                "updated_at": d["updated_at"],
            }
            for d in drafts
        ]

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
        profile = get_profile(engine, user["id"])
        if profile.is_empty:
            raise HTTPException(status_code=400, detail="请先填写或导入履历内容")
        evidence, gaps = match_profile_to_job(profile, job)
        # 422: hard degree floors the profile fails (blocking gaps) block even
        # when other requirements match; a job whose evaluable requirements are
        # ALL unmet also blocks as a total mismatch.
        if is_total_mismatch(evidence, gaps) or any(bool(gap.get("blocking")) for gap in gaps):
            raise HTTPException(
                status_code=422,
                detail="您的档案与该岗位的要求差距较大，建议关注其他更匹配的职位",
            )
        draft = generate_resume_draft(profile, job)
        return _with_computed_status(
            persist_resume_draft(
                engine,
                user["id"],
                payload.job_id,
                draft["title"],
                draft["sections"],
                draft["evidence"],
                draft["gaps"],
            )
        )

    @app.get("/api/resume-drafts/{draft_id}", response_model=ResumeDraftOut)
    def resume_draft(
        draft_id: int,
        engine: Annotated[DatabaseEngine, Depends(get_engine)],
        user: Annotated[dict, Depends(get_current_user)],
    ) -> dict:
        try:
            return _with_computed_status(get_resume_draft(engine, user["id"], draft_id))
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
            return _with_computed_status(
                update_resume_draft_sections(engine, user["id"], draft_id, payload.sections)
            )
        except KeyError:
            raise HTTPException(status_code=404, detail="简历草稿不存在") from None

    @app.post("/api/resume-drafts/{draft_id}/export")
    def export_resume(
        draft_id: int,
        engine: Annotated[DatabaseEngine, Depends(get_engine)],
        user: Annotated[dict, Depends(get_current_user)],
        format: Annotated[ExportFormat, Query()] = "docx",
        mode: Annotated[ExportMode, Query()] = "application",
        override: Annotated[bool, Query()] = False,
    ) -> Response:
        try:
            draft = get_resume_draft(engine, user["id"], draft_id)
        except KeyError:
            raise HTTPException(status_code=404, detail="简历草稿不存在") from None

        export_draft = _draft_for_export(draft)

        # 422: empty content — enforced regardless of override, and before the
        # review guard: an empty draft never reaches "reviewed", so the review
        # guard would 409 with the contradictory "还有 0 项待确认".
        export_items = [item for section in export_draft["sections"] for item in section.get("items", [])]
        if not export_items:
            raise HTTPException(status_code=422, detail="导出内容为空，请至少保留一项内容后再导出")

        # 409: unreviewed draft — blocked unless the caller passes override.
        if _compute_draft_status(draft) != "reviewed" and not override:
            items = [item for section in draft.get("sections", []) for item in section.get("items", [])]
            pending = sum(1 for item in items if item.get("decision") not in ("adopt", "edit", "remove"))
            raise HTTPException(status_code=409, detail=f"草稿尚未审阅完成，还有 {pending} 项待确认")

        # 409: application 模式下存在未绑定档案证据的内容 —— 需显式确认后才允许导出。
        # 诊断模式不受此限制：无证据条目在附录中被明确标注，而非静默进入投递版。
        # 证据引用须真实存在于当前档案（伪造/已失效的 profile_field_id 不算有证据）。
        if mode == "application" and not override:
            profile = get_profile(engine, user["id"])
            valid_field_ids = {
                fact["profile_field_id"] for fact in flatten_profile_facts(profile)
            }
            unlinked = collect_unlinked_items(export_draft, valid_field_ids)
            if unlinked:
                raise HTTPException(
                    status_code=409,
                    detail=(
                        f"导出内容中有 {len(unlinked)} 项未关联档案证据（可能为手动添加），"
                        "请逐项确认内容真实无误后再导出"
                    ),
                )

        include_appendix = mode == "diagnostic"
        ext = "docx" if format == "docx" else "pdf"
        if format == "docx":
            try:
                content = export_docx(export_draft, include_appendix=include_appendix)
            except Exception:
                logger.exception("export_docx failed (draft_id=%s, format=%s)", draft_id, format)
                raise HTTPException(status_code=500, detail="文件生成失败，请稍后重试") from None
            media_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        else:
            try:
                content = export_pdf(export_draft, include_appendix=include_appendix)
            except Exception:
                logger.exception("export_pdf failed (draft_id=%s, format=%s)", draft_id, format)
                raise HTTPException(status_code=500, detail="文件生成失败，请稍后重试") from None
            media_type = "application/pdf"

        filename = build_export_filename(export_draft, ext, mode)
        return Response(
            content=content,
            media_type=media_type,
            headers={"Content-Disposition": content_disposition_header(filename)},
        )

    # ── Subscriptions (PRD 4.1) ────────────────────────────────────────

    def _enrich_subscription(sub: dict, engine: DatabaseEngine) -> dict:
        """Attach computed fields: new_count, institution_statuses, is_empty_30d, last_pushed_at."""
        institution_ids = sub["institution_ids"]
        institution_statuses = get_institutions_status(engine, institution_ids)
        active_ids = [s["id"] for s in institution_statuses if not s["is_maintenance"]]
        new_count = count_new_jobs_for_subscription(
            engine, sub["keyword"], active_ids, sub["last_checked_at"]
        )
        is_empty_30d = not has_matching_jobs_last_30d(
            engine, sub["keyword"], active_ids
        )
        return {
            **sub,
            "new_count": new_count,
            "institution_statuses": institution_statuses,
            "is_empty_30d": is_empty_30d,
            "last_pushed_at": sub.get("last_pushed_at"),
        }

    BROAD_KEYWORD_RATIO = 0.5  # >50% match ratio = broad keyword

    def _maybe_broad_keyword_warning(
        engine: DatabaseEngine, keyword: str, institution_ids: list[int]
    ) -> str | None:
        """Return a warning string if the keyword is too broad, else None."""
        total = count_total_jobs_in_institutions(engine, institution_ids)
        if total == 0:
            return None
        matched = count_total_matching_jobs(engine, keyword, institution_ids)
        ratio = matched / total
        if ratio > BROAD_KEYWORD_RATIO:
            return f"关键词过宽，命中 {matched} 条职位（占比 {int(ratio * 100)}%），建议缩小范围"
        return None

    @app.post("/api/subscriptions", response_model=SubscriptionOut, status_code=201)
    def create_subscription_endpoint(
        payload: SubscriptionCreate,
        engine: Annotated[DatabaseEngine, Depends(get_engine)],
        user: Annotated[dict, Depends(get_current_user)],
    ) -> dict:
        # Resolve institution_ids: default to all enabled institutions
        if payload.institution_ids is not None:
            institution_ids = payload.institution_ids
        else:
            enabled = list_institutions(engine)
            institution_ids = [inst["id"] for inst in enabled if inst["enabled"]]
            # Cap at 12
            institution_ids = institution_ids[:12]
        if not institution_ids:
            raise HTTPException(status_code=422, detail="请至少选择 1 家机构")

        # Validate all institution IDs exist
        institutions = get_institutions_by_ids(engine, institution_ids)
        if len(institutions) != len(institution_ids):
            raise HTTPException(status_code=400, detail="部分机构不存在")

        sub = create_subscription(
            engine,
            user["id"],
            payload.name.strip(),
            payload.keyword.strip(),
            institution_ids,
        )
        enriched = _enrich_subscription(sub, engine)
        warning = _maybe_broad_keyword_warning(engine, payload.keyword.strip(), institution_ids)
        if warning:
            enriched["warning"] = warning
        return enriched

    @app.get("/api/subscriptions", response_model=list[SubscriptionOut])
    def list_subscriptions_endpoint(
        engine: Annotated[DatabaseEngine, Depends(get_engine)],
        user: Annotated[dict, Depends(get_current_user)],
    ) -> list[dict]:
        subs = list_subscriptions(engine, user["id"])
        return [_enrich_subscription(sub, engine) for sub in subs]

    @app.delete("/api/subscriptions/{subscription_id}", status_code=204)
    def delete_subscription_endpoint(
        subscription_id: int,
        engine: Annotated[DatabaseEngine, Depends(get_engine)],
        user: Annotated[dict, Depends(get_current_user)],
    ) -> Response:
        try:
            delete_subscription(engine, user["id"], subscription_id)
        except KeyError:
            raise HTTPException(status_code=404, detail="订阅不存在") from None
        return Response(status_code=204)

    @app.post("/api/subscriptions/{subscription_id}/mark-read", response_model=SubscriptionOut)
    def mark_subscription_read_endpoint(
        subscription_id: int,
        engine: Annotated[DatabaseEngine, Depends(get_engine)],
        user: Annotated[dict, Depends(get_current_user)],
    ) -> dict:
        try:
            sub = mark_subscription_read(engine, user["id"], subscription_id)
        except KeyError:
            raise HTTPException(status_code=404, detail="订阅不存在") from None
        return _enrich_subscription(sub, engine)

    @app.post("/api/subscriptions/scan", response_model=SubscriptionScanOut)
    def scan_subscriptions_endpoint(
        engine: Annotated[DatabaseEngine, Depends(get_engine)],
        user: Annotated[dict, Depends(get_current_user)],
    ) -> dict:
        return scan_subscriptions(engine, datetime.now(timezone.utc), user_id=user["id"])

    # ── Notifications (B2 订阅触达：站内通知) ──────────────────────────

    @app.get("/api/notifications", response_model=list[NotificationOut])
    def notifications_endpoint(
        engine: Annotated[DatabaseEngine, Depends(get_engine)],
        user: Annotated[dict, Depends(get_current_user)],
        limit: Annotated[int, Query(ge=1, le=100)] = 20,
    ) -> list[dict]:
        return list_notifications(engine, user["id"], limit)

    @app.get("/api/notifications/unread-count")
    def unread_count_endpoint(
        engine: Annotated[DatabaseEngine, Depends(get_engine)],
        user: Annotated[dict, Depends(get_current_user)],
    ) -> dict:
        return {"count": count_unread_notifications(engine, user["id"])}

    @app.post("/api/notifications/{notification_id}/read", response_model=NotificationOut)
    def mark_notification_read_endpoint(
        notification_id: int,
        engine: Annotated[DatabaseEngine, Depends(get_engine)],
        user: Annotated[dict, Depends(get_current_user)],
    ) -> dict:
        try:
            return mark_notification_read(engine, user["id"], notification_id)
        except KeyError:
            raise HTTPException(status_code=404, detail="通知不存在") from None

    @app.post("/api/notifications/read-all")
    def mark_all_notifications_read_endpoint(
        engine: Annotated[DatabaseEngine, Depends(get_engine)],
        user: Annotated[dict, Depends(get_current_user)],
    ) -> dict:
        return {"marked": mark_all_notifications_read(engine, user["id"])}

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


def get_optional_user(
    engine: Annotated[DatabaseEngine, Depends(get_engine)],
    authorization: Annotated[str | None, Header()] = None,
) -> dict | None:
    if not authorization:
        return None
    token = None
    if authorization.lower().startswith("bearer "):
        token = authorization[7:].strip()
    if not token:
        raise HTTPException(status_code=401, detail="请先登录")
    payload = verify_token(token)
    if payload is None:
        raise HTTPException(status_code=401, detail="请先登录")
    user = get_user_by_id(engine, int(payload["uid"]))
    if user is None:
        raise HTTPException(status_code=401, detail="账号不存在或已失效")
    return user


def _compute_draft_status(draft: dict) -> str:
    """Return 'reviewed' when every section item carries a valid decision."""
    items = [item for section in draft.get("sections", []) for item in section.get("items", [])]
    if not items:
        return "draft"
    return "reviewed" if all(item.get("decision") in ("adopt", "edit", "remove") for item in items) else "draft"


def _with_computed_status(draft: dict) -> dict:
    """Inject computed review status into a draft dict for the response model."""
    return {**draft, "status": _compute_draft_status(draft)}


def _draft_for_export(draft: dict) -> dict:
    """Strip removed items and the gaps paragraph from a draft for export.

    The gaps paragraph is always removed: in application mode it is simply
    omitted, and in diagnostic mode it is replaced by the match-analysis
    appendix (added by the exporter when *include_appendix* is True).
    """
    sections = [
        {
            **section,
            "items": [item for item in section.get("items", []) if item.get("decision") != "remove"],
        }
        for section in draft.get("sections", [])
        if section.get("id") != "gaps" and section.get("title") != "投递前需补充确认"
    ]
    return {**draft, "sections": sections}


app = create_app()
