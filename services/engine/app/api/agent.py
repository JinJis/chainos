"""Agent run (streamed) + job event history + staging-graph inspection."""
from __future__ import annotations

import json
from collections.abc import AsyncIterator
from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import select

from ..agent import run_agent
from ..db import get_session, session_scope
from ..graph import StagingGraphRepo
from ..graph_schema import FLOW_VIEW_EDGES
from ..models import Job, JobEvent, NeedFactTicket, Theme
from ..schemas import JobEventOut

router = APIRouter(tags=["agent"])


def _sse(payload: dict) -> str:
    return f"data: {json.dumps(payload)}\n\n"


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
        try:
            yield _sse({"kind": "job", "job_id": job_id, "message": f"job {job_id} started"})
            for ev in run_agent(
                theme_id=theme_id,
                theme_name=name,
                depth_max=depth,
                providers=providers,
            ):
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
        except Exception as exc:  # noqa: BLE001
            job = session.get(Job, job_id)
            if job:
                job.status = "error"
                job.error = str(exc)
            session.commit()
            yield _sse({"kind": "error", "message": str(exc)})
        finally:
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
