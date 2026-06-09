# Session Handoff: 2026-06-09 - Real Adapter & Crawl Strategy Discovery

## What was done

### 1. Real site reconnaissance

Tested accessibility and structure of ~10 institutions from the seed list. Key findings:

- **Hospital recruitment is NOT static HTML on the main domain.** Most large hospitals use third-party recruitment SaaS (Beisen/北森 `zhiye.com` platform) with SPA rendering.
- The Beisen portal pages are empty HTML shells — `httpx` + `BeautifulSoup` cannot extract job data.
- However, the *actual announcement content* is often hosted as **static HTML on the hospital's main site** (e.g. `www.nfyy.com/job/gkzp/a_121553.html`). The SPA portal just links to it.
- This means the real pipeline is: Playwright discovers the announcement URL → httpx fetches the static page → rule-based parser extracts structured jobs.

### 2. First real adapter: 南方医院 (nfyy)

- **Adapter**: `backend/app/services/adapters/nfyy.py` — parses numbered-section announcements.
- **Fixture**: `backend/fixtures/nfyy/a_121553.html` — real HTML from the hospital site, saved for offline testing.
- **Tests**: `backend/tests/test_nfyy_adapter.py` — 7 tests covering extraction count, titles, education, categories, parser metadata, confidence, and tags.
- **Integration**: `crawler.py` now dispatches by `crawl_strategy` field. Strategy `"nfyy"` routes to the dedicated adapter.
- **Seed updated**: Institution #21 now enabled with real `listing_url` and `crawl_strategy: "nfyy"`.

### 3. Architecture change: adapter dispatch

`crawl_institution()` in `crawler.py` now has a 3-tier dispatch:
1. `fixture://` prefix → fixture path (unchanged)
2. `crawl_strategy` matches a registered adapter → dedicated adapter
3. fallback → generic crawler (unchanged)

New adapters are added by: creating `adapters/{name}.py`, adding a case in `_resolve_adapter()`, and updating the institution's `crawl_strategy` in seeds.

## Key discovery: the real bottleneck

The original handoff assumed "add static adapters for 24 institutions." The reality is:

| What we thought | What's actually true |
|---|---|
| Recruitment pages are static HTML | They're SPA portals (Beisen/zhiye.com) |
| Each page lists jobs in a parseable table | Content is often a single long announcement PDF/HTML |
| Need per-site HTML parsers | Need announcement → structured jobs extraction |

The true pipeline for most institutions is:
1. **Discover** the announcement URL (may need Playwright once per institution)
2. **Fetch** the announcement page (usually static HTML, httpx is enough)
3. **Extract** structured jobs from the announcement text (rule-based or LLM)

## Verification

- Backend: 12 tests passing (5 original + 7 new adapter tests)
- Frontend: 2 tests passing, typecheck clean, build clean
- No dependencies added to production; Playwright is dev-only for reconnaissance

## Still open

- Playwright remains a dev dependency for future institution reconnaissance
- Only one real adapter (nfyy) exists; the pattern is proven and replicable
- For institutions with less structured announcements, an LLM extraction fallback is the logical next step (`.env.example` already reserves the config)
- 23 other disabled institutions still need reconnaissance + adapters
- No git repo initialized yet

## Recommended next steps

1. **Add 2-3 more adapters** using the same pattern (reconnaissance → fixture → parser → tests) to validate the approach scales across institution types (hospital/university/research institute).
2. **Add LLM extraction fallback** for announcements that don't follow a numbered-section format.
3. **Initialize git** and commit the baseline + this first real adapter as the foundation.
