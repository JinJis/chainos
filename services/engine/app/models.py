"""Relational models (Postgres): theme metadata, agent jobs + event log,
Need-Fact tickets, and uploaded sources. The knowledge graph itself lives in
Neo4j; these tables hold workflow/job state and evidence metadata."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import JSON, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db.base import Base, IdMixin, TimestampMixin

# Workflow status values kept as plain strings (portable, readable in the DB).
THEME_STATUSES = ("draft", "building", "staged", "published")
JOB_STATUSES = ("running", "done", "error")
TICKET_STATUSES = ("open", "resolved")


class Theme(IdMixin, TimestampMixin, Base):
    __tablename__ = "themes"

    name: Mapped[str] = mapped_column(String(200))
    depth_max: Mapped[int] = mapped_column(Integer, default=3)
    status: Mapped[str] = mapped_column(String(20), default="draft")
    version: Mapped[int] = mapped_column(Integer, default=0)
    # tier -> provider ("anthropic" | "google"), e.g. {"DEEP": "google", ...}
    model_assignment: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    seed_tickers: Mapped[list[str]] = mapped_column(JSON, default=list)
    context_notes: Mapped[str | None] = mapped_column(Text, default=None)
    # Admin-pasted research output (e.g. from the Gemini Deep Research UI). The agent
    # structures THIS into the graph instead of calling a research API itself.
    research_report: Mapped[str | None] = mapped_column(Text, default=None)
    published_at: Mapped[datetime | None] = mapped_column(default=None)

    jobs: Mapped[list[Job]] = relationship(back_populates="theme", cascade="all, delete-orphan")
    tickets: Mapped[list[NeedFactTicket]] = relationship(
        back_populates="theme", cascade="all, delete-orphan"
    )


class Job(IdMixin, TimestampMixin, Base):
    __tablename__ = "jobs"

    theme_id: Mapped[str] = mapped_column(ForeignKey("themes.id", ondelete="CASCADE"))
    kind: Mapped[str] = mapped_column(String(40), default="agent_run")
    status: Mapped[str] = mapped_column(String(20), default="running")
    error: Mapped[str | None] = mapped_column(Text, default=None)
    finished_at: Mapped[datetime | None] = mapped_column(default=None)

    theme: Mapped[Theme] = relationship(back_populates="jobs")
    events: Mapped[list[JobEvent]] = relationship(
        back_populates="job", cascade="all, delete-orphan", order_by="JobEvent.seq"
    )


class JobEvent(IdMixin, TimestampMixin, Base):
    """One line of the agent's thinking trace — replayable into the Studio console."""

    __tablename__ = "job_events"

    job_id: Mapped[str] = mapped_column(ForeignKey("jobs.id", ondelete="CASCADE"))
    seq: Mapped[int] = mapped_column(Integer)
    kind: Mapped[str] = mapped_column(String(40))  # research|deep|persist|ticket|done|error
    message: Mapped[str] = mapped_column(Text)
    data: Mapped[dict[str, Any] | None] = mapped_column(JSON, default=None)

    job: Mapped[Job] = relationship(back_populates="events")


class NeedFactTicket(IdMixin, TimestampMixin, Base):
    """Agent → Admin pull request for a missing authoritative figure (PRD §6.2 Step 3)."""

    __tablename__ = "need_fact_tickets"

    theme_id: Mapped[str] = mapped_column(ForeignKey("themes.id", ondelete="CASCADE"))
    metric: Mapped[str] = mapped_column(String(200))  # WHAT
    target_ref: Mapped[str] = mapped_column(String(200))  # WHERE (node/edge)
    reason: Mapped[str] = mapped_column(Text)  # WHY
    priority: Mapped[int] = mapped_column(Integer, default=2)
    status: Mapped[str] = mapped_column(String(20), default="open")
    resolved_at: Mapped[datetime | None] = mapped_column(default=None)
    # Structured locator the verification loop uses to find + lock the target in
    # Staging: {kind: edge|node, type, from, to, product_ref, field, label, node_id}.
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    # Value written back once an admin uploads evidence and the parse is approved.
    locked_value: Mapped[float | None] = mapped_column(default=None)

    theme: Mapped[Theme] = relationship(back_populates="tickets")
    sources: Mapped[list[Source]] = relationship(back_populates="ticket")


class Source(IdMixin, TimestampMixin, Base):
    """Evidence metadata. The number extracted from it is written into Neo4j with a
    SOURCED_FROM link back to this row's id."""

    __tablename__ = "sources"

    theme_id: Mapped[str] = mapped_column(ForeignKey("themes.id", ondelete="CASCADE"))
    ticket_id: Mapped[str | None] = mapped_column(
        ForeignKey("need_fact_tickets.id", ondelete="SET NULL"), default=None
    )
    type: Mapped[str] = mapped_column(String(20), default="filing")  # filing|IR|report|news
    publisher: Mapped[str] = mapped_column(String(200), default="")
    url: Mapped[str] = mapped_column(String(500), default="")
    as_of_date: Mapped[str] = mapped_column(String(80), default="")
    confidence: Mapped[str] = mapped_column(String(20), default="verified")
    filename: Mapped[str | None] = mapped_column(String(300), default=None)
    content_text: Mapped[str | None] = mapped_column(Text, default=None)
    verified: Mapped[bool] = mapped_column(default=False)

    ticket: Mapped[NeedFactTicket | None] = relationship(back_populates="sources")
