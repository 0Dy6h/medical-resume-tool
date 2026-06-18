# Skills And Workflow Map - 2026-06-18

## Purpose

This note lists the most practical skills and tool patterns for the next main developer. It is intentionally selective: use fewer skills consistently rather than many skills casually.

## Default Execution Flow

For non-trivial future work:

1. `project-grill` - clarify scope, terminology, and product boundary before coding.
2. `vertical-slice-planning` - split the idea into independently verifiable slices.
3. `writing-plans` - create an implementation-ready plan with exact files, tests, commands, and acceptance criteria.
4. `test-driven-development` - implement one behavior at a time through RED -> GREEN -> REFACTOR.
5. `systematic-debugging` - use when any test, build, crawl, import, or UI behavior fails unexpectedly.
6. `requesting-code-review` - run before committing multi-file code changes.
7. `session-handoff` - write a repo-local handoff if work stops before the next slice is complete.

## Product And Planning Skills

### `project-grill`

Use when:

- The user says "先别写代码".
- A feature boundary is ambiguous.
- The change could alter product positioning, evidence rules, data boundaries, or user workflow.

Expected output:

- Current understanding.
- Confirmed facts from docs/code.
- One high-leverage open question at a time.
- Scope boundaries and durable decisions.

### `vertical-slice-planning`

Use when:

- Turning product suggestions into execution slices.
- Avoiding backend-only or frontend-only milestones.
- Creating issue-ready drafts without publishing issues.

Expected output:

- Thin, demoable slices.
- AFK/HITL classification.
- Explicit blockers.
- Verification for each slice.

### `writing-plans`

Use when:

- A slice is ready for implementation.
- A main developer or subagent needs exact steps.

Expected output:

- Saved plan under `docs/plans/YYYY-MM-DD-<topic>.md`.
- Exact files.
- Focused tests.
- Commands and expected results.
- Bite-sized tasks.

## Implementation And Quality Skills

### `test-driven-development`

Use for:

- New backend routes/services.
- New frontend API helper behavior.
- Profile import changes.
- Resume matching changes.
- Crawler/parser changes.

Project verification commands:

```powershell
uv run --project backend pytest -q
cd frontend
pnpm test
pnpm typecheck
pnpm build
```

### `systematic-debugging`

Use when:

- A fixture or real adapter changes behavior.
- Import/OCR behaves unexpectedly.
- Tests fail.
- A frontend page shows stale or incorrect state.
- A deployment smoke fails.

Rule:

- Build a reliable feedback loop before changing code.

### `requesting-code-review`

Use before committing:

- Multi-file feature slices.
- Auth/profile/resume/crawler changes.
- Any code touching user-uploaded files, exports, crawling, or persistence.

Skip or lighten for:

- Documentation-only changes.
- Small non-behavioral config alignment.

### `github-code-review`

Use when:

- Reviewing an existing PR.
- Preparing a GitHub review comment.
- Comparing branch changes against `main`.

This repo currently has no observed GitHub PR workflow in local files, so default to local diff review unless the user gives a PR or remote workflow.

## Code Navigation Skills

### `codegraph`

Current status:

- CodeGraph is already indexed for this repo.
- Latest check: 236 indexed files, 3223 nodes, 6593 edges.

Use:

- Start with `mcp_codegraph_codegraph_context` for architecture or feature-context questions.
- Run `codegraph sync` after large edits if symbol queries seem stale.

### `codebase-map`

Use when:

- A future session needs to understand a broad area before changing it.
- Examples: profile import pipeline, crawler adapter dispatch, resume evidence generation.

## Frontend Skills

### `frontend-design`

Use when:

- Reworking first-run flow, job detail, resume evidence UI, analytics dashboards, or any visible interface.

Project-specific guidance:

- This is a workbench, not a marketing page.
- Keep density high but readable.
- Prefer workflow clarity over decorative UI.
- Preserve the existing restrained, professional medical/productivity tone unless deliberately redesigning the design system.

### Useful frontend verification

After frontend changes:

```powershell
cd frontend
pnpm test
pnpm typecheck
pnpm build
```

For visual/interaction changes, also run the app and inspect with Playwright or browser automation.

## Research And External Reference Skills

### `openai-docs`

Use only if adding or changing OpenAI API/product integration. This project currently does not require it for the existing rule-based pipeline.

### `github-*` skills

Use only once a real GitHub workflow is requested:

- `github-auth`
- `github-pr-workflow`
- `github-code-review`
- `github-issues`

Do not add GitHub side effects unless the user asks.

## Recommended Future Skill Combos

### First-run onboarding slice

Use:

- `project-grill`
- `vertical-slice-planning`
- `writing-plans`
- `frontend-design`
- `test-driven-development`

### Resume evidence UX slice

Use:

- `project-grill`
- `codegraph`
- `writing-plans`
- `test-driven-development`
- `frontend-design`

### New official-site adapter slice

Use:

- `systematic-debugging` for real-site behavior.
- `test-driven-development` with saved fixtures.
- `requesting-code-review` before commit.

Guardrails:

- No login-based scraping.
- No anti-bot bypass.
- Preserve source traceability.
- Keep PDFs evidence-only unless fixtures and tests are included.

### Profile import enhancement slice

Use:

- `systematic-debugging` if handling a failed import sample.
- `test-driven-development` with fixture resumes.
- `writing-plans` if changing extraction contract.

Guardrails:

- Do not discard unassigned source text.
- Preserve review items, confidence, and warnings.
- Keep OCR optional and gracefully degraded.

## Skills To Avoid For Now

- Broad autonomous project execution: too heavy for the current focused repo.
- Large multi-agent execution: only use after a written plan exists.
- OpenAI integration skills: not needed unless the product deliberately adds LLM features.
- Web platform scraping helpers that encourage login/proxy/anti-bot behavior: conflicts with project boundaries.
