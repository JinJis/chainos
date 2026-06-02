"""Agent run (streamed) + job event history + staging-graph inspection."""
from __future__ import annotations

import asyncio
import json
import logging
import threading
from collections.abc import AsyncIterator
from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import select

from ..agent import run_agent
from ..agent.loop import AgentEvent
from ..db import get_session, session_scope
from ..graph import StagingGraphRepo
from ..graph_schema import FLOW_VIEW_EDGES
from ..logging_config import _extras, get_logger
from ..models import Job, JobEvent, NeedFactTicket, Theme
from ..schemas import JobEventOut

router = APIRouter(tags=["agent"])
log = get_logger("api.agent")

# Send an SSE keep-alive comment if no agent event arrives within this window, so
# the Studio proxy (undici) doesn't abort the stream during a long research step.
_HEARTBEAT_S = 15.0


def _sse(payload: dict) -> str:
    return f"data: {json.dumps(payload)}\n\n"


# Only these loggers reach the Studio console — the agent's own reasoning (LLM
# prompts/responses, graph writes, publish). API request logs (health checks, Studio
# polling) and DB connection noise are intentionally excluded.
_CONSOLE_LOGGERS = (
    "chainos.agent",
    "chainos.llm",
    "chainos.graph",
    "chainos.publish",
    "chainos.predict",
)


class _SSELogHandler(logging.Handler):
    """Buffers agent-related `chainos.*` log records during a run so the run endpoint
    can drain them into the SSE stream — surfacing the Engine's reasoning/debug
    logging directly in the Studio console. Records are filtered by the chainos
    logger's own level (DEBUG when LOG_LEVEL=DEBUG), so verbosity follows .env.
    Thread-safe: produced on the worker thread, drained on the event loop."""

    def __init__(self) -> None:
        super().__init__(level=logging.NOTSET)
        self._buffer: list[dict] = []
        self._lock = threading.Lock()

    def emit(self, record: logging.LogRecord) -> None:
        if not record.name.startswith(_CONSOLE_LOGGERS):
            return  # skip request/health/db plumbing — keep the console to agent logs
        try:
            message = record.getMessage()
            extras = _extras(record)
            if extras:
                message += "  " + " ".join(f"{k}={v}" for k, v in extras.items())
            if record.exc_info:
                message += "\n" + logging.Formatter().formatException(record.exc_info)
            with self._lock:
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
        with self._lock:
            out, self._buffer = self._buffer, []
        return out


@router.post("/themes/{theme_id}/run")
async def run_theme_agent(theme_id: str) -> StreamingResponse:
    """Run the multi-LLM agent loop and stream its thinking trace as SSE.
    Persists every event (replayable) and the Need-Fact tickets it raises."""
    log.info("run agent requested", extra={"theme_id": theme_id})
    with session_scope() as s:
        theme = s.get(Theme, theme_id)
        if theme is None:
            log.warning("run agent: theme not found", extra={"theme_id": theme_id})
            raise HTTPException(404, "theme not found")
        theme.status = "building"
        job = Job(theme_id=theme_id, kind="agent_run", status="running")
        s.add(job)
        s.flush()
        job_id = job.id
        name = theme.name
        depth = theme.depth_max
        providers = dict(theme.model_assignment or {})
        research_report = theme.research_report or ""

    async def event_stream() -> AsyncIterator[str]:
        session = get_session()
        capture = _SSELogHandler()
        chainos_logger = logging.getLogger("chainos")
        chainos_logger.addHandler(capture)
        loop = asyncio.get_running_loop()
        queue: asyncio.Queue = asyncio.Queue()
        sentinel = object()

        # The agent does blocking LLM/Neo4j work (Deep Research can take minutes), so
        # it runs in a worker THREAD and pushes events back to the event loop. This
        # keeps the server responsive and lets research thoughts stream live.
        def emit(ev: AgentEvent) -> None:
            loop.call_soon_threadsafe(queue.put_nowait, ev)

        def worker() -> None:
            try:
                run_agent(
                    theme_id=theme_id,
                    theme_name=name,
                    depth_max=depth,
                    providers=providers,
                    emit=emit,
                    research_report=research_report,
                )
            except Exception as exc:  # safety net — run_agent emits its own errors too
                log.exception("agent worker crashed", extra={"job_id": job_id, "theme_id": theme_id})
                loop.call_soon_threadsafe(
                    queue.put_nowait,
                    AgentEvent(-1, "error", f"{type(exc).__name__}: {exc}"),
                )
            finally:
                loop.call_soon_threadsafe(queue.put_nowait, sentinel)

        fut = loop.run_in_executor(None, worker)
        log.info("agent stream opened", extra={"job_id": job_id, "theme_id": theme_id})
        try:
            yield _sse({"kind": "job", "job_id": job_id, "message": f"job {job_id} started"})
            while True:
                # Heartbeat: if no event arrives within the window, send an SSE comment
                # so the Studio proxy's body timeout never fires during long research.
                try:
                    ev = await asyncio.wait_for(queue.get(), timeout=_HEARTBEAT_S)
                except TimeoutError:
                    for entry in capture.drain():
                        yield _sse(entry)
                    yield ": keepalive\n\n"
                    continue
                # Flush any engine log lines produced while this step ran.
                for entry in capture.drain():
                    yield _sse(entry)
                if ev is sentinel:
                    break
                # Persist real step events (skip ephemeral streamed research thoughts).
                if not ev.ephemeral:
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
                elif ev.kind == "error":
                    job = session.get(Job, job_id)
                    if job:
                        job.status = "error"
                        job.error = ev.message
                session.commit()
                yield _sse(
                    {"seq": ev.seq, "kind": ev.kind, "message": ev.message, "data": ev.data}
                )
            for entry in capture.drain():  # tail
                yield _sse(entry)
        finally:
            await fut
            chainos_logger.removeHandler(capture)
            session.close()

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@router.get("/jobs/{job_id}/events", response_model=list[JobEventOut])
def job_events(job_id: str) -> list[JobEventOut]:
    with session_scope() as s:
        events = s.scalars(
            select(JobEvent).where(JobEvent.job_id == job_id).order_by(JobEvent.seq)
        ).all()
        log.debug("job events", extra={"job_id": job_id, "count": len(events)})
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
    graph = StagingGraphRepo().get_graph(theme_id, depth=depth, edge_types=edge_types)
    log.debug(
        "staging graph",
        extra={"theme_id": theme_id, "depth": depth,
               "nodes": len(graph["nodes"]), "edges": len(graph["edges"])},
    )
    return graph
