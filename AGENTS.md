# AGENTS.md — SecureLife AI

Guidance for AI coding assistants (Claude Code, Codex, Cursor, …) working in this repo. Paths are relative to the repo root.

## Project

SecureLife AI — a lead-qualification + insurance-document intelligence CRM for a fictional Indian insurance broker (SecureLife Insurance Brokers). Design rationale lives in `docs/ARCHITECTURE.md`; setup lives in `README.md`.

## Stack

- **Backend**: Python 3.12+, FastAPI, Pydantic v2, SQLAlchemy 2 (async), SQLite, uv.
- **AI**: Groq via the `openai` async SDK (`AsyncOpenAI`) pointed at `https://api.groq.com/openai/v1`. One model per agent via `GROQ_MODEL_*` env vars: `qwen/qwen3.8-27b` (chat, analysis), `openai/gpt-oss-20b` (chat extractor, qualification), `openai/gpt-oss-120b` (document extraction) — chosen so consecutive broker steps never share a per-minute rate-limit bucket.
- **PDF**: PyMuPDF for validation AND for the per-page text extraction we feed the model (Groq's text models can't ingest PDFs natively). Scanned PDFs are a known limitation — pages with no text layer are reported honestly rather than fabricated.
- **Frontend** — two SPAs:
  - `frontend-prospect/` — React 19, Vite, Tailwind v4. Minimal: a single chat page, hand-rolled fetch client, hand-rolled types. Port 5174.
  - `frontend-broker/` — React 19, Vite, Tailwind v4, React Router v7, TanStack Query v5, `openapi-fetch` typed from backend OpenAPI. Port 5173.
- **Monorepo layout**: `backend/`, `frontend-broker/`, and `frontend-prospect/` as siblings.

## Running locally — three terminals

```bash
# Terminal 1 — backend (http://localhost:8000)
cd backend
cp .env.example .env         # then set GROQ_API_KEY
uv sync
uv run uvicorn app.main:app --reload --port 8000

# Terminal 2 — broker dashboard (http://localhost:5173)
cd frontend-broker
npm install
npm run dev

# Terminal 3 — prospect chat (http://localhost:5174)
cd frontend-prospect
npm install
npm run dev
```

Both Vite dev servers proxy `/api` to `127.0.0.1:8000`. `backend/.env.example` documents every setting.

## Checks to run after a change

These are fast and spend no Groq tokens:

```bash
cd backend && uv run pytest -q
cd frontend-broker && npm run typecheck
cd frontend-prospect && npx tsc -b --noEmit
```

- `frontend-broker`: `npm run gen:api` regenerates `src/api/types.ts` from the running backend. Run it whenever a backend response schema changes.
- `backend/scripts/seed.py` inserts 7 demo leads, at least one per pipeline stage. `--reset` wipes the database first; it's needed after any column change, since there are no migrations.
- `backend/scripts/verify_groq.py` and `backend/scripts/e2e_smoke.py` call the real Groq API and use up the free-tier quota. Don't run them, or any other live-model test, unless the user asks.

## Coding conventions

### Python

- **Every LLM-backed capability is an agent.** One class per job in `backend/app/agents/<name>_agent.py` (`ChatAgent`, `ChatExtractorAgent`, `QualificationAgent`, `DocumentExtractorAgent`, `AnalysisAgent`), one prompt at `backend/app/prompts/<name>_agent.md` referenced via the class's `PROMPT_NAME`. Agents never touch the DB. In the broker UI, actions that run an agent say so ("Run analysis agent"). The prospect app keeps saying "assistant" — no agent jargon there.
- **Agents propose, code decides.** Agent output always passes through deterministic code before it's stored: `QualificationScorer` verifies evidence and dealbreaker quotes and computes the score/verdict (any verified dealbreaker → `NOT_QUALIFIED`); orchestrators own status transitions. Don't let an agent set status or a final score directly.
- **What the chat asks lives in one place.** `backend/app/services/question_plan.py` defines the core facts and the 2–4 facts per insurance type. The chat agent, chat extractor, broker checklist and qualification agent all read it — add or change questions there, never in a prompt.
- **ORM entities live in `backend/app/data_models/`** (not `models/` — "model" means an LLM in this codebase).
- **OOP by default.** Services, repositories, agents, orchestrators are classes with methods — not loose module-level functions. Pydantic models stay as classes. One-line utilities (`slugify`-style) can remain functions.
- **Dependency injection via constructor**, not module-level singletons. The one exception is `functools.lru_cache` factories for process-wide clients (Groq AsyncOpenAI, Settings).
- **Pydantic DTOs are separate from ORM models.** Never return ORM instances from a route; map via `from_attributes=True`.
- **Out-schemas use `extra="allow"`** so adding fields later doesn't break the frontend contract.
- **No inline prompt strings.** Prompts live as markdown files under `backend/app/prompts/` and are loaded via `PromptLibrary`.
- **Async everywhere in the agents.** Use `AsyncOpenAI`. Never block the event loop with sync model calls.
- **Every model call goes through `ModelFallback`** (`app/agents/client.py`): `await ModelFallback.for_agent(primary).create(client, ...)`. Never call `client.chat.completions.create` directly in an agent — a rate-limited model must hand off to the next. Anything that gates broker visibility (name, contact) must also have a deterministic path (`services/contact_capture.py`, `services/name_capture.py`).
- **Respect Groq's per-minute limits.** A request whose `max_tokens` exceeds the org's output-tokens-per-minute limit (1000 on the free tier) can be rejected outright, and prompt + `max_tokens` must fit each model's 8000 tokens-per-minute bucket. Every agent takes its cap from a `GROQ_MAX_TOKENS_*` setting; never hard-code `max_tokens`. Pass `extra_body=reasoning_options(model)` so gpt-oss models use low reasoning effort.
- **Background work owns its own DB session.** Use `asyncio.create_task` + `async with db.session()` — do NOT reuse a request-scoped session, it'll be torn down before the task finishes.
- **PDF handling**: use `PyMuPDF` to pull the text layer with `--- Page N ---` markers before sending to the model. Groq's chat models are text-only — do not attempt to attach PDF bytes directly.
- **User-safe errors at the boundary**: every exception that could reach the UI must go through `app.agents.errors.user_safe_message()`. Raw `str(exc)` must never appear in SSE frames, `Document.error_message`, or HTTP response bodies. Full exception stays in `log.exception(...)`.

### TypeScript / React

- **Broker app**: use the generated `openapi-fetch` client. `import { api } from '@/api/client'` and `api.GET('/api/leads', …)`. Don't hand-write fetch calls.
- **Prospect app**: use the thin `api` object in `frontend-prospect/src/api/client.ts`. It owns a minimal hand-rolled type surface for the three endpoints the chat needs. Do NOT drag `openapi-fetch` into the prospect app — keeping its bundle small is a feature.
- **Query keys** are stable arrays, e.g. `['leads']`, `['document', id]`, `['analysis', leadId]`.
- **Polling for status**: use `refetchInterval` on react-query. Stop polling when the status reaches a terminal state.
- **Streaming (chat)**: POST + SSE via `fetch` + `ReadableStream` (POST is not supported by native `EventSource`). The utility lives at `frontend-prospect/src/lib/sse.ts`.
- **Styling**: Tailwind utility classes. UI primitives in `components/ui/*` follow the shadcn convention (`cva`, `cn`, forwardRef). Both apps keep their own copies — tiny files, easier than a shared package for the MVP.

## Business rules worth knowing

- **Broker list hides incomplete prospects by default.** `GET /api/leads` returns only leads with `full_name` AND at least one of (`email`, `phone`). The chat flow still creates and updates Lead rows from the first turn — they just stay invisible to the broker until the prospect shares the mandatory fields. Pass `?include_incomplete=true` to override (QA tooling). The prospect app rehydrates via `GET /api/leads/{id}`, which is never filtered.
- **Agents run when the broker says so.** Upload stores a PDF as `UPLOADED`; extraction starts only on `POST /api/documents/{id}/extract`. The chat flow records facts but never touches `status` or `qualification_score`.
- **Qualification.** `POST /api/leads/{id}/qualify` refuses (400 + `missing`) until name, contact and insurance type are captured (`REQUIRED_TO_QUALIFY` in `question_plan.py`) — no tokens spent. Intent and timeline are asked in chat but don't block; the agent reads urgency from the transcript. The broker can correct insurance type, intent and timeline from the Edit dialog (`PATCH` with `extracted_fields`). Otherwise it runs the qualification agent. A `QUALIFIED` verdict requires score ≥ `QUALIFICATION_THRESHOLD` and no missing plan facts. The verdict is stored on the lead (`qualification_verdict`) but never closes it.
- **Pipeline stages = dashboard tabs.** `Lead.status` is one of `NEW` (New leads) → `IN_PROGRESS` (qualification agent has run) → `DOCS_PENDING` (qualified + documents uploaded) → `ANALYZED` (analysis agent has run), or `CLOSED`. Every automatic transition goes through `backend/app/services/pipeline.py::PipelineRules` — never set `lead.status` directly in a route or orchestrator. Closing is a broker action: `PATCH status=CLOSED` requires `close_reason` (`DISQUALIFIED | PURCHASED | OTHER`) plus an optional `close_note`; re-opening clears them.
- **Hard delete.** `DELETE /api/leads/{id}` cascades to messages, qualifications, documents, extractions, analyses via ORM `all, delete-orphan`. No soft-delete, no audit log — prod would want both. UI gates behind a confirmation dialog.
- **Visibility ≠ qualification.** The broker list shows a prospect once name + contact exist, independent of qualification. `profile_completeness` (how much of the question plan is captured) and `qualification_score` (the agent's judgement) are different numbers.

## Shared files — change with care

These files wire the whole app together. When several agents work in parallel, have one owner per change to them:

- `backend/app/main.py`
- `backend/app/db.py`
- `backend/app/settings.py`
- `backend/app/agents/client.py`
- `backend/app/agents/prompts.py`
- `backend/app/data_models/__init__.py` (the individual entity files are owned by their domain)
- `backend/app/routers/__init__.py`
- `backend/app/schemas/__init__.py`
- `backend/pyproject.toml`
- `frontend-broker/vite.config.ts`
- `frontend-broker/src/App.tsx`
- `frontend-broker/src/api/client.ts`
- `frontend-prospect/vite.config.ts`
- `frontend-prospect/src/App.tsx`

If a change needs a new field on an existing `Out` schema, add it as optional (safe because of `extra="allow"`). Removing or renaming is a cross-system contract change — regenerate TS types with `cd frontend-broker && npm run gen:api`.

## Where new work goes

- **New domain entity** → `backend/app/data_models/<entity>.py` + import in `data_models/__init__.py` + matching schema in `backend/app/schemas/`.
- **New LLM-backed capability** → a new agent class in `backend/app/agents/<name>_agent.py` + a prompt file at `backend/app/prompts/<name>_agent.md` + `GROQ_MODEL_<NAME>` / `GROQ_MAX_TOKENS_<NAME>` settings. Pick a model whose rate-limit bucket isn't already used by the step before it.
- **New insurance type or question** → `backend/app/services/question_plan.py` (+ a typed field on `LeadExtractedFields` if it's a new key).
- **New route** → router module under `backend/app/routers/` + register in `routers/__init__.py`.
- **New broker UI primitive** → `frontend-broker/src/components/ui/<primitive>.tsx` following the `cva`/`cn`/forwardRef pattern.
- **New broker page** → `frontend-broker/src/pages/<Name>Page.tsx` + register in `App.tsx` router.
- **New prospect-facing feature** → think twice. The prospect app is intentionally minimal (chat only). If it's a prospect-UX feature, add it to `frontend-prospect/`. If it's actually a broker tool, keep it in `frontend-broker/`.

## What not to do

- Don't commit `backend/.env` or any file with a real API key.
- Don't invent fake data in production code paths. Demo data belongs in `backend/scripts/seed.py` only.
- Don't hard-code machine-specific paths (home directories, drive letters) in code, docs or scripts. Resolve paths relative to the repo or from settings.
- Don't add agent frameworks (LangChain, LangGraph, CrewAI). Direct `openai` SDK calls against Groq's OpenAI-compatible endpoint are correct for this project.
- Don't use `FastAPI BackgroundTasks` for LLM work — session lifetime trap. Use `asyncio.create_task` + session-per-job.
- Don't bypass the typed API client with hand-written fetch — unless you're in the prospect app, which deliberately uses a thin hand-rolled client.
- Don't skip the `extra="allow"` config on `Out` schemas.
- Don't collapse the two frontends back into one. The split is deliberate and documented in `docs/ARCHITECTURE.md` ("Tech stack and why").
- Don't surface broker-side CRM language ("Pipeline", "Qualification score", "Lead") in the prospect app. The prospect sees warmth, not a sales funnel.
