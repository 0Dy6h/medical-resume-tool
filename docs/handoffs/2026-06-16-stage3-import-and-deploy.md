# Stage 3 Profile Import + Deploy Handoff — 2026-06-16 (上午)

## Goal

Review the codex-implemented Stage 3 profile-import fact extractor (heading-independent), commit + push, build a fresh deploy package, deploy to the Tencent Cloud CVM, and leave a clean continuation note.

## Current state

- **Profile import no longer requires section headings.** The `/api/profile/import` endpoint switched from the heading-only `parse_profile_from_lines` to a new fact-extraction pipeline (`build_profile_contract`):
  - `profile_import/blocks.py` — `lines -> DocumentBlock`; reuses `merge_bullets_with_parent` / `normalize_heading` / `normalize_time_range`; headings only add a `section_hint` boost, they no longer gate recognition.
  - `profile_import/extractors.py` — per-block recognition for education / experiences / projects / certificates / languages / skills / publications / awards / teaching, reusing the legacy `_build_*` builders; skills are also pulled from experience/project highlights.
  - `profile_import/scoring.py` — confidence from evidence signals.
  - `profile_import/pipeline.py` — routes facts: `>=0.75` auto-structured, `0.45-0.75` -> `review_items` (待确认), lower -> `unassigned_blocks` (未归类); `import_meta.extractor_name = "fact-extractor-v1"`.
- The multi-format extraction layer (`extract_profile_text`: docx/pdf/txt/md + image OCR) was **not** touched.
- Frontend `ProfilePage.tsx` import preview gained a 「待确认」 section (review_items, default unchecked, merge into the right collection on confirm) and a 「未归类原文」 collapsible section.
- `legacy_to_contract` / `parse_profile_from_lines` are no longer called by the endpoint but remain (still exported, still covered by `test_profile_import.py`). `extraction.py` got only a comment marking it as a reserved future structured-extraction path.
- **Deployed live** to http://110.42.136.106/ (still HTTP plaintext, no HTTPS — unchanged).

## Commits created (all pushed to origin/main)

1. `9c5e3bf feat: heading-independent profile import (Stage 3 fact extractor)`
2. `923ccec deploy: add 2026-06-16 deployment docs for Stage 3 import`
3. `d1b5474 fix: export ~/.local/bin in deploy.sh for non-interactive ssh`

## Verification

- `pytest -q` — **86 passed** (was 83; +3). `test_extractors.py` asserts the unsectioned acceptance sample field-by-field (school/degree/dates, 3 highlights, skills set, review/unassigned empty, exact import_meta).
- Frontend `pnpm typecheck` / `pnpm test` (5) / `pnpm build` — all pass.
- Server after deploy: `/health` = `{"status":"ok"}`, `/api/profile` = `401`, `dist` rebuilt (12:29), `nginx -t` ok + reload, nginx `root` = `/opt/medical-resume-tool/frontend/dist`.

## Deployment details (server facts — save time next round)

- **uv** is at `/home/ubuntu/.local/bin/uv` and is **NOT on PATH in a non-interactive ssh session** (`ssh host 'bash deploy.sh'`). This broke the original deploy.sh at `uv sync`. Fixed in `d1b5474` (deploy.sh now prepends `$HOME/.local/bin` to PATH). The systemd service uses uv's absolute path, so the running service was unaffected.
- **systemd `medical-resume.service`**: `User=ubuntu`, `WorkingDirectory=/opt/medical-resume-tool/backend`, `ExecStart=/home/ubuntu/.local/bin/uv run --project /opt/medical-resume-tool/backend uvicorn app.main:app --host 127.0.0.1 --port 8000`, `Environment` already has `AUTH_SECRET` + `DATABASE_URL` (sqlite app.db). Already the multi-user version — **DB preserved, no reset needed.**
- Stage 3 added **no new Python deps**, and `.venv` already existed → backend went live with just `sudo systemctl restart medical-resume` (no `uv sync` strictly required).
- `pnpm` / `node` / `corepack` are in `/usr/bin` (nodesource node_22). `sudo` is passwordless for ubuntu.
- **Tesseract OCR** installed this session: `tesseract-ocr tesseract-ocr-chi-sim` (+ eng). Image/scanned-PDF import now works server-side (previously would degrade to a warning).
- **Backup / rollback point**: `/opt/backups/medical-resume-tool-2026-06-16-114827`.
- Deploy package `medical-resume-tool-deploy-2026-06-16.zip` is a build artifact, reproducible with `git archive --format=zip -o <name>.zip HEAD`. `.gitattributes` has `*.zip export-ignore` so packages never bundle historical zips. The local copy was removed after deploy (work-tree cleanup).

## Known boundaries (Stage 3 v1, rule-based — expect tuning on real resumes)

- The acceptance sample is an ideal input; real resumes will expose edges.
- A block containing `项目/课题/队列/平台/基金` is classified as a project and excluded from experiences → a real job that mentions a project may be misrouted.
- Skill vocab is broad (`\bR\b`, `统计`, `随访`, `伦理`) → possible false positives.
- The GCP certificate name is special-cased to `GCP证书` (`extractors.py` `_certificate_fact`).
- Education with no parseable date range scores 0.65 → lands in 待确认 rather than auto-import (intentional conservative default).
- Detail: `backend/app/services/profile_import/HANDOFF.md` (Stage 3 section).

## Still open

- **Browser end-to-end acceptance is pending** (user task): log in at http://110.42.136.106/ → 我的履历 → import a real **headingless** resume → confirm structured items appear, uncertain ones go to 待确认, residue to 未归类原文.
- The older `medical-resume-tool-deploy-2026-06-12.zip` is still tracked in git (398KB). Superseded by the 06-16 package and the new "don't commit zips" policy; optional `git rm` cleanup later.
- Still HTTP plaintext, no HTTPS.

## Recommended next step

Drive the Stage 3 extractor against real resumes, not the ideal sample:

1. Import several real headingless resumes (PDF/DOCX) via the live site or a local run.
2. Record where it misroutes (experience↔project), over-extracts skills, or drops content into 未归类.
3. Tune `extractors.py` (entity/skill vocab, project-vs-experience precedence) and `scoring.py` thresholds against those cases; add each as a fixture in `tests/test_extractors.py`.
4. Only after real-resume accuracy is acceptable, consider the deferred items (consolidate `extraction.py`'s structured path, or remove the now-dead `legacy_to_contract`).
