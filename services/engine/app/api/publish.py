"""Validation gate (M2) and publish (M3)."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from ..db import session_scope
from ..models import Theme
from ..publish import validate_theme
from ..schemas import ValidationOut

router = APIRouter(tags=["publish"])


@router.get("/themes/{theme_id}/validate", response_model=ValidationOut)
def validate(theme_id: str) -> ValidationOut:
    """Run the publish validation gate against Staging. Highlights any exposed
    figure missing source_id / base_date / next_update."""
    with session_scope() as s:
        if s.get(Theme, theme_id) is None:
            raise HTTPException(404, "theme not found")
    report = validate_theme(theme_id)
    return ValidationOut(**report.to_dict())
