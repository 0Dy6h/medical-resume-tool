# Adapter Batch 1 Handoff — 2026-06-09

## Goal

Add real website adapters for the 24 disabled generic seed institutions.

## Completed

### New adapters (5 institutions enabled)

| ID | Institution | Adapter | Pattern |
|---|---|---|---|
| 7 | 浙大二院 | `z2hospital.py` | listing page → per-article detail scraping |
| 11 | 北京大学医学部 | `bjmu.py` | rsc.bjmu.edu.cn listing → article parsing |
| 19 | 中国疾病预防控制中心 | `chinacdc.py` | department notices (inline) + annual notices (metadata) |
| 27 | 哈尔滨医科大学 | `hrbmu.py` | listing → table-based position extraction from 拟聘公示 |
| 28 | 南京医科大学 | `njmu.py` | rsc.njmu.edu.cn listing → announcement condition extraction |

### Infrastructure changes

- `crawler.py` `_resolve_adapter()` now dispatches to all 6 adapters (nfyy + 5 new)
- `seeds.py` updated: 5 seeds enabled with correct `listing_url` and `crawl_strategy`; remaining disabled seeds annotated with reason (SPA, login-required, timeout, etc.)
- HTML fixtures saved for offline testing: `fixtures/{z2hospital,chinacdc,njmu,hrbmu,bjmu}/`
- 12 new tests in `tests/test_adapters.py` (all pass)

### Reconnaissance results for remaining 19 disabled seeds

**Could become Tier 2 adapters (need more work):**
- ID 12 上交医 (`join.shsmu.edu.cn`) — static page, needs structure analysis
- ID 16 上药所 (`simm.cas.cn/web/rcdw/rczp/`) — listing reachable but sparse
- ID 17 生物物理所 — same pattern as 16
- ID 29 中医科学院 — redirects to cacms.ac.cn, has `build.html#rczp`
- ID 30 公卫中心 — recruit channel mixed with procurement

**Blocked (SPA/login/unreachable):**
- ID 8 同济 — SPA (`hr.tjhonline.com.cn/zp.html`)
- ID 13 浙大医学院 — ConnectError
- ID 20 国家卫健委科研所 — ConnectError
- ID 23 宣武医院 — requires login
- ID 26 温州眼视光 — ConnectError

**No recruit page found on homepage:**
- ID 9 南京鼓楼, 10 肿瘤医院, 14 湘雅, 22 齐鲁, 24 天津总医院, 25 重庆附一

**Key pattern insight:** Most institutions use either (a) static announcement pages or (b) SPA-based third-party recruitment systems (Beisen, 北森). Positions are frequently in PDF/xlsx attachments rather than inline HTML.

## Verification

- `pytest backend/tests/ -q` → 24 passed
- All fixture-based tests run offline (no network)

## Recommended next steps

1. For sites with PDF/xlsx attachments (njmu, hrbmu main notice): add `openpyxl`/`pdfplumber` to extract position tables
2. For SPA sites (同济): evaluate headless browser approach (Playwright) — be aware this adds complexity
3. For unreachable sites: set up periodic reachability checks and auto-enable when they come back
4. Wire up error handling in crawl runs: if a live adapter fails, store the error and mark the run as partial success
