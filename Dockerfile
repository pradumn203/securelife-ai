# syntax=docker/dockerfile:1
#
# SecureLife AI as one container on port 8000:
#   /broker/ broker dashboard      (static, served by nginx)
#   /chat/   prospect chat         (static, served by nginx)
#   /api/    FastAPI backend       (uvicorn, proxied by nginx)
#
# Build:  docker build -t securelife-ai .
# Run:    docker compose up --build      (reads backend/.env if present)
#    or:  docker run -p 8000:8000 --env-file backend/.env securelife-ai

ARG NODE_VERSION=24
ARG PYTHON_VERSION=3.13

# --- 1. Frontends -------------------------------------------------------------
FROM node:${NODE_VERSION}-alpine AS frontends
WORKDIR /build

# Dependencies first, so source edits don't bust the npm cache layer.
COPY frontend-broker/package.json frontend-broker/package-lock.json frontend-broker/.npmrc frontend-broker/
COPY frontend-prospect/package.json frontend-prospect/package-lock.json frontend-prospect/.npmrc frontend-prospect/
RUN npm ci --prefix frontend-broker && npm ci --prefix frontend-prospect

COPY frontend-broker/ frontend-broker/
COPY frontend-prospect/ frontend-prospect/
# Same origin as the API, so both apps call relative /api paths.
ENV VITE_API_BASE_URL=""
RUN npm run build --prefix frontend-broker -- --base=/broker/ \
 && npm run build --prefix frontend-prospect -- --base=/chat/

# --- 2. Python dependencies ---------------------------------------------------
FROM python:${PYTHON_VERSION}-slim AS backend-deps
COPY --from=ghcr.io/astral-sh/uv:0.13 /uv /bin/uv
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    UV_PROJECT_ENVIRONMENT=/app/backend/.venv
WORKDIR /app/backend
COPY backend/pyproject.toml backend/uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

# --- 3. Runtime ---------------------------------------------------------------
FROM python:${PYTHON_VERSION}-slim AS runtime

RUN apt-get update \
 && apt-get install -y --no-install-recommends nginx \
 && rm -rf /var/lib/apt/lists/*

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/app/backend/.venv/bin:$PATH" \
    DATABASE_URL=sqlite+aiosqlite:///./data/securelife.db \
    UPLOAD_DIR=./data/uploads

RUN groupadd --system --gid 10001 securelife \
 && useradd --system --uid 10001 --gid securelife --home-dir /app --shell /usr/sbin/nologin securelife

WORKDIR /app/backend
COPY --from=backend-deps /app/backend/.venv .venv
COPY backend/app app
COPY backend/scripts scripts
COPY --from=frontends /build/frontend-broker/dist /app/static/broker
COPY --from=frontends /build/frontend-prospect/dist /app/static/chat
COPY docker/nginx.conf /app/nginx.conf
COPY docker/start.sh /app/start.sh
# Strip Windows line endings in case the repo was checked out with CRLF.
RUN sed -i 's/\r$//' /app/start.sh && chmod +x /app/start.sh

# SQLite file and uploaded PDFs. The default paths in backend/.env
# (./data/...) resolve here too, so an env file from local dev just works.
# start.sh resets this to the demo data on every start.
RUN mkdir -p data/uploads && chown -R securelife:securelife data

USER securelife
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/health', timeout=4)"]

CMD ["/app/start.sh"]
