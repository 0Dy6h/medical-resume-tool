---
name: resume-tool-dev
description: Bootstrap, verify, and safely extend the 简历撰写工具 (Chinese medical job-intelligence + truthful resume-tailoring tool). Use when working on this repo — environment setup, running tests, or changing the requirement matcher / resume generation. Covers the non-obvious env traps and the truthfulness invariants that must not be broken.
---

# Working on the 简历撰写工具 repo

Local Chinese **medical job-intelligence + truthful resume-tailoring** tool.
FastAPI + SQLite backend (`backend/app`), React/Vite frontend (`frontend/src`).
Read `AGENTS.md` and `docs/architecture.md` first; this skill adds the parts that
are easy to get wrong.

## 1. Bootstrap the environment (do this before anything)

The repo may carry a **stale `.venv` / `node_modules` from another machine**.
Symptoms and fixes:

- `uv run` fails with `os error 5` on `backend/.venv/lib64` → `rm -rf backend/.venv`; `uv` recreates it.
- `pnpm` fails with `ERR_PNPM_ABORTED_REMOVE_MODULES_DIR_NO_TTY` → `cd frontend && CI=true pnpm install`.
- `uv` is at `~/.local/bin`, not on PATH → `export PATH="$PATH:/c/Users/12035/.local/bin"`.
- Ad-hoc `python -c` with Chinese output is garbled in Git Bash → prefix `PYTHONIOENCODING=utf-8`.
- `.claude/settings.json` is generated permission noise — gitignored; never commit it.

## 2. Verify (match effort to the change)

```bash
# backend
uv run --project backend pytest -q                 # expect: all green (184+ as of 2026-07-26)
# frontend
cd frontend && pnpm test && pnpm typecheck && pnpm build
```

For a real cross-stack check, start both services and hit `/health`, `/api/jobs`,
`/api/analytics/summary`, and `http://127.0.0.1:5173`.

## 3. Invariants that must not break

- **Truthfulness (non-negotiable).** The resume generator only reorders/joins the
  user's own profile field values — it never invents wording. Every evidence row
  is anchored to a `profile_field_id`. When matching cannot confidently support a
  requirement, emit an honest **gap** (`未在你的履历中找到对应证据`), not a weak
  match. A degree the applicant fails is a **blocking** gap, not a generated resume.
- **Matching quality is measured, not asserted.** Changes under
  `backend/app/services/matching/` must keep `backend/tests/test_matching_eval.py`
  green: top-1 source accuracy, zero wrong-source attributions, zero false
  positives on negatives, over a tuning profile and a held-out profile.
- **Regenerate the IDF table** after editing `matching/segment.py`:
  `cd backend && python -m scripts.build_idf` (writes `app/data/jd_idf.json`; it is
  built offline from fixtures, never from live user data).
- **Do not change `classifier.extract_requirements`** casually — it writes the
  persisted `jobs.requirements` column and the job filters; replacing it needs a
  data migration. The new matcher lives in `matching/` and is additive.

## 4. Matching pipeline (where to make changes)

`match_profile_to_job` (`backend/app/services/resume.py`) →
`matching.segment_requirements` (clause extraction) →
per requirement: `matching.gates.evaluate_degree_gate` (ordinal 学历 check) else
`matching.scorer.best_matches` (CJK bigram + IDF + concept lexicon).
`matching/scorer.py` is deliberately conservative near the noise floor; if you
lower a threshold, re-check the eval's negative cases for new false positives.

## 5. Current priorities

See `docs/handoffs/2026-07-26-end-of-day.md`. Next offline-verifiable win:
import-side routing in `backend/app/services/profile_import/` — extract `basics`
and stop one work block auto-importing as experience + a fabricated project +
publication. The LLM lane (`jd_structurer.py`) is blocked on no API key in this
environment; it is an enhancement, not a dependency.
