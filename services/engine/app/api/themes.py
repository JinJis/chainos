"""Theme CRUD."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from sqlalchemy import select

from ..db import session_scope
from ..graph import ProductionGraphRepo, StagingGraphRepo
from ..logging_config import get_logger
from ..models import Theme
from ..schemas import ThemeCreate, ThemeOut, ThemeUpdate

router = APIRouter(prefix="/themes", tags=["themes"])
log = get_logger("api.themes")


def _to_out(theme: Theme, *, with_counts: bool = True) -> ThemeOut:
    out = ThemeOut.model_validate(theme)
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
            research_report=body.research_report,
            status="draft",
        )
        s.add(theme)
        s.flush()
        out = _to_out(theme)
    log.info("theme created", extra={"theme_id": out.id, "theme_name": out.name})
    return out


@router.patch("/{theme_id}", response_model=ThemeOut)
def update_theme(theme_id: str, body: ThemeUpdate) -> ThemeOut:
    log.info("update theme", extra={"theme_id": theme_id})
    with session_scope() as s:
        theme = s.get(Theme, theme_id)
        if theme is None:
            log.warning("update_theme: not found", extra={"theme_id": theme_id})
            raise HTTPException(404, "theme not found")
        if body.research_report is not None:
            theme.research_report = body.research_report
        s.flush()
        out = _to_out(theme)
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
