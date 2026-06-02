"""Studio graph editor + source manager (manual staging edits, confidence toggle)."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from sqlalchemy import select

from ..db import session_scope
from ..graph import StagingGraphRepo
from ..logging_config import get_logger
from ..models import Source, Theme
from ..schemas import EdgeEdit, SourceOut

router = APIRouter(tags=["editor"])
log = get_logger("api.editor")


@router.get("/themes/{theme_id}/sources", response_model=list[SourceOut])
def list_sources(theme_id: str) -> list[SourceOut]:
    with session_scope() as s:
        rows = s.scalars(
            select(Source).where(Source.theme_id == theme_id).order_by(Source.created_at.desc())
        ).all()
        log.debug("list sources", extra={"theme_id": theme_id, "count": len(rows)})
        return [SourceOut.model_validate(r) for r in rows]


@router.post("/themes/{theme_id}/edges/edit")
def edit_edge(theme_id: str, body: EdgeEdit) -> dict:
    """Apply a manual edit to a staged edge (e.g. flip confidence, correct a value)."""
    log.info(
        "edit edge",
        extra={"theme_id": theme_id, "type": body.type, "from": body.from_id,
               "to": body.to_id, "updates": body.updates},
    )
    with session_scope() as s:
        if s.get(Theme, theme_id) is None:
            log.warning("edit_edge: theme not found", extra={"theme_id": theme_id})
            raise HTTPException(404, "theme not found")
    payload = {
        "type": body.type,
        "from": body.from_id,
        "to": body.to_id,
        "product_ref": body.product_ref,
    }
    updated = StagingGraphRepo().lock_edge(theme_id, payload, body.updates)
    if not updated:
        log.warning("edit_edge: no matching staged edge",
                    extra={"theme_id": theme_id, "from": body.from_id, "to": body.to_id})
        raise HTTPException(404, "no matching staged edge")
    log.info("edge updated", extra={"theme_id": theme_id, "updated": updated})
    return {"updated": updated}
