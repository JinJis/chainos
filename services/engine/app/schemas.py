"""API request/response DTOs (kept separate from ORM models)."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


# ── Themes ────────────────────────────────────────────────────────────────────
class ThemeCreate(BaseModel):
    name: str
    depth_max: int = 3
    model_assignment: dict[str, str] = Field(default_factory=dict)
    seed_tickers: list[str] = Field(default_factory=list)
    context_notes: str | None = None


class ThemeOut(BaseModel):
    id: str
    name: str
    depth_max: int
    status: str
    version: int
    model_assignment: dict[str, str]
    seed_tickers: list[str]
    context_notes: str | None
    published_at: datetime | None
    created_at: datetime
    staging_counts: dict[str, int] = Field(default_factory=dict)
    production_counts: dict[str, int] = Field(default_factory=dict)
    open_tickets: int = 0

    class Config:
        from_attributes = True


# ── Jobs / events ─────────────────────────────────────────────────────────────
class JobEventOut(BaseModel):
    seq: int
    kind: str
    message: str
    data: dict[str, Any] | None = None
    created_at: datetime

    class Config:
        from_attributes = True


# ── Tickets ───────────────────────────────────────────────────────────────────
class TicketOut(BaseModel):
    id: str
    theme_id: str
    metric: str
    target_ref: str
    reason: str
    priority: int
    status: str
    created_at: datetime
    resolved_at: datetime | None = None
    payload: dict[str, Any] = Field(default_factory=dict)
    locked_value: float | None = None
    source_count: int = 0

    class Config:
        from_attributes = True


class SourceCreate(BaseModel):
    type: str = "filing"
    publisher: str = ""
    url: str = ""
    as_of_date: str = ""
    confidence: str = "verified"
    content_text: str | None = None


class SourceOut(BaseModel):
    id: str
    type: str
    publisher: str
    url: str
    as_of_date: str
    confidence: str
    filename: str | None
    verified: bool
    created_at: datetime

    class Config:
        from_attributes = True


# ── Verification loop (M2) ────────────────────────────────────────────────────
class ParsePreview(BaseModel):
    field: str
    value: float | None
    span: str
    extracted_by: str
    confidence: str
    found: bool
    source_id: str | None = None


class ApproveBody(BaseModel):
    # Optional admin override of the parsed value.
    value: float | None = None


class ValidationOut(BaseModel):
    ok: bool
    total: int
    passed: int
    failed: int
    failures: list[dict[str, Any]]


# ── Graph editor (M2) ─────────────────────────────────────────────────────────
class EdgeEdit(BaseModel):
    """Manual edit of a staged edge (confidence toggle / value correction)."""

    type: str
    from_id: str = Field(alias="from")
    to_id: str = Field(alias="to")
    product_ref: str | None = None
    updates: dict[str, Any]

    class Config:
        populate_by_name = True
