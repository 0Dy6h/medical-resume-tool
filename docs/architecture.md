# Architecture

## Summary

The MVP is a local web application with a FastAPI backend, SQLite persistence, and a React/Vite frontend. The backend owns crawling, parsing, classification, analytics, username/password authentication, user-scoped profile storage, private job workflow state, resume draft generation, report generation, and exports. The frontend is a dense workbench for individual job seekers.

## Data Flow

1. Institution seeds are initialized from `backend/app/services/seeds.py`.
2. `POST /api/crawl-runs` selects enabled or specified institutions.
3. Fixture sources return deterministic sample jobs; real adapters fetch official announcement pages.
4. Attachment-aware adapters discover public `.xlsx`, `.xls`, and `.pdf` links. `.xlsx/.xls` tables can produce row-level jobs; PDF links are currently recorded as evidence only.
5. Parsed jobs are normalized, tagged, hashed, and upserted into SQLite.
6. Analytics reads the current job table and computes category, education, region, capability, institution-focus, and parser-quality aggregates.
7. Login/register issues signed bearer tokens for private profile, import, draft, export, and job-status endpoints.
8. The profile form saves structured user facts as JSON under the signed-in user.
9. Optional per-user job status stores private triage state, notes, and deadlines without changing public job records.
10. Resume generation segments job requirements, matches them against profile facts (semantic bigram scoring plus an arithmetic degree gate), and stores only sourced evidence.
11. Exports render the stored draft as DOCX or PDF. Application exports omit internal gap diagnostics by default; diagnostic exports are explicit.

## Main Tables

- `institutions` - seed source metadata and last crawl status.
- `crawl_runs` - crawl execution summary and error list.
- `jobs` - normalized job records, raw snapshots, tags, parser metadata, confidence.
- `users` - local username/password accounts.
- `profiles` - one structured profile per user.
- `job_statuses` - private per-user job triage state, note, and deadline.
- `resume_drafts` - user-scoped generated sections, evidence, and gaps.
- `reports` - generated Markdown/HTML market reports.

## API Surface

- `POST /api/auth/register`
- `POST /api/auth/login`
- `GET /api/auth/me`
- `GET /api/institutions`
- `POST /api/crawl-runs`
- `GET /api/crawl-runs/{id}`
- `GET /api/jobs`
- `GET /api/jobs/{id}`
- `PUT /api/jobs/{job_id}/status`
- `DELETE /api/jobs/{job_id}/status`
- `GET /api/jobs/{job_id}/structure`
- `GET /api/analytics/summary`
- `POST /api/reports`
- `GET /api/profile`
- `PUT /api/profile`
- `POST /api/profile/import`
- `POST /api/resume-drafts`
- `GET /api/resume-drafts/{id}`
- `PUT /api/resume-drafts/{id}`
- `POST /api/resume-drafts/{id}/export?format=docx|pdf&mode=application|diagnostic`

## Resume Truth Constraint

The resume generator flattens the structured profile into facts with `profile_field_id`, and writes every evidence item with a `profile_field_id`, readable `source_label`, `matched_terms`, and `evidence_strength`. No wording is invented — a resume line reorders and joins the user's own field values. Gaps use the wording `未在你的履历中找到对应证据` and do not suggest fabrication.

## Requirement Matching

`backend/app/services/matching/` replaces the earlier whitespace-token keyword overlap, which could not tokenize Chinese (no word boundaries) and matched only on a small hardcoded keyword list.

- `segment.py` locates the requirement block by heading, splits enumerated clauses out of the whitespace-collapsed announcement text, and drops application procedure and employer self-description. Returns a warning (rather than a fabricated requirement) when no requirements are found, e.g. when they live in an attachment.
- `tokenize.py` produces CJK character bigrams so differently-worded terms sharing a sub-term still overlap; Latin acronyms (`SPSS`, `GCP`) are kept whole.
- `scorer.py` ranks facts per requirement by IDF-weighted overlap (weights committed in `app/data/jd_idf.json`, built offline by `scripts/build_idf.py` — never recomputed from live user data) plus a small concept lexicon. It is deliberately conservative: a weak concept-only bridge stays a gap rather than asserting a low-confidence match.
- `gates.py` evaluates degree/学历 requirements by ordinal comparison (大专 < 本科 < 硕士 < 博士), which similarity scoring cannot do. A requirement the applicant categorically fails (e.g. a 博士-only post for a 硕士 holder) becomes a **blocking** gap instead of a generated resume.

Matching quality is guarded by a labeled eval set (`backend/tests/test_matching_eval.py`) with hard bars on top-1 source accuracy, zero wrong-source attributions, and zero false positives on negative cases, over one tuning profile and one held-out profile.

## Current Source Strategy

The first six seeds use fixture data so the MVP can run without external network fragility. Six official-site adapters are enabled for real sources: `nfyy`, `z2hospital`, `bjmu`, `chinacdc`, `hrbmu`, and `njmu`. `bjmu` and `chinacdc` parse xlsx attachments into row-level jobs when the public attachment is available; `njmu` and `hrbmu` record discovered attachments without parsing PDFs. Remaining disabled seeds keep public official URLs and blocked/generic strategy notes until source-specific adapters and data-quality checks are added.

## Attachment Evidence

Attachment-derived jobs keep the same top-level traceability fields as other jobs. Additional attachment facts are stored in `extraction_evidence`, including `announcement_url`, `attachment_url`, `attachment_name`, `sheet_name`, `row_index`, and `headers`. Announcement-level records may include `extraction_evidence.attachments` entries with `status` values such as `discovered`, `parsed`, or `failed`.

## Parser Quality Review

`/api/analytics/summary` includes `parser_quality`, grouped by `parser_name`. Each row reports total jobs, low-confidence jobs, attachment-sourced jobs, failed attachment events, average confidence, and a `review_status` of `stable`, `watch`, or `review`. The frontend analysis page renders this as a compact quality table so adapter regressions are visible during normal workbench use.
