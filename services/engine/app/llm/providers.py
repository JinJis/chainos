"""Provider adapters. Each provider exposes one `complete()` method. SDKs are
imported lazily so the Engine boots even when a provider package or key is
absent — in that case the router falls back to the offline provider."""
from __future__ import annotations

import hashlib
import json
from typing import Any, Protocol

from ..config import Settings


class ProviderResult:
    def __init__(self, text: str, model: str, usage: dict[str, int] | None = None) -> None:
        self.text = text
        self.model = model
        self.usage = usage or {}


class ProviderAdapter(Protocol):
    name: str

    def complete(
        self,
        *,
        model: str,
        messages: list[dict[str, str]],
        system: str | None,
        max_tokens: int,
        temperature: float,
        json_schema: dict[str, Any] | None,
    ) -> ProviderResult: ...


class AnthropicProvider:
    name = "anthropic"

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._client: Any | None = None

    def _get_client(self) -> Any:
        if self._client is None:
            from anthropic import Anthropic  # lazy import

            self._client = Anthropic(api_key=self._settings.anthropic_api_key)
        return self._client

    def complete(
        self,
        *,
        model: str,
        messages: list[dict[str, str]],
        system: str | None,
        max_tokens: int,
        temperature: float,
        json_schema: dict[str, Any] | None,
    ) -> ProviderResult:
        client = self._get_client()
        sys_prompt = system or ""
        if json_schema is not None:
            sys_prompt += (
                "\n\nRespond with ONLY a single JSON object matching this schema, "
                f"no prose, no markdown fences:\n{json.dumps(json_schema)}"
            )
        resp = client.messages.create(
            model=model,
            system=sys_prompt or None,
            max_tokens=max_tokens,
            temperature=temperature,
            messages=messages,
        )
        text = "".join(
            block.text for block in resp.content if getattr(block, "type", None) == "text"
        )
        usage = {
            "input_tokens": getattr(resp.usage, "input_tokens", 0),
            "output_tokens": getattr(resp.usage, "output_tokens", 0),
        }
        return ProviderResult(text=text, model=model, usage=usage)


class GoogleProvider:
    name = "google"

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._client: Any | None = None

    def _get_client(self) -> Any:
        if self._client is None:
            from google import genai  # lazy import

            self._client = genai.Client(api_key=self._settings.google_api_key)
        return self._client

    def complete(
        self,
        *,
        model: str,
        messages: list[dict[str, str]],
        system: str | None,
        max_tokens: int,
        temperature: float,
        json_schema: dict[str, Any] | None,
    ) -> ProviderResult:
        from google.genai import types as gt  # lazy import

        client = self._get_client()
        # Flatten chat into a single prompt; the agent passes full state each turn.
        parts = [f"{m['role']}: {m['content']}" for m in messages]
        contents = "\n".join(parts)
        config: dict[str, Any] = {
            "temperature": temperature,
            "max_output_tokens": max_tokens,
        }
        if system:
            config["system_instruction"] = system
        if json_schema is not None:
            config["response_mime_type"] = "application/json"
        resp = client.models.generate_content(
            model=model, contents=contents, config=gt.GenerateContentConfig(**config)
        )
        return ProviderResult(text=resp.text or "", model=model)


class OfflineProvider:
    """Deterministic, key-free provider. Powers tests and lets the whole stack
    run without external calls. For JSON requests it returns a stable stub keyed
    on the prompt so behavior is reproducible."""

    name = "offline"

    def complete(
        self,
        *,
        model: str,
        messages: list[dict[str, str]],
        system: str | None,
        max_tokens: int,
        temperature: float,
        json_schema: dict[str, Any] | None,
    ) -> ProviderResult:
        prompt = "\n".join(m["content"] for m in messages)
        digest = hashlib.sha256(prompt.encode()).hexdigest()[:8]
        if json_schema is not None:
            stub = _offline_json_stub(json_schema, digest)
            return ProviderResult(text=json.dumps(stub), model=f"offline:{model}")
        text = f"[offline:{model}] deterministic response ({digest}) to: {prompt[:120]}"
        return ProviderResult(text=text, model=f"offline:{model}")


def _offline_json_stub(schema: dict[str, Any], seed: str) -> Any:
    """Build a minimal value satisfying a JSON-schema-ish dict (best effort)."""
    t = schema.get("type")
    if t == "object":
        props = schema.get("properties", {})
        return {k: _offline_json_stub(v, seed) for k, v in props.items()}
    if t == "array":
        item = schema.get("items", {"type": "string"})
        return [_offline_json_stub(item, seed)]
    if t == "number" or t == "integer":
        return int(seed, 16) % 100
    if t == "boolean":
        return True
    return f"offline-{seed}"
