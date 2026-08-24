# Product


## Platform

web

## Users

Primary: recruiters operating at scale — solo recruiters, agencies, and high-volume hiring pipelines screening dozens to hundreds of resumes against a single job description. They work under time pressure, low tooling overhead, and need to triage quickly without a full ATS. Secondary audiences are not confirmed; design should not optimize for hiring managers or casual HR until validated.

## Product Purpose

Smart Resume Screener makes batch resume screening fast and explainable without an ATS. Upload a job description (text or file) + batch resumes (PDF/DOCX/TXT) → LLM parsing + semantic embeddings produce a scored, ranked shortlist. Purpose is to reduce triage time and surface nuanced fit beyond keyword matching. Success is a trustworthy ranked list with clear evidence (matching/missing skills, sub-scores, analysis) that a recruiter can act on in minutes.

## Positioning

Meaningfully different mechanism: LLM + semantic scoring. Combines structured parsing (skills, experience, education), embedding-based semantic similarity (OpenAI `text-embedding-3-small` or local), and LLM-generated fit analysis into a 0–10 score with shortlist flag and sub-scores (skills/experience/education). Unlike keyword filters, it captures conceptual alignment and explains gaps. Neighboring products that only keyword-match or hide reasoning cannot copy this explainable semantic ranking without the same pipeline.

## Operating Context

- Workflow: create session → file or paste JD → normalize requirements → batch-upload resumes → poll session status → fetch parsed candidates + match details → filter by score/status/search → re-score all → export JSON/CSV. All runs inside a single dashboard (two-column: JD inputs left, results right).
- Environments: web dashboard on Next.js 16.3.2 + Tailwind v4 (dark, glass/surface tokens), FastAPI + MongoDB Atlas backend with in-process worker for scoring. Local dev on `localhost:3000` (HMR), API via `NEXT_PUBLIC_API_BASE` or proxied.
- Rituals: no ATS sync required; resumes are sent automatically after a JD is provided; polling drives scoring state; re-score recovers parse-failed candidates.

## Capabilities and Constraints

- Confirmed capabilities: JD via text or file (`.pdf/.docx/.txt`, ≤10 MB), batch resume upload (≤10 MB each, PDF/DOCX/TXT only), normalized requirements extraction, per-candidate parsing, semantic similarity, LLM match scoring with tolerant JSON parsing, shortlisting, filtering (score ≥5–9, status, search), deletion, and exports.
- Constraints: keep stack and flows — Next.js 16 (app router, `react-dropzone`, `framer-motion`), FastAPI + MongoDB Atlas (`MONGO_URI`, `LLM_API_KEY`, `EMBEDDING_PROVIDER=openai`), existing dark theme tokens (`--color-bg: #0b0d10`, `--color-surface`, `--color-accent: #34d399`, `--color-1..5` rainbow), and dashboard information architecture. Do not add heavy dependencies or break polling/auth (`srs_token`).
- Undecided: integrations (ATS, email), multi-role/multi-session management, privacy/GDPR handling, pricing.

## Brand Commitments

- Name: Smart Resume Screener (no established logo/voice to preserve). Current identity is a minimal dark dashboard with `◆` mark, Inter + JetBrains Mono, glass cards, grid-pattern accents, and the four sampled UI primitives when work touches UI: Shining Text (HextaUI) for loading, Rainbow Button (Magic UI) for all buttons, File Upload (Aceternity) for both drop zones, Card with Grid Ellipsis (Indie UI) for all text/candidate containers. No other brand assets are binding.

## Evidence on Hand

- Live codebase: `web/app/page.tsx` dashboard, `web/components/*` (CandidateCard, CandidateDetail, JobDescriptionForm, JDFileUploader, Uploader, ScoreGauge), `web/components/ui/*` (rainbow-button, shining-text, file-upload, grid-pattern-card), `app/api/*` + scoring/matching pipelines. No fabricated testimonials, case studies, or benchmarks; evidence is the runnable product and its 28 unit + 4 e2e gates.

## Product Principles

1. **Explain the score or don't show it.** Every ranking must be accompanied by matching/missing skills, sub-scores, and a short analysis that a recruiter can audit.
2. **Speed over setup.** The path JD → resumes → ranked shortlist should require minimal configuration and survive interruptions (polling, re-score).
3. **Trust through transparency.** Handle parse/LLM failures explicitly, preserve partial progress, and never hide uncertainty behind a clean number.

## Accessibility & Inclusion

No product-specific accessibility requirement was established in this round. The dashboard must remain keyboard-operable and screen-reader-friendly (proper labels on drop zones, dialogs, and filters), but no WCAG target was confirmed.
