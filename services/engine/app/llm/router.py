"""The LLM router — the ONE place model calls are dispatched (CLAUDE.md §4).

Resolves (tier, provider) → concrete model id from settings, calls the provider,
and returns an LlmResponse whose `model` field is the exact id used. That id is
what gets written to `SOURCED_FROM.extracted_by` so every number traces to the
model that produced it. No SDK calls happen anywhere else in the codebase."""
from __future__ import annotations

import json
import time
from functools import lru_cache
from typing import Any

from ..config import Settings, get_settings
from ..logging_config import get_logger
from .providers import (
    AnthropicProvider,
    GoogleProvider,
    OfflineProvider,
    ProviderAdapter,
    ResearchCallback,
)
from .types import LlmMessage, LlmRequest, LlmResponse, Provider, Tier

log = get_logger("llm")


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
        offline = self._settings.offline
        log.debug(
            "llm call",
            extra={
                "tier": request.tier.value,
                "provider": provider.value,
                "model": model,
                "mode": "offline" if offline else "live",
                "json": request.json_schema is not None,
                "max_tokens": request.max_tokens,
            },
        )
        # Full PROMPT (system + messages) — visible in the Studio console at DEBUG.
        user_text = "\n".join(f"[{m.role}] {m.content}" for m in request.messages)
        log.debug(
            "LLM PROMPT  %s/%s %s\n--- system ---\n%s\n--- user ---\n%s",
            request.tier.value,
            provider.value,
            model,
            request.system or "(none)",
            user_text,
        )
        start = time.perf_counter()
        try:
            result = adapter.complete(
                model=model,
                messages=[{"role": m.role, "content": m.content} for m in request.messages],
                system=request.system,
                max_tokens=request.max_tokens,
                temperature=request.temperature,
                json_schema=request.json_schema,
            )
        except Exception:
            log.exception(
                "llm call FAILED",
                extra={"tier": request.tier.value, "provider": provider.value, "model": model},
            )
            raise
        duration_ms = round((time.perf_counter() - start) * 1000, 1)

        # Raw RESPONSE text.
        log.debug("LLM RESPONSE  %s (%sms)\n%s", result.model, duration_ms, _truncate(result.text))

        data: Any | None = None
        if request.json_schema is not None:
            data = _safe_parse_json(result.text)
            if data is None:
                log.warning(
                    "llm JSON response did not parse",
                    extra={"tier": request.tier.value, "model": result.model,
                           "preview": result.text[:200]},
                )
            else:
                # Parsed RESULT.
                log.debug(
                    "LLM RESULT (parsed)  %s\n%s",
                    result.model,
                    _truncate(json.dumps(data, ensure_ascii=False, indent=2)),
                )
        log.info(
            "llm done",
            extra={
                "tier": request.tier.value,
                "model": result.model,
                "ms": duration_ms,
                "in_tokens": result.usage.get("input_tokens", 0),
                "out_tokens": result.usage.get("output_tokens", 0),
                "chars": len(result.text),
            },
        )
        return LlmResponse(
            text=result.text,
            model=result.model,
            provider=provider,
            tier=request.tier,
            data=data,
            usage=result.usage,
        )

    # ── RESEARCH tier (autonomous web research) ───────────────────────────────
    def research(
        self,
        brief: str,
        *,
        provider: Provider | None = None,
        on_event: ResearchCallback | None = None,
    ) -> LlmResponse:
        """Run the RESEARCH tier — an autonomous, web-grounded deep-research pass.
        Google → Gemini Deep Research agent; Anthropic → Claude + web_search.
        Streams progress via `on_event(kind, text)`."""
        resolved = self._resolve_provider(provider)
        emit = on_event or (lambda _kind, _text: None)
        offline = self._settings.offline
        timeout = self._settings.research_timeout_s
        log.info(
            "RESEARCH start",
            extra={"provider": resolved.value, "offline": offline, "timeout_s": timeout},
        )
        if offline:
            result = self._offline.deep_research(brief=brief, on_event=emit, timeout_s=timeout)
        elif resolved == Provider.GOOGLE:
            result = self._google.deep_research(
                brief=brief, on_event=emit, max_mode=self._settings.research_max, timeout_s=timeout
            )
        else:
            result = self._anthropic.deep_research(
                brief=brief, on_event=emit, max_mode=self._settings.research_max, timeout_s=timeout
            )
        log.info(
            "RESEARCH done",
            extra={"provider": resolved.value, "model": result.model, "chars": len(result.text)},
        )
        return LlmResponse(
            text=result.text,
            model=result.model,
            provider=resolved,
            tier=Tier.RESEARCH,
            data=None,
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


# Cap very long prompt/response dumps in the log/console (generous but bounded).
_LOG_MAX_CHARS = 8000


def _truncate(text: str, limit: int = _LOG_MAX_CHARS) -> str:
    if len(text) <= limit:
        return text
    return f"{text[:limit]}… (+{len(text) - limit} more chars)"


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
