"""Predict API. Reads the Redis momentum cache for the Terminal overlay; the
run endpoint (re)computes it from news. Production is never mutated."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..db import session_scope
from ..models import Theme
from ..predict import compute_and_cache, load_momentum
from ..predict.fixtures import SAMPLE_NEWS

router = APIRouter(prefix="/predict", tags=["predict"])


class RunBody(BaseModel):
    # Optional news batch; defaults to the bundled sample feed.
    news: list[dict[str, Any]] | None = None


@router.post("/{theme_id}/run")
def run_predict(theme_id: str, body: RunBody | None = None) -> dict:
    """Ingest a news batch (or the sample feed), score momentum, cache to Redis.
    Normally driven by the pipeline scheduler; exposed here for dev/admin."""
    with session_scope() as s:
        if s.get(Theme, theme_id) is None:
            raise HTTPException(404, "theme not found")
    news = (body.news if body and body.news else None) or SAMPLE_NEWS
    return compute_and_cache(theme_id, news)


@router.get("/{theme_id}")
def get_predict(theme_id: str) -> dict:
    """Read the cached momentum overlay (cache-only; never touches Production)."""
    return load_momentum(theme_id)
