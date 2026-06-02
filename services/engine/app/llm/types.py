"""Shared types for the LLM router."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class Tier(StrEnum):
    """Task tier — routes to the right model by complexity/cost (PRD §6.1)."""

    DEEP = "DEEP"  # industry depth reasoning, hidden vendor inference, graph skeleton
    MEDIUM = "MEDIUM"  # precise numeric extraction from disclosures, cross-check
    LOW = "LOW"  # news parsing, sentiment, JSON normalization
    RESEARCH = "RESEARCH"  # broad candidate discovery (Deep Research / web_search)


class Provider(StrEnum):
    ANTHROPIC = "anthropic"
    GOOGLE = "google"


@dataclass
class LlmMessage:
    role: str  # "user" | "assistant"
    content: str


@dataclass
class LlmRequest:
    tier: Tier
    messages: list[LlmMessage]
    system: str | None = None
    provider: Provider | None = None  # None → project/default provider
    max_tokens: int = 4096
    temperature: float = 0.2
    # When set, the provider is asked to return JSON matching this schema. Used
    # for MEDIUM numeric extraction and LOW schema-normalization steps.
    json_schema: dict[str, Any] | None = None


@dataclass
class LlmResponse:
    text: str
    model: str  # exact model id used → written to SOURCED_FROM.extracted_by
    provider: Provider
    tier: Tier
    # Parsed JSON when json_schema was requested and parsing succeeded.
    data: Any | None = None
    usage: dict[str, int] = field(default_factory=dict)
