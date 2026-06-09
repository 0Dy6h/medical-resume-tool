# Architecture

## Summary

The MVP is a local web application with a FastAPI backend, SQLite persistence, and a React/Vite frontend. The backend owns crawling, parsing, classification, analytics, profile storage, resume draft generation, report generation, and exports. The frontend is a dense workbench for individual job seekers.

## Data Flow

1. Institution seeds are initialized from `backend/app/services/seeds.py`.
2. `POST /api/crawl-runs` selects enabled or specified institutions.
3. Fixture sources return deterministic sample jobs; generic sources attempt public page parsing.
4. Parsed jobs are normalized, tagged, hashed, and upserted into SQLite.
5. Analytics reads the current job table and computes category, education, region, capability, and institution-focus aggregates.
6. The profile form saves structured user facts as JSON.
7. Resume generation matches job requirements against profile facts and stores only sourced evidence.
8. Exports render the stored draft as DOCX or PDF.

## Main Tables

- `institutions` - seed source metadata and last crawl status.
- `crawl_runs` - crawl execution summary and error list.
- `jobs` - normalized job records, raw snapshots, tags, parser metadata, confidence.
- `profiles` - single local structured profile.
- `resume_drafts` - generated sections, evidence, and gaps.
- `reports` - generated Markdown/HTML market reports.

## API Surface

- `GET /api/institutions`
- `POST /api/crawl-runs`
- `GET /api/crawl-runs/{id}`
- `GET /api/jobs`
- `GET /api/jobs/{id}`
- `GET /api/analytics/summary`
- `POST /api/reports`
- `GET /api/profile`
- `PUT /api/profile`
- `POST /api/resume-drafts`
- `GET /api/resume-drafts/{id}`
- `PUT /api/resume-drafts/{id}`
- `POST /api/resume-drafts/{id}/export?format=docx|pdf`

## Resume Truth Constraint

The resume generator flattens the structured profile into facts with `profile_field_id`, matches requirements by rule-based keyword overlap, and writes every evidence item with a `profile_field_id`. Gaps use the wording `未在你的履历中找到对应证据` and do not suggest fabrication.

## Current Source Strategy

The first six seeds use fixture data so the MVP can run without external network fragility. The other 24 seeds keep public official URLs and are disabled until source-specific adapters and data-quality checks are added.

