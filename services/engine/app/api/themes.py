"""Theme CRUD."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from sqlalchemy import select

from ..db import session_scope
from ..graph import ProductionGraphRepo, StagingGraphRepo
from ..models import Theme
from ..schemas import ThemeCreate, ThemeOut

router = APIRouter(prefix="/themes", tags=["themes"])


def _to_out(theme: Theme, *, with_counts: bool = True) -> ThemeOut:
    out = ThemeOut.model_validate(theme)
    if with_counts:
        out.staging_counts = StagingGraphRepo().count(theme.id)
        out.production_counts = ProductionGraphRepo().count(theme.id)
        out.open_tickets = sum(1 for t in theme.tickets if t.status == "open")
    return out


@router.post("", response_model=ThemeOut)
def create_theme(body: ThemeCreate) -> ThemeOut:
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
        return _to_out(theme)


@router.get("", response_model=list[ThemeOut])
def list_themes() -> list[ThemeOut]:
    with session_scope() as s:
        themes = s.scalars(select(Theme).order_by(Theme.created_at.desc())).all()
        return [_to_out(t) for t in themes]


@router.get("/{theme_id}", response_model=ThemeOut)
def get_theme(theme_id: str) -> ThemeOut:
    with session_scope() as s:
        theme = s.get(Theme, theme_id)
        if theme is None:
            raise HTTPException(404, "theme not found")
        return _to_out(theme)


@router.delete("/{theme_id}")
def delete_theme(theme_id: str) -> dict[str, str]:
    with session_scope() as s:
        theme = s.get(Theme, theme_id)
        if theme is None:
            raise HTTPException(404, "theme not found")
        s.delete(theme)
    StagingGraphRepo().clear_theme(theme_id)
    ProductionGraphRepo().clear_theme(theme_id)
    return {"status": "deleted", "id": theme_id}
