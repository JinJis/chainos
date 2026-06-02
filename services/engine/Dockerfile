# Chainos Engine — FastAPI + LangGraph. Build context: services/engine
FROM python:3.11-slim AS base

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    UV_LINK_MODE=copy \
    PATH="/app/.venv/bin:$PATH"

WORKDIR /app
RUN pip install --no-cache-dir uv

# Dependency layer (cached unless pyproject/lock change).
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

# App source (generated.py is checked in, so no Node build step is needed).
COPY app ./app
COPY migrations ./migrations
COPY alembic.ini ./

EXPOSE 8000

# Run migrations, then serve. Datastores are awaited via compose healthchecks.
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000"]
