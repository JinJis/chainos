"""Theme CRUD."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from sqlalchemy import select

from ..agent.prompts import research_brief
from ..db import session_scope
from ..graph import ProductionGraphRepo, StagingGraphRepo
from ..logging_config import get_logger
from ..models import Theme
from ..schemas import (
    ResearchBriefOut,
    ResearchOut,
    ResearchUpdate,
    ThemeCreate,
    ThemeOut,
)

router = APIRouter(prefix="/themes", tags=["themes"])
log = get_logger("api.themes")


def _to_out(theme: Theme, *, with_counts: bool = True) -> ThemeOut:
    out = ThemeOut.model_validate(theme)
    out.research_chars = len(theme.research_report or "")
    if with_counts:
        out.staging_counts = StagingGraphRepo().count(theme.id)
        out.production_counts = ProductionGraphRepo().count(theme.id)
        out.open_tickets = sum(1 for t in theme.tickets if t.status == "open")
    return out


@router.post("", response_model=ThemeOut)
def create_theme(body: ThemeCreate) -> ThemeOut:
    log.info(
        "create theme",
        extra={"theme_name": body.name, "depth": body.depth_max, "models": body.model_assignment},
    )
    with session_scope() as s:
        theme = Theme(
            name=body.name,
            depth_max=body.depth_max,
            model_assignment=body.model_assignment,
            seed_tickers=body.seed_tickers,
            context_notes=body.context_notes,
            status="draft",
        )
        s.add(theme)
        s.flush()
        out = _to_out(theme)
    log.info("theme created", extra={"theme_id": out.id, "theme_name": out.name})
    return out


@router.get("", response_model=list[ThemeOut])
def list_themes() -> list[ThemeOut]:
    with session_scope() as s:
        themes = s.scalars(select(Theme).order_by(Theme.created_at.desc())).all()
        log.debug("list themes", extra={"count": len(themes)})
        return [_to_out(t) for t in themes]


@router.get("/{theme_id}", response_model=ThemeOut)
def get_theme(theme_id: str) -> ThemeOut:
    with session_scope() as s:
        theme = s.get(Theme, theme_id)
        if theme is None:
            log.warning("get_theme: not found", extra={"theme_id": theme_id})
            raise HTTPException(404, "theme not found")
        log.debug("get_theme", extra={"theme_id": theme_id, "status": theme.status})
        return _to_out(theme)


# ── Research document (paste the Gemini Deep Research output here) ────────────
@router.get("/{theme_id}/research/brief", response_model=ResearchBriefOut)
def get_research_brief(theme_id: str) -> ResearchBriefOut:
    """The ready-to-use research prompt. Copy it into the Gemini Deep Research UI,
    run it, then paste the result back via PUT /themes/{id}/research."""
    with session_scope() as s:
        theme = s.get(Theme, theme_id)
        if theme is None:
            raise HTTPException(404, "theme not found")
        brief = research_brief(theme.name, theme.depth_max, theme.seed_tickers or [])
        return ResearchBriefOut(brief=brief)


@router.get("/{theme_id}/research", response_model=ResearchOut)
def get_research(theme_id: str) -> ResearchOut:
    with session_scope() as s:
        theme = s.get(Theme, theme_id)
        if theme is None:
            raise HTTPException(404, "theme not found")
        report = theme.research_report or ""
        return ResearchOut(report=report, chars=len(report))


@router.put("/{theme_id}/research", response_model=ResearchOut)
def put_research(theme_id: str, body: ResearchUpdate) -> ResearchOut:
    """Save the admin-provided research document (from the Gemini Deep Research UI)."""
    with session_scope() as s:
        theme = s.get(Theme, theme_id)
        if theme is None:
            log.warning("put_research: theme not found", extra={"theme_id": theme_id})
            raise HTTPException(404, "theme not found")
        theme.research_report = body.report
        log.info("research document saved", extra={"theme_id": theme_id, "chars": len(body.report)})
        return ResearchOut(report=body.report, chars=len(body.report))


@router.delete("/{theme_id}")
def delete_theme(theme_id: str) -> dict[str, str]:
    log.info("delete theme", extra={"theme_id": theme_id})
    with session_scope() as s:
        theme = s.get(Theme, theme_id)
        if theme is None:
            log.warning("delete_theme: not found", extra={"theme_id": theme_id})
            raise HTTPException(404, "theme not found")
        s.delete(theme)
    StagingGraphRepo().clear_theme(theme_id)
    ProductionGraphRepo().clear_theme(theme_id)
    log.info("theme deleted (staging + production cleared)", extra={"theme_id": theme_id})
    return {"status": "deleted", "id": theme_id}
