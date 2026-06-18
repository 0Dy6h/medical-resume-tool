# Product Research Synthesis - 2026-06-18

## Goal

This note prepares the next product and implementation phase for the Chinese medical job intelligence and truthful resume tailoring MVP. It records comparable products/projects, reusable standards, and the product lessons most relevant to this repository.

## Local Baseline

The current product is a local FastAPI/SQLite + React/Vite workbench with:

- Official-public-source job crawling and parsing.
- Deterministic fixture data for stable demos.
- Six enabled official-site adapters: `nfyy`, `z2hospital`, `bjmu`, `chinacdc`, `hrbmu`, `njmu`.
- Job traceability through `source_url`, `source_text_hash`, `fetched_at`, `parser_name`, confidence, raw text, and attachment evidence.
- Structured profile storage and import from DOCX/PDF/TXT/Markdown/images.
- Truth-constrained resume draft generation with `sections`, `evidence`, and `gaps`.
- DOCX/PDF export.

The strongest product position is not "AI resume generation". It is:

> Trusted medical job intelligence plus evidence-backed resume tailoring.

## Comparable Open-Source Projects

### Reactive Resume

- Source: <https://github.com/amruthpillai/reactive-resume>
- What it is: A full open-source resume builder focused on templates, rich editing, sharing, and export.
- Relevant lessons:
  - Resume editing must feel like a document product, not only a form.
  - Export fidelity and template control are core user trust points.
  - It is useful as a benchmark for polished resume editing UX, not for medical job intelligence or truthful-evidence matching.
- Avoid copying:
  - Broad template marketplace scope before the evidence workflow is strong.
  - Generic resume-builder positioning.

### OpenResume

- Source: <https://github.com/xitanggg/open-resume>
- What it is: An open-source resume builder and resume parser oriented toward privacy and browser-side usability.
- Relevant lessons:
  - Import/parsing UX needs a preview-and-correction loop.
  - A structured resume schema improves downstream rendering and export.
  - Privacy/local-first messaging resonates with resume users.
- Avoid copying:
  - Treating parsing success as enough. This project also needs source confidence, review items, and domain-specific medical facts.

### Resume Matcher

- Source: <https://github.com/srbhr/Resume-Matcher>
- What it is: A resume-to-job-description matching project focused on ATS-style keyword analysis and job targeting.
- Relevant lessons:
  - Users understand "match", "missing keyword", and "improvement suggestion" faster than raw model scores.
  - Matching should be explainable by requirement, not only a single percentage.
  - The next version should show "requirement -> profile evidence -> resume bullet" as the central UX.
- Avoid copying:
  - Keyword stuffing incentives. This project should remain evidence-first and truth-constrained.

### JobSpy

- Source: <https://github.com/speedyapply/JobSpy>
- What it is: A Python job scraping package that aggregates common job boards.
- Relevant lessons:
  - Normalized job schemas and source-specific adapters are the right shape.
  - Adapter health and source volatility need ongoing monitoring.
  - Query/filter ergonomics matter once job volume grows.
- Avoid copying:
  - Login-based platform scraping, proxy rotation, anti-bot bypasses, and platform ToS risk. This repo's boundary is public official recruitment pages only.

### Job Application Trackers / Career CRMs

- Examples seen in GitHub search: self-hosted job trackers, job application CRM projects, and AI career assistant experiments.
- Relevant lessons:
  - A useful job product usually needs a personal workflow state, not only search: saved, evaluating, preparing, applied, rejected, archived.
  - Deadline, source, notes, and application status are high-value fields.
  - A narrow tracker layer can make the current job library feel like a user workbench.
- Avoid copying:
  - Full CRM/account/team scope before the single-user job-to-resume loop is crisp.

## Relevant Standards And Official References

### JSON Resume

- Source: <https://jsonresume.org/schema/>
- Why it matters:
  - Provides a widely known resume data model vocabulary.
  - Useful reference for export/template interoperability and eventual profile schema cleanup.
- Fit for this project:
  - Use as inspiration, not as a direct replacement. The current profile schema needs medical/research-specific fields and evidence IDs.

### schema.org JobPosting

- Source: <https://schema.org/JobPosting>
- Why it matters:
  - Provides a standard vocabulary for job postings: title, hiring organization, date posted, valid through, employment type, job location, qualifications, responsibilities, education requirements.
- Fit for this project:
  - Useful to align normalized job fields and future public/export contracts.
  - High priority fields to add or harden: `datePosted`, `validThrough` / deadline, hiring organization, job location, qualifications, responsibilities.

### W3C PROV-O

- Source: <https://www.w3.org/TR/prov-o/>
- Why it matters:
  - Official provenance vocabulary for entities, activities, agents, generated-at time, and source derivation.
- Fit for this project:
  - The repo already has provenance concepts. PROV-O can guide naming for future evidence and audit trails without requiring a full RDF implementation.
  - Useful concepts: source entity, crawl activity, parser agent, generated job entity, profile fact entity, resume draft entity.

### Robots Exclusion Protocol

- Source: <https://www.rfc-editor.org/rfc/rfc9309>
- Why it matters:
  - Official robots.txt protocol. Public-source crawling should be deliberate about allowed/disallowed paths and respectful request behavior.
- Fit for this project:
  - Add as a future crawler-quality guardrail if real crawling expands.
  - Keep current no-login/no-bypass rule.

### O*NET

- Source: <https://services.onetcenter.org/>
- Why it matters:
  - Official US occupation/skills/abilities/work-activities data.
- Fit for this project:
  - Useful as a skills-taxonomy benchmark, especially for general abilities and work activities.
  - Not China-medical-specific enough to replace local rules.

### ESCO

- Source: <https://esco.ec.europa.eu/en/use-esco/use-esco-services-api>
- Why it matters:
  - Official European skills/competences/occupations classification and API.
- Fit for this project:
  - Useful for the shape of a skill taxonomy and synonym mapping.
  - Should be adapted cautiously because Chinese medical recruitment language differs.

## Product Conclusions

### 1. Keep The Differentiation Narrow

Do not compete as a generic resume builder. Own the wedge:

- Medical/public-health/research job seekers.
- Official public recruitment evidence.
- Truthful profile facts.
- Explainable job requirement matching.
- Exportable resume draft after evidence review.

### 2. Turn Provenance Into User Value

Traceability should not stay as backend metadata. It should become user-facing trust:

- Job source badge: official page, Excel attachment row, PDF evidence-only, fixture demo.
- Parser confidence badge.
- "Last fetched at" and original announcement link.
- Resume evidence chain: job requirement -> matched profile fact -> generated draft item.

### 3. Build The Aha Moment Around Evidence

The strongest first-time experience should be:

1. Load demo or crawl enabled institutions.
2. Pick one target job.
3. Import or load example profile.
4. Generate a draft.
5. See matched evidence and gaps.
6. Export an employer-facing version that omits internal diagnostic gaps.

### 4. Add Job Workflow State Before More Adapters

The next product layer should make jobs actionable:

- Saved / ignored / preparing / applied.
- Deadline and note fields.
- Match summary: "matched N of M requirements".
- Filter by actionable status.

This will create more user value than adding many low-quality sources.

### 5. Separate Market Insight From Parser Operations

The current analytics page mixes user insight with data-quality operations. Future UI should split:

- Market insight: categories, education, capabilities, institution focus.
- Data quality: parser confidence, attachment failures, low-confidence review queue.

### 6. Avoid Keyword-Stuffing Incentives

Resume-matching products often drift into ATS keyword stuffing. This project should explicitly avoid that:

- No suggestion should introduce a fact absent from the structured profile.
- Missing requirement suggestions should say "add if true" or "prepare supporting material", not "write X".
- Evidence strength should be explicit: strong, partial, weak, absent.

## Candidate Next Research Tasks

1. Sample 10-20 real medical recruitment announcements and manually label the most common requirement types.
2. Compare the current profile schema against JSON Resume and medical/research needs.
3. Define a minimal internal evidence vocabulary inspired by PROV-O.
4. Create a small golden set for requirement -> evidence -> draft evaluation.
5. Review robots.txt and polite crawling expectations for the enabled official sites before expanding adapters.
