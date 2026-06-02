"""Agent run (streamed) + job event history + staging-graph inspection."""
from __future__ import annotations

import json
import logging
from collections.abc import AsyncIterator
from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import select

from ..agent import run_agent
from ..db import get_session, session_scope
from ..graph import StagingGraphRepo
from ..graph_schema import FLOW_VIEW_EDGES
from ..logging_config import _extras, get_logger
from ..models import Job, JobEvent, NeedFactTicket, Theme
from ..schemas import JobEventOut

router = APIRouter(tags=["agent"])
log = get_logger("api.agent")


def _sse(payload: dict) -> str:
    return f"data: {json.dumps(payload)}\n\n"


class _SSELogHandler(logging.Handler):
    """Buffers `chainos.*` log records during an agent run so the run endpoint can
    drain them into the SSE stream — surfacing the Engine's debug/error logging
    directly in the Studio console. Records are filtered by the chainos logger's
    own level (DEBUG when LOG_LEVEL=DEBUG), so verbosity follows .env."""

    def __init__(self) -> None:
        super().__init__(level=logging.NOTSET)
        self._buffer: list[dict] = []

    def emit(self, record: logging.LogRecord) -> None:
        try:
            message = record.getMessage()
            extras = _extras(record)
            if extras:
                message += "  " + " ".join(f"{k}={v}" for k, v in extras.items())
            if record.exc_info:
                message += "\n" + logging.Formatter().formatException(record.exc_info)
            self._buffer.append(
                {
                    "kind": "log",
                    "level": record.levelname,
                    "logger": record.name,
                    "message": message,
                }
            )
        except Exception:  # never let logging break the stream
            pass

    def drain(self) -> list[dict]:
        out, self._buffer = self._buffer, []
        return out


@router.post("/themes/{theme_id}/run")
async def run_theme_agent(theme_id: str) -> StreamingResponse:
    """Run the multi-LLM agent loop and stream its thinking trace as SSE.
    Persists every event (replayable) and the Need-Fact tickets it raises."""
    with session_scope() as s:
        theme = s.get(Theme, theme_id)
        if theme is None:
            raise HTTPException(404, "theme not found")
        theme.status = "building"
        job = Job(theme_id=theme_id, kind="agent_run", status="running")
        s.add(job)
        s.flush()
        job_id = job.id
        name = theme.name
        depth = theme.depth_max
        providers = dict(theme.model_assignment or {})

    async def event_stream() -> AsyncIterator[str]:
        session = get_session()
        capture = _SSELogHandler()
        chainos_logger = logging.getLogger("chainos")
        chainos_logger.addHandler(capture)
        log.info("agent stream opened", extra={"job_id": job_id, "theme_id": theme_id})
        try:
            yield _sse({"kind": "job", "job_id": job_id, "message": f"job {job_id} started"})
            for ev in run_agent(
                theme_id=theme_id,
                theme_name=name,
                depth_max=depth,
                providers=providers,
            ):
                # Flush any engine log lines produced while this step ran.
                for entry in capture.drain():
                    yield _sse(entry)
                session.add(
                    JobEvent(
                        job_id=job_id,
                        seq=ev.seq,
                        kind=ev.kind,
                        message=ev.message,
                        data=ev.data or None,
                    )
                )
                if ev.kind == "done":
                    for spec in ev.data.get("tickets", []):
                        session.add(NeedFactTicket(theme_id=theme_id, **spec))
                    job = session.get(Job, job_id)
                    if job:
                        job.status = "done"
                        job.finished_at = datetime.now(UTC)
                    theme = session.get(Theme, theme_id)
                    if theme:
                        theme.status = "staged"
                session.commit()
                yield _sse({"seq": ev.seq, "kind": ev.kind, "message": ev.message, "data": ev.data})
            for entry in capture.drain():  # tail
                yield _sse(entry)
        except Exception as exc:  # noqa: BLE001
            log.exception("agent stream FAILED", extra={"job_id": job_id, "theme_id": theme_id})
            for entry in capture.drain():  # include the captured traceback
                yield _sse(entry)
            job = session.get(Job, job_id)
            if job:
                job.status = "error"
                job.error = str(exc)
            session.commit()
            yield _sse({"kind": "error", "message": f"{type(exc).__name__}: {exc}"})
        finally:
            chainos_logger.removeHandler(capture)
            session.close()

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@router.get("/jobs/{job_id}/events", response_model=list[JobEventOut])
def job_events(job_id: str) -> list[JobEventOut]:
    with session_scope() as s:
        events = s.scalars(
            select(JobEvent).where(JobEvent.job_id == job_id).order_by(JobEvent.seq)
        ).all()
        return [JobEventOut.model_validate(e) for e in events]


@router.get("/themes/{theme_id}/staging-graph")
def staging_graph(
    theme_id: str,
    depth: int | None = Query(default=None),
    views: list[str] | None = Query(default=None),
) -> dict:
    """The draft graph as it stands in Staging — for the Studio editor/preview."""
    edge_types: list[str] | None = None
    if views:
        edge_types = sorted({et for v in views for et in FLOW_VIEW_EDGES.get(v, [])})
    return StagingGraphRepo().get_graph(theme_id, depth=depth, edge_types=edge_types)
