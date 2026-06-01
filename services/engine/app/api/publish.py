"""Validation gate (M2) and publish (M3)."""
from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException

from ..db import session_scope
from ..models import Theme
from ..publish import PublishBlocked, diff_theme, publish_graph, validate_theme
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


@router.get("/themes/{theme_id}/publish/diff")
def publish_diff(theme_id: str) -> dict:
    """Preview what Publish would change in Production."""
    with session_scope() as s:
        if s.get(Theme, theme_id) is None:
            raise HTTPException(404, "theme not found")
    return diff_theme(theme_id)


@router.post("/themes/{theme_id}/publish")
def publish(theme_id: str) -> dict:
    """Explicit admin action: validate Staging, then atomically snapshot it into
    the read-only Production DB the Terminal consumes. Blocks on gate failure."""
    with session_scope() as s:
        theme = s.get(Theme, theme_id)
        if theme is None:
            raise HTTPException(404, "theme not found")
        try:
            result = publish_graph(theme_id)
        except PublishBlocked as exc:
            # 409: cannot publish — surface the unmet items.
            raise HTTPException(409, detail=exc.report.to_dict()) from exc
        theme.version += 1
        theme.status = "published"
        theme.published_at = datetime.now(UTC)
        version = theme.version
    return {
        "status": "published",
        "version": version,
        "production_counts": result.counts,
        "verified_figures": result.report.passed,
    }
