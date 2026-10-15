# SecureLife AI

A small CRM for an insurance broker. Prospects chat with an assistant that asks a few questions relevant to the cover they want. The broker then qualifies them, reads their existing policy PDFs and gets a written analysis, all with AI agents running on Groq.

The design, the trade-offs and the failure handling are in [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md); this file is just how to run it.


## Hosted Application

You can try the application live, hosted on **Render Free Tier**, using the links below:

- **Prospect Chat:** [Open Prospect Chat](https://securelife-ai.onrender.com/chat/)
- **Broker Dashboard:** [Open Broker Dashboard](https://securelife-ai.onrender.com/broker/)

> **Note:** Since the application is hosted on Render's free tier, the first request may take 30–60 seconds or longer while the server wakes up from inactivity.


## Setup

You need Python 3.12+, [uv](https://docs.astral.sh/uv/getting-started/installation/), Node.js 20+ and a free Groq API key from <https://console.groq.com/keys>.

Run each part in its own terminal, from the repo root.

**Backend** (http://localhost:8000, API docs at `/docs`)

```bash
cd backend
cp .env.example .env                 # then set GROQ_API_KEY in .env
uv sync
uv run python scripts/verify_groq.py # optional: checks the key and models
uv run python scripts/seed.py        # optional: 7 demo leads, one or more per stage
uv run uvicorn app.main:app --reload --port 8000
```

**Broker dashboard** (http://localhost:5173)

```bash
cd frontend-broker
npm install
npm run dev
```

**Prospect chat** (http://localhost:5174)

```bash
cd frontend-prospect
npm install
npm run dev
```

Both front ends proxy `/api` to the backend on port 8000.

### Docker (one container)

The image builds both front ends and runs everything behind one port, 8000: nginx serves the two apps and passes `/api` to the backend.

```bash
docker compose up --build
```

- Broker dashboard: http://localhost:8000/broker/
- Prospect chat: http://localhost:8000/chat/
- API docs: http://localhost:8000/docs

If `backend/.env` exists, Compose passes it to the container at run time (Compose 2.24 or later); it is never copied into the image. Every start is a fresh demo: the container wipes the database and uploaded PDFs, then loads the seven demo leads. Anything you add is gone after a restart.

Without Compose:

```bash
docker build -t securelife-ai .
docker run -p 8000:8000 --env-file backend/.env securelife-ai
```

## Trying it

1. Open the prospect chat and say what you're looking for, e.g. "I need to renew my car insurance". Answer its questions. Once you've given a name and a phone number or email, you show up on the broker dashboard under **New leads**.
2. In the dashboard, open the lead and click **Run qualification agent**.
3. Upload a policy PDF (any text-based policy; `backend/tests/fixtures/sample.pdf` is a tiny one), then **Run extractor agent** and **Run analysis agent**.
4. Close the lead from **Edit** with a reason: purchased, disqualified or other.

The seeded leads let you see every stage without spending tokens. Priya Nair has a finished analysis, and Karan Mehta was closed as disqualified.

## Useful commands

| Command | What it does |
|---|---|
| `uv run pytest` (in `backend/`) | Unit tests |
| `uv run python scripts/seed.py --reset` | Wipes the database and reseeds it. Needed after schema changes. |
| `uv run python scripts/e2e_smoke.py` | Calls every API endpoint against a running backend. Uses real Groq tokens. |
| `npm run gen:api` (in `frontend-broker/`) | Regenerates the typed API client from the running backend |
| `npm run typecheck` (in `frontend-broker/`) | Type check |

## Layout

```
backend/            FastAPI app
  app/agents/       the five AI agents and the Groq client
  app/prompts/      one Markdown prompt per agent
  app/services/     business rules: pipeline stages, question plans, scoring
  app/data_models/  SQLAlchemy entities
  scripts/          seed, verify_groq, e2e_smoke
frontend-broker/    broker dashboard (React)
frontend-prospect/  prospect chat (React)
docs/               ARCHITECTURE.md and diagrams
Dockerfile          one-container build (API + both front ends)
docker/             nginx config and start script for the image
```

## Common problems

| Problem | Fix |
|---|---|
| Chat says the assistant isn't configured | `GROQ_API_KEY` is missing from `backend/.env`. Add it and restart the backend. |
| "We've hit our AI usage limit" | Groq's free tier limits tokens per minute and per day for each model. Wait a minute and try again. If it keeps happening, the daily quota is used up; wait or use a paid key. |
| `seed.py` fails with `no such column` | The database is from an older schema. Run `seed.py --reset`. |
| A new chat doesn't appear on the dashboard | The prospect hasn't given both a name and a phone or email yet. Incomplete chats are hidden on purpose. |
| Extraction fails on a large PDF | Lower `GROQ_EXTRACTION_MAX_INPUT_CHARS` in `.env`. Scanned PDFs with no text layer aren't supported. |
| Document stuck in processing | Restart the backend. It marks stale jobs as failed, then you can click **Retry agent**. |

## Author

Pradumn Kumar Mishra · [mishrapradumn2014@gmail.com](mailto:mishrapradumn2014@gmail.com)
