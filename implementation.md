# Smart Resume Screener — Implementation Plan (Demo Parity)

> **Goal:** make the application match the `DemoVideo.mp4` flow and visuals exactly — from the login screen through the end-to-end screening workflow.
>
> **Scope:** full-stack — FastAPI (backend) + Next.js/React/TypeScript/Tailwind (frontend) + MongoDB.

---

## 1. Demo flow (source of truth)

Captured from `DemoVideo.mp4` (~1:33). The complete end-to-end flow is:

1. **Login page** — light beige background, white card. Small green "SMART RESUME SCREENER" eyebrow, bold "Welcome back", subtext "Sign in to continue screening candidates." Fields: **Email** and **Password**. Solid green "Login" button. Footer "Don't have an account? **Create an account**".
2. **Dashboard** — three numbered sections, left column (inputs) + right column (results):
   - **01 — Define the job**: "Role title" input, "Job description text" textarea, "File job description" submit button.
   - **02 — Add candidates**: "Upload resumes" drop zone ("Drop resumes here or click to browse", "PDF or TXT - multiple files supported"), a live candidate counter, and a per-file status log ("`file.pdf - parsed (20 skills found)`").
   - **03 — Review the shortlist**: a "Score all candidates" / "Re-score all candidates" button, and candidate cards.
3. **Candidate card** — circular overall score (e.g. "7.2"), a "SHORTLISTED" badge, email + "0 yrs experience", **Skills / Experience / Education** sub-score breakdown, an analysis sentence with a **semantic similarity** score, green (matching) vs. red (missing) skill tags, and **Details** / **Delete** buttons.
4. **Details modal** — tabs (Skills / Experience / Education), education line, "EXPERIENCE (N YRS DETECTED)" with projects + leadership, "RAW RESUME TEXT" section.

**Header chrome throughout:** title + green diamond icon, "API connected" status pill (green dot), "Logout" button.

---

## 2. Decisions made during conversation

| Topic | Decision |
|---|---|
| Login identifier | **Email + password** (demo-exact). Username removed from login; email is the login identifier. Username kept only on the sign-up form. |
| JD entry | **Both paste text and file upload**. Role-title field + job-description textarea + "File job description" button, AND retain the existing JD file upload. |
| Scoring model | **Demo breakdown**: overall 0–10 score (float) + Skills / Experience / Education sub-scores + semantic-similarity score + matching vs. missing skills + a shortlist flag + an analysis sentence. |
| Visual theme | **Match the demo's light beige + green** aesthetic, replacing the current dark glassmorphism. |
| Sign-up | **Open self-registration** (no invite gate): username + email + password + confirm. |
| Auth model | **Per-user accounts** in MongoDB (bcrypt) + JWT; the entire `/v1` screening API is protected. |
| JD re-scoring | **Already implemented**: updating a JD resets existing candidates and re-enqueues scoring (preserved). |

---

## 3. Architecture

```
Next.js (React 19, TS, Tailwind v4)
        │  JSON + Bearer JWT
        ▼
FastAPI  (/v1/auth/*  — open;  /v1/sessions/*, /v1/candidates/* — protected)
        │
        ├── MongoDB  (sessions, users, jobs)  — candidates embedded in session docs
        ├── LocalFileStorage  (originals, dev)
        └── AtlasTaskQueue → ResumeWorker
                ├── parse (extract resume)
                ├── score (LLM breakdown + embeddings)
                └── re-score on JD change
```

### Data model change

Replace `MatchResult` with a demo-shaped result:

```python
class MatchResult(StrictModel):
    candidate_id: str
    score: float                  # 0–10, one decimal (e.g. 7.2)
    skills_score: float           # 0–10
    experience_score: float       # 0–10
    education_score: float        # 0–10
    matching_skills: list[str]    # green tags
    missing_skills: list[str]     # red tags
    semantic_similarity: float    # 0–10 (embeddings)
    analysis: str                 # the natural-language sentence
    shortlisted: bool             # score >= threshold (default 7.0)
    model: ModelMetadata
```

`score` becomes a float, which touches `ScoreGauge` (currently integer-only) and candidate sorting. The `users` collection keeps its unique `email` index; login resolves by email.

---

## 4. Phase-by-phase implementation plan

### Phase 1 — Login + sign-up parity
- **`app/api/auth.py`**: `LoginRequest` → `{email, password}`; resolve via `get_by_email`, verify bcrypt hash, issue JWT (`sub` = user id or email). `SignupRequest` already `{username, email, password}`.
- **`app/db/user_repository.py`**: ensure unique `email` index + `get_by_email` (present).
- **`web/app/login/page.tsx`**: swap username → email field; call `api.login(email, password)`.
- **`web/lib/api.ts`**: `login(email, password)` sends `{email, password}`.
- **Tests**: update login test to use email; add unknown-email case.

### Phase 2 — JD entry: role title + paste text + file upload
- **`app/api/routes.py`**: add optional `title` to `JobDescriptionRequest`; pass through `save_job_description` so the normalized JD `title` can be overridden. Reuse existing `/job-description` (text) and `/job-description/file` endpoints (both already trigger `rescore_session`).
- **Frontend**: new `JobDescriptionForm` (role title + textarea + "File job description" button → `POST /v1/sessions/{id}/job-description`). Keep `JDFileUploader` (file path) as a secondary "or upload a file" control.
- **Note**: role title is display/metadata; scoring uses normalized requirements from the description text.

### Phase 3 — Candidate count + per-file parse status log
- **`app/api/routes.py`**: `session_status` already returns `total` + per-file `status`; derive `skills_count` from `resume.parsed_json.skills` on read (no migration).
- **Frontend**: in "02 — Add candidates", render a live counter + status list ("`{filename} - parsed ({n} skills found)`").

### Phase 4 — Scoring model: demo breakdown
- **`app/domain/match.py`**: rewrite `MatchResult` to the §3 shape.
- **`app/matching/scoring.py` + `app/llm/client.py` + `prompts/match_scoring_v1.txt`**: update the prompt to return `{score, skills_score, experience_score, education_score, matching_skills, missing_skills, semantic_similarity, analysis}`. Compute `semantic_similarity` from embeddings when available; fall back to a lexical/Jaccard skill-overlap score when no embedding client is configured.
- **`app/matching/embeddings.py`**: add an OpenAI embeddings-backed `EmbeddingClient` (or keep `NullEmbeddingClient` + lexical fallback).
- **`app/workers/tasks.py`**: `score_candidate` persists the new fields; `shortlisted = score >= 7.0`.
- **`app/api/routes.py`**: `/matches` returns the new fields; `candidate_detail` includes the full breakdown + `resume.extracted_text` (raw-text tab) + `parsed_json`.
- **`web/lib/types.ts`**: mirror the new `Match` shape.

### Phase 5 — Candidate card + details modal
- **`web/components/CandidateCard.tsx`** (rewrite): circular float score, SHORTLISTED badge, email + experience, Skills/Experience/Education sub-score boxes, green/red skill tags, analysis sentence with semantic-similarity, Details + Delete buttons.
- **`web/components/CandidateDetail.tsx`** (new modal): tabs Skills / Experience / Education; education summary; "EXPERIENCE (N YRS DETECTED)" with projects + leadership; "RAW RESUME TEXT" from `resume.extracted_text`.
- **`app/api/routes.py`**: add `DELETE /v1/candidates/{candidate_id}` — remove from session `candidates` array + delete the original from storage.
- **Frontend**: wire Delete to the new endpoint, then re-poll.

### Phase 6 — "Score all / Re-score all candidates"
- **Backend**: add `POST /v1/sessions/{session_id}/score` (reuse `rescore_session` for every parsed candidate).
- **Frontend**: "Score all candidates" (enabled when JD filed + candidates exist) and "Re-score all candidates" (when already scored). Both call the endpoint and re-poll.

### Phase 7 — Visual theme: light beige + green
- **`web/app/globals.css` + `web/tailwind.config.ts`**: replace dark tokens with the demo's light palette (near-white beige background, white cards, green accent). Update `--color-bg`, `--color-surface`, `--color-text*`, `--color-accent*`, borders; remove the dark radial dot texture.
- **Components**: restyle header (green diamond icon, "API connected" pill, Logout), cards, drop zone, buttons, modal.

### Phase 8 — Header chrome & "API connected" status
- **Frontend**: add an "API connected" status pill (green dot) driven by a lightweight `/health` poll. Add the green diamond icon + restyle "Logout".

### Phase 9 — Tests, docs, verification
- **Backend tests**: update `test_scoring.py`, `test_workers.py`, `test_mongo_repository.py`, `test_session_routes.py` for the new `MatchResult` fields + delete-candidate endpoint.
- **Frontend tests**: update `components.test.tsx` + add `CandidateDetail` test; update `dashboard.spec.ts` for the new card/breakdown + email login.
- **Docs**: update `README.md` (email login, new scoring, delete, light theme).
- **Verification gates**:
  - Backend: `pytest -q`, `ruff check .`, `mypy app tests scripts`
  - Frontend: `npx tsc --noEmit`, `NODE_ENV=test npm test`, `npm run test:e2e`, `npm run build`

---

## 5. Files created / modified

**Create**
- `web/components/JobDescriptionForm.tsx`
- `web/components/CandidateDetail.tsx` (+ `.module.css`)

**Modify**
- `app/api/auth.py` (email login)
- `app/api/routes.py` (title field, delete candidate, score-all endpoint, match fields)
- `app/db/user_repository.py` (email lookup wiring)
- `app/domain/match.py` (new MatchResult)
- `app/matching/scoring.py`, `app/matching/embeddings.py`, `app/llm/client.py`
- `app/workers/tasks.py`
- `prompts/match_scoring_v1.txt`
- `web/lib/types.ts`, `web/lib/api.ts`
- `web/app/login/page.tsx`, `web/app/page.tsx`, `web/app/globals.css`, `web/tailwind.config.ts`
- `web/components/CandidateCard.tsx`, `ScoreGauge.tsx`, `Uploader.tsx`, `JDFileUploader.tsx`, `StatusStrip.tsx`
- tests (backend + frontend), `README.md`

**Rewrite**
- `implementation.md` (this document)

---

## 6. Risks & notes

- **Float score migration**: `score` changes `int → float`. Sorting, gauge clamping, and any `>= 7` shortlist logic must all switch to float. Backward-compat with existing `scored` documents is out of scope (dev data is disposable; the worker re-scores on JD change anyway).
- **Semantic similarity needs embeddings**: if no embedding provider is configured, fall back to lexical skill-overlap so the UI never renders a blank similarity.
- **Open sign-up**: per the decision, registration is now open. If the app becomes public-facing, revisit with an invite/allow-list gate.
- **The demo is a separate static prototype** (`login.html`, `index.html` on `localhost:5500`); this plan re-implements its behavior in the existing Next.js + FastAPI stack, not by porting its HTML.
