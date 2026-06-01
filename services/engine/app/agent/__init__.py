"""LangGraph agent loop: RESEARCH → DEEP → persist (Staging) → Need-Fact gaps.
State is passed explicitly each turn — no hidden memory (CLAUDE.md §4)."""

from .loop import AgentEvent, run_agent

__all__ = ["AgentEvent", "run_agent"]
