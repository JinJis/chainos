"""Explicit agent state (LangGraph channels)."""
from __future__ import annotations

from typing import Any, TypedDict


class AgentState(TypedDict, total=False):
    theme_id: str
    theme_name: str
    depth_max: int
    # tier -> provider, e.g. {"RESEARCH": "google", "DEEP": "anthropic", ...}
    providers: dict[str, str]
    offline: bool

    candidates: list[dict[str, Any]]
    nodes: list[dict[str, Any]]
    edges: list[dict[str, Any]]
    ticket_specs: list[dict[str, Any]]

    # Per-step log surfaced to the Studio console; overwritten each node.
    log: dict[str, Any]
