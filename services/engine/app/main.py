"""Chainos Engine FastAPI app. M0 exposes health + an LLM-router probe; later
milestones mount the agent, tickets, publish, and Production read routers."""
from __future__ import annotations

import time
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exception_handlers import (
    http_exception_handler,
    request_validation_exception_handler,
)
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from starlette.exceptions import HTTPException as StarletteHTTPException

from . import __version__
from .api import agent as agent_api
from .api import editor as editor_api
from .api import predict as predict_api
from .api import publish as publish_api
from .api import terminal as terminal_api
from .api import themes as themes_api
from .api import tickets as tickets_api
from .config import get_settings
from .llm import Tier, get_router
from .logging_config import configure_logging, get_logger

# Configure logging at import so alembic/seed/uvicorn all share the format.
_settings = get_settings()
configure_logging(_settings.log_level, _settings.log_format)
log = get_logger("api")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Re-apply after uvicorn sets up its own logging so our config wins.
    configure_logging(_settings.log_level, _settings.log_format)
    log.info(
        "engine starting",
        extra={
            "version": __version__,
            "llm_mode": "offline" if _settings.offline else "live",
            "log_level": _settings.log_level.upper(),
        },
    )
    # Best-effort table creation so the API is usable immediately in dev.
    try:
        from .db.init import init_db

        init_db()
        log.debug("relational tables ensured")
    except Exception:  # noqa: BLE001 — Postgres may not be up yet; routes still import
        log.warning("init_db skipped (datastore not ready yet)", exc_info=True)
    yield
    log.info("engine shutting down")


app = FastAPI(title="Chainos Engine", version=__version__, lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:3001"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def log_requests(request: Request, call_next):
    start = time.perf_counter()
    log.debug("→ request", extra={"method": request.method, "path": request.url.path})
    try:
        response = await call_next(request)
    except Exception:
        log.exception(
            "unhandled request error",
            extra={"method": request.method, "path": request.url.path},
        )
        raise
    duration_ms = round((time.perf_counter() - start) * 1000, 1)
    status = response.status_code
    # /health is polled by Docker (DEBUG); 4xx → WARNING, 5xx → ERROR so failures stand out.
    if request.url.path == "/health":
        emit = log.debug
    elif status >= 500:
        emit = log.error
    elif status >= 400:
        emit = log.warning
    else:
        emit = log.info
    emit(
        "← response",
        extra={"method": request.method, "path": request.url.path, "status": status, "ms": duration_ms},
    )
    return response


@app.exception_handler(StarletteHTTPException)
async def _log_http_exception(request: Request, exc: StarletteHTTPException):
    """Log the REASON behind every 4xx/5xx (e.g. 'theme not found') so the cause
    of a failing request is visible, not just the status code."""
    emit = log.error if exc.status_code >= 500 else log.warning
    emit(
        "http error",
        extra={
            "method": request.method,
            "path": request.url.path,
            "status": exc.status_code,
            "detail": exc.detail,
        },
    )
    return await http_exception_handler(request, exc)


@app.exception_handler(RequestValidationError)
async def _log_validation_error(request: Request, exc: RequestValidationError):
    log.warning(
        "request validation failed",
        extra={"method": request.method, "path": request.url.path, "errors": exc.errors()},
    )
    return await request_validation_exception_handler(request, exc)


app.include_router(themes_api.router)
app.include_router(agent_api.router)
app.include_router(tickets_api.router)
app.include_router(editor_api.router)
app.include_router(publish_api.router)
app.include_router(terminal_api.router)
app.include_router(predict_api.router)


@app.get("/health")
def health() -> dict[str, Any]:
    s = get_settings()
    return {
        "status": "ok",
        "version": __version__,
        "llm_mode": "offline" if s.offline else "live",
        "default_provider": s.llm_default_provider,
    }


class RouterProbe(BaseModel):
    tier: Tier = Tier.LOW
    prompt: str = "Say hello to Chainos."


@app.post("/debug/llm")
def debug_llm(body: RouterProbe) -> dict[str, Any]:
    """Probe the router end-to-end (offline by default). Never exposes keys."""
    resp = get_router().prompt(body.tier, body.prompt)
    return {"model": resp.model, "tier": resp.tier, "text": resp.text}
