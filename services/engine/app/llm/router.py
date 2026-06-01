"""The LLM router — the ONE place model calls are dispatched (CLAUDE.md §4).

Resolves (tier, provider) → concrete model id from settings, calls the provider,
and returns an LlmResponse whose `model` field is the exact id used. That id is
what gets written to `SOURCED_FROM.extracted_by` so every number traces to the
model that produced it. No SDK calls happen anywhere else in the codebase."""
from __future__ import annotations

import json
from functools import lru_cache
from typing import Any

from ..config import Settings, get_settings
from .providers import (
    AnthropicProvider,
    GoogleProvider,
    OfflineProvider,
    ProviderAdapter,
)
from .types import LlmMessage, LlmRequest, LlmResponse, Provider, Tier


class LlmRouter:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._offline = OfflineProvider()
        self._anthropic = AnthropicProvider(settings)
        self._google = GoogleProvider(settings)

    # ── model resolution ─────────────────────────────────────────────────────
    def model_id(self, tier: Tier, provider: Provider) -> str:
        s = self._settings
        table: dict[tuple[Tier, Provider], str] = {
            (Tier.DEEP, Provider.ANTHROPIC): s.model_deep_anthropic,
            (Tier.DEEP, Provider.GOOGLE): s.model_deep_google,
            (Tier.MEDIUM, Provider.ANTHROPIC): s.model_medium_anthropic,
            (Tier.MEDIUM, Provider.GOOGLE): s.model_medium_google,
            (Tier.LOW, Provider.ANTHROPIC): s.model_low_anthropic,
            (Tier.LOW, Provider.GOOGLE): s.model_low_google,
            # RESEARCH reuses the DEEP model id; the agent adds web_search /
            # Deep Research orchestration on top.
            (Tier.RESEARCH, Provider.ANTHROPIC): s.model_deep_anthropic,
            (Tier.RESEARCH, Provider.GOOGLE): s.model_deep_google,
        }
        return table[(tier, provider)]

    def _resolve_provider(self, requested: Provider | None) -> Provider:
        if requested is not None:
            return requested
        return Provider(self._settings.llm_default_provider)

    def _adapter(self, provider: Provider) -> ProviderAdapter:
        if self._settings.offline:
            return self._offline
        return self._anthropic if provider == Provider.ANTHROPIC else self._google

    # ── dispatch ──────────────────────────────────────────────────────────────
    def complete(self, request: LlmRequest) -> LlmResponse:
        provider = self._resolve_provider(request.provider)
        model = self.model_id(request.tier, provider)
        adapter = self._adapter(provider)
        result = adapter.complete(
            model=model,
            messages=[{"role": m.role, "content": m.content} for m in request.messages],
            system=request.system,
            max_tokens=request.max_tokens,
            temperature=request.temperature,
            json_schema=request.json_schema,
        )
        data: Any | None = None
        if request.json_schema is not None:
            data = _safe_parse_json(result.text)
        return LlmResponse(
            text=result.text,
            model=result.model,
            provider=provider if not self._settings.offline else provider,
            tier=request.tier,
            data=data,
            usage=result.usage,
        )

    # ── convenience helpers ───────────────────────────────────────────────────
    def prompt(
        self,
        tier: Tier,
        user: str,
        *,
        system: str | None = None,
        provider: Provider | None = None,
        json_schema: dict[str, Any] | None = None,
        max_tokens: int = 4096,
    ) -> LlmResponse:
        return self.complete(
            LlmRequest(
                tier=tier,
                messages=[LlmMessage(role="user", content=user)],
                system=system,
                provider=provider,
                json_schema=json_schema,
                max_tokens=max_tokens,
            )
        )


def _safe_parse_json(text: str) -> Any | None:
    text = text.strip()
    if text.startswith("```"):
        # strip a ```json … ``` fence if a model added one
        text = text.split("```", 2)[1].removeprefix("json").strip()
    try:
        return json.loads(text)
    except (ValueError, IndexError):
        return None


@lru_cache
def get_router() -> LlmRouter:
    return LlmRouter(get_settings())
