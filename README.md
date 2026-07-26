# School ERP — Autonomous Substitute Agent
### Project Overview & Onboarding Guide

---

## 1. Project Title & Core Vision

**Project name (working title):** The Staffroom Ledger — an AI-powered School Operations Command Center

**The problem:** School administration is heavily manual — physical leave forms, siloed timetables, and admins manually resolving scheduling conflicts (e.g., "Teacher X is on leave, who covers their classes?") by hand.

**What this application does:** It closes that loop end-to-end, with no manual scheduling work required:

1. An admin uploads a photo/scan of a physical leave application form.
2. A vision-language model (Gemini) extracts structured data from it — teacher name, date, reason, sections affected — with a **confidence score per field**.
3. If confidence is high enough, the system automatically identifies every class session that teacher was scheduled to teach that day, and a **constraint solver (Google OR-Tools CP-SAT)** finds the best substitute(s) for each vacant session — factoring in subject qualification, current daily workload, and a **fairness constraint** (don't keep picking the same overused substitute).
4. The resolved schedule change is applied directly to the live timetable in the database, and the admin dashboard updates in real time to show exactly what changed and why.
5. If confidence is too low (e.g. illegible handwriting), the form is flagged **"needs review"** instead of guessing — and the admin can manually correct the flagged fields in the dashboard, which re-triggers the same solving pipeline.

**High-level goal for AI integration:** The AI's job is strictly **document understanding** (turning a messy photo into structured, confidence-scored data). All actual scheduling decisions are made by a deterministic constraint solver, not the AI model — this is a deliberate design choice: the AI never "decides" who teaches what, it only reads forms. This keeps the scheduling logic auditable, testable, and explainable (every substitution decision has a plain-English reasoning string attached).

---

## 2. Tech Stack Summary

### Backend
| Component | Technology |
|---|---|
| API framework | FastAPI (Python) |
| Server | Uvicorn |
| Language | Python 3.14 |
| Database | Supabase (hosted Postgres) |
| DB client | `supabase-py` |
| Vision / document extraction | **Google Gemini API** (`google-genai` SDK) — currently `gemini-3.5-flash` (free tier; Google renames this model frequently, check `ai.google.dev` if extraction starts failing with a 404) |
| Scheduling / constraint solving | Google OR-Tools (`ortools`), specifically the CP-SAT solver |
| Env config | `python-dotenv` |
| Validation | Pydantic (via FastAPI) |

### Frontend
| Component | Technology |
|---|---|
| Framework | React + TypeScript |
| Build tool | Vite |
| Styling | Tailwind CSS v4 (via `@tailwindcss/vite` plugin — **not** the old `tailwind.config.js` + PostCSS setup) |
| State management | Zustand (chosen as the web equivalent of the brief's Riverpod suggestion — Flutter-specific, so not applicable here) |
| Animation | Framer Motion (used sparingly, for the "ledger stamp" effect) |
| HTTP | Native `fetch` (no axios/react-query — kept deliberately simple) |

### Infrastructure (not yet deployed — currently local-only)
- Planned: Vercel (frontend) + Railway/Render (backend) + Supabase (already cloud-hosted)

---

## 3. Current Project Architecture & Folder Structure

```
school-erp/
├── backend/
│   ├── main.py                  # FastAPI app entrypoint — all HTTP routes live here, thin layer only
│   ├── db.py                    # Data access layer. SchoolDB Protocol + SupabaseDB implementation.
│   │                             # Deliberately separated so orchestrator logic can be tested with a
│   │                             # FakeDB (see agent/test_orchestrator.py) with no live DB needed.
│   ├── requirements.txt
│   ├── .env                     # NOT committed — SUPABASE_URL, SUPABASE_SERVICE_KEY, GEMINI_API_KEY
│   ├── .env.example
│   ├── venv/                    # Local virtualenv — NOT committed
│   │
│   ├── solver/
│   │   ├── substitute_solver.py # Pure function: solve_substitutions(vacant_sessions, teachers) -> assignments
│   │   │                         # Uses OR-Tools CP-SAT. Hard constraints: subject qualification, no
│   │   │                         # double-booking, daily load cap. Soft constraints (in objective):
│   │   │                         # minimize substitution_count_month (fairness) + current_load_today.
│   │   │                         # Gracefully degrades: if no valid assignment exists, returns top-3
│   │   │                         # "least-bad" fallback candidates instead of failing outright.
│   │   └── test_solver.py       # Standalone test using hardcoded demo data, no DB/API needed
│   │
│   ├── vision/
│   │   ├── extract_form.py      # extract_form_data(image_bytes) -> ExtractionResult
│   │   │                         # Calls Gemini with a strict JSON-schema system prompt, forcing
│   │   │                         # PER-FIELD confidence scores. Routes to "auto_applied" or
│   │   │                         # "needs_review" based on FIELD_CONFIDENCE_THRESHOLD (0.75) and
│   │   │                         # OVERALL_CONFIDENCE_THRESHOLD (0.70). Never trusts the model's
│   │   │                         # own confidence blindly — re-validates on the Python side.
│   │   └── test_extract_form.py # Tests the routing/validation logic with MOCKED model responses
│   │                             # (no live API calls) — proves the safety logic independent of
│   │                             # whether Gemini itself is available/correct that day.
│   │
│   └── agent/
│       ├── orchestrator.py      # The core pipeline glue. Two public entry points:
│       │   - process_leave_form(extraction, db): full automatic pipeline from a fresh extraction
│       │   - resolve_reviewed_form(form_id, corrected_fields, db): re-runs solving after a human
│       │     corrects a flagged field (treats human input as 100% confidence)
│       │   Both funnel into a shared private helper, _resolve_and_persist(), so behavior is
│       │   identical regardless of whether data came from AI or a human correction.
│       └── test_orchestrator.py # Tests the FULL pipeline logic with a FakeDB (in-memory, implements
│                                 # the SchoolDB Protocol) — no Supabase, no Gemini, no network calls.
│                                 # This is the most important test file: it proves the end-to-end
│                                 # decision logic (confidence gating → date parsing → solving →
│                                 # persistence) is correct independent of any external service.
│
├── frontend/
│   └── src/
│       ├── main.tsx, App.tsx    # App shell. App.tsx fetches the live timetable on mount (useEffect)
│       │                         # and renders the upload control + all dashboard panels.
│       ├── store.ts             # Zustand store — SINGLE source of client state. Two async actions:
│       │   - uploadForm(file): POSTs to /forms/upload, applies the result to state
│       │   - submitCorrection(correction): POSTs to /forms/{id}/review, applies result identically
│       │   Both funnel through a shared applyResult() helper so every dashboard panel (alerts,
│       │   ledger diff, review queue) updates consistently regardless of which path triggered it.
│       │   timetableGrid is ALWAYS re-fetched from the backend after any change — never inferred
│       │   client-side — Postgres is the single source of truth for the schedule.
│       ├── api.ts               # Thin fetch wrapper around the FastAPI backend. Exports:
│       │                         # uploadLeaveForm, submitReviewCorrection, fetchTimetable.
│       ├── mockData.ts          # Shape-matches the real API/DB schema exactly — used for initial
│       │                         # alerts and as a type reference; NOT used for the timetable grid
│       │                         # anymore (that's live-fetched).
│       ├── AlertFeed.tsx         # Proactive alerts panel (bottlenecks, fairness warnings, etc.)
│       ├── LedgerDiff.tsx        # THE signature visual: struck-through old assignment → new
│       │                         # assignment, with a rotated "RESOLVED" rubber-stamp animation
│       ├── ReviewQueue.tsx       # Shows extracted fields + confidence %. If status is
│       │                         # "needs_review", also renders <CorrectionForm> — an editable
│       │                         # form pre-filled with extracted values, submitting via
│       │                         # store.submitCorrection()
│       ├── TimetableGrid.tsx     # Live period-by-period schedule view, "SUB" tag on substitutions
│       ├── index.css             # Tailwind v4 @theme block — design tokens (see below)
│       └── vite-env.d.ts        # Typed import.meta.env for VITE_API_BASE_URL
│
└── supabase/
    ├── schema.sql                # Full Postgres schema — teachers, rooms, sections, timeslots,
    │                             # class_sessions (atomic schedulable unit), form_submissions,
    │                             # timetable_versions (diff history), substitution_log
    │                             # (explainability trail), alerts. Realtime enabled on the tables
    │                             # the frontend would subscribe to.
    └── seed.py                   # Populates realistic DEMO data with deliberate stress points:
                                  # a fairness trap (one overused substitute vs. an ideal
                                  # zero-substitutions candidate) and a room-capacity bottleneck,
                                  # so the solver and alert system have real conflicts to resolve.
```

### Data flow (the core loop)

```
[Photo of paper form]
      │
      ▼
POST /forms/upload  ──────────────► extract_form_data() [Gemini]
                                            │
                                    ExtractionResult (fields + confidence)
                                            │
                                            ▼
                                  process_leave_form() [orchestrator]
                                            │
                              ┌─────────────┴─────────────┐
                        confidence OK               confidence too low
                              │                             │
                              ▼                             ▼
                  get_affected_sessions()          return "needs_review"
                  + solve_substitutions()          (frontend shows CorrectionForm)
                  [OR-Tools CP-SAT]                          │
                              │                              ▼
                              ▼                    admin types corrected fields
                        apply_diff()                          │
                    (writes to Postgres)                      ▼
                              │                    POST /forms/{id}/review
                              │                    ──► resolve_reviewed_form()
                              │                        (same solving path, reused)
                              ▼
                  Response → Zustand store → every dashboard panel re-renders
                  → GET /timetable re-fetched → grid reflects new source of truth
```

### Design tokens (frontend visual identity — "Staffroom Ledger" theme)
Deliberately NOT a generic dark-SaaS dashboard — themed around a registrar's ledger book:
- `--color-ink` (#14213D, base navy), `--color-paper` (#EDE6D6, card surfaces), `--color-brass` (#C9A227, accent/stamps), `--color-sage` (#4F7965, success/resolved), `--color-rust` (#B33A3A, needs-review/critical)
- Fonts: Fraunces (display serif), Inter (body), IBM Plex Mono (data/timestamps — evokes stamped forms)

---

## 4. Current Working Features (fully functional, tested end-to-end with real APIs)

- ✅ Photo/scan upload → Gemini vision extraction with per-field confidence scoring
- ✅ Confidence-based routing: auto-apply vs. needs-review, with malformed-JSON and mixed-language handling
- ✅ CP-SAT constraint solver: resolves teacher vacancies with subject-qualification and daily-load hard constraints, and a fairness soft-constraint (avoids repeatedly picking an overused substitute)
- ✅ Graceful degradation: if no valid substitute exists, returns ranked fallback candidates instead of failing
- ✅ Human correction workflow: a form flagged "needs review" can be corrected via an editable form in the dashboard, which re-runs the exact same solving pipeline
- ✅ Live timetable persistence to Postgres (Supabase), with a `GET /timetable` endpoint as the single source of truth for the frontend grid
- ✅ Explainability: every substitution decision stores a plain-English reasoning string (`substitution_log` table)
- ✅ Proactive dashboard alerts (e.g., room-capacity bottlenecks, fairness warnings)
- ✅ Reactive frontend state (Zustand) — one backend response updates every dashboard panel consistently
- ✅ Full test coverage on the two riskiest pieces (solver logic, orchestrator pipeline) using fakes/mocks — no live credentials needed to verify core logic is correct

## Known limitations / things NOT yet built
- ❌ No authentication/authorization — anyone can hit any endpoint. CORS is wide open (`allow_origins=["*"]`). Fine for hackathon demo, NOT production-ready.
- ❌ No deployment yet — everything runs locally only.
- ❌ Only handles the "leave application → substitute reassignment" workflow. Other document types (admissions, fee receipts) mentioned in the original brief are not implemented.
- ❌ Predictive/forecasting alerts (the "digital twin" concept from early brainstorming) are not built — current alerts are simple rule-based checks (e.g., room capacity), not historical-trend predictions.
- ❌ No RFID/computer-vision attendance integration.
- ❌ Solver only resolves substitute-teacher assignment for a SINGLE affected teacher's sessions per form — it does not do full-timetable re-optimization.

---

## 5. Local Setup & Development Guide

### Prerequisites
- Node.js (any recent version)
- Python 3.11+ (tested on 3.14)
- A free Supabase account (supabase.com)
- A free Google Gemini API key (aistudio.google.com → "Get API key")

### Backend setup
```bash
cd backend
python3 -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

Create `backend/.env`:
```
SUPABASE_URL=your_supabase_project_url
SUPABASE_SERVICE_KEY=your_supabase_service_role_key   # NOT the anon key
GEMINI_API_KEY=your_gemini_api_key
```

### Database setup
1. In Supabase → SQL Editor, run the full contents of `supabase/schema.sql` (choose "Run without RLS" if prompted — the backend uses the service-role key which bypasses RLS anyway).
2. Seed demo data:
```bash
python3 ../supabase/seed.py
```

### Run the backend
```bash
uvicorn main:app --port 8000
```
**Do NOT use `--reload`** — with `venv/` nested inside `backend/`, the reloader can enter an infinite restart loop watching its own package cache files. Restart manually after code changes instead.

### Frontend setup
```bash
cd frontend
npm install
```

Create `frontend/.env`:
```
VITE_API_BASE_URL=http://localhost:8000
```

### Run the frontend
```bash
npm run dev
```
Open the printed local URL (typically `http://localhost:5173`).

### Verifying it works
- `http://localhost:8000/health` → `{"status":"ok"}`
- `http://localhost:8000/docs` → FastAPI's interactive API docs
- Upload a real photo of a leave-style note (teacher name, date, reason) via the dashboard's "Upload leave form" button

---

## 6. Upcoming Roadmap & Planned AI Features

High-level, not yet scoped in detail — areas to pick up next:

- **Deployment**: Vercel (frontend) + Railway/Render (backend), Supabase already cloud-hosted.
- **Additional document types**: extend the vision pipeline beyond leave applications (e.g., admission forms, fee receipts) — likely needs a form-type classifier or a type selector at upload time.
- **Predictive/forecasting alerts**: move beyond simple rule-based alerts (room capacity) toward historical-trend-based predictions (e.g., forecasting likely absence spikes or resource bottlenecks days in advance).
- **Full-timetable optimization**: currently the solver only resolves vacancies for one affected teacher per form; a more ambitious version could re-optimize larger chunks of the timetable at once.
- **Authentication & multi-admin support**: currently no login system; all actions are anonymous/unrestricted.
- **Attendance integration**: RFID or computer-vision-based attendance, mentioned in the original brief, not started.
- **Self-improving extraction**: logging human corrections (already captured implicitly via the review endpoint) could feed into prompt refinement or a lightweight fine-tuning loop over time.

---

## 7. Context Notes for AI Assistants (Claude / Cursor / ChatGPT / etc.)

- **Language/stack**: Python 3.14 + FastAPI backend; React + TypeScript + Vite frontend. Tailwind CSS is **v4** — uses `@theme` in CSS and the `@tailwindcss/vite` plugin, NOT a `tailwind.config.js` file or PostCSS. Don't "fix" the CSS by adding an old-style config file.
- **State management**: Zustand only. No Redux, no Context API for global state. A single store (`store.ts`) holds all dashboard state.
- **Testing philosophy**: Every risky/external-dependent module (solver, vision extraction, orchestrator) has a corresponding test file that uses **fakes/mocks instead of live credentials** — `FakeDB` implements the same `SchoolDB` Protocol as the real `SupabaseDB`, and vision tests mock the model's JSON response rather than calling the API. When adding new logic, follow this pattern: write it against an interface/protocol, test with a fake, only wire to the real service last.
- **Separation of concerns is intentional and strict**:
  - `db.py` — ONLY reads/writes rows. No business logic.
  - `solver/substitute_solver.py` — ONLY constraint-solving math. No I/O.
  - `vision/extract_form.py` — ONLY calls the vision model and validates/routes its output. No scheduling logic.
  - `agent/orchestrator.py` — the ONLY place that ties these together into a decision pipeline.
  - `main.py` — deliberately kept "boring": thin HTTP handlers only, no business logic.
  - Do not blur these boundaries — e.g., don't put solving logic in `main.py`, don't put DB queries in the solver.
- **The AI model (Gemini) never makes scheduling decisions** — it only extracts structured data from images. All actual substitute-assignment logic is deterministic (OR-Tools CP-SAT). Keep it this way — don't ask the LLM to "just decide who should substitute," since that breaks the auditability/explainability design goal.
- **Confidence-gating is a safety-critical pattern used throughout**: never let low-confidence AI output silently drive a real action. Any new AI-derived data source should follow the same pattern as `extract_form.py` — per-field confidence, explicit thresholds, and a human-in-the-loop fallback path (see `resolve_reviewed_form` in the orchestrator) rather than best-effort guessing.
- **Gemini model naming churns frequently** (renamed several times in 2026 alone). If extraction suddenly 404s, check `MODEL = "..."` in `vision/extract_form.py` against the current model list at ai.google.dev — this is a one-line fix, not a deeper bug.
- **The `class_sessions` table is the atomic schedulable unit** — not "class" or "period" — a single (section, subject, teacher, room, timeslot) combination. Any new scheduling feature should operate at this granularity.
- **`teacher_id` vs `original_teacher_id`**: `class_sessions` has two foreign keys into `teachers`. Any Supabase `.select()` that embeds `teachers` MUST disambiguate which relationship to use (e.g. `teachers!class_sessions_teacher_id_fkey(name)`), or PostgREST will throw an ambiguous-relationship error.
- **Timetable is always re-fetched from `GET /timetable` after any mutation** — never inferred/patched client-side. If you're tempted to update the grid optimistically in the frontend, don't; re-fetch instead, per the existing pattern in `store.ts`.
- **Local dev quirk**: never run `uvicorn` with `--reload` in this project structure (venv is nested inside the watched directory and can cause an infinite reload loop). Restart manually instead.