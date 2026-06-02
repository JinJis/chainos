"""Provider adapters. Each provider exposes one `complete()` method. SDKs are
imported lazily so the Engine boots even when a provider package or key is
absent — in that case the router falls back to the offline provider."""
from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from typing import Any, Protocol

from ..config import Settings
from ..logging_config import get_logger

log = get_logger("llm.provider")

# Callback for streaming research progress: (kind, text) where kind is
# "thought" (agent reasoning) or "status" (pipeline note).
ResearchCallback = Callable[[str, str], None]


def _enum_str(value: Any) -> str | None:
    """Normalize an SDK field that may be a str OR an enum to its string value,
    so comparisons like == 'step.delta' work regardless of SDK typing."""
    if value is None:
        return None
    value = getattr(value, "value", value)  # unwrap enums (e.g. EventType.STEP_DELTA)
    return str(value)


def _delta_text(delta: Any) -> str:
    """Pull the text out of a step.delta across possible SDK shapes."""
    for attr in ("text", "thought", "content", "summary"):
        val = getattr(delta, attr, None)
        if isinstance(val, str) and val:
            return val
    if isinstance(delta, dict):
        for key in ("text", "thought", "content", "summary"):
            if isinstance(delta.get(key), str):
                return delta[key]
    return ""


def _describe(obj: Any) -> str:
    """Compact structural description of an SDK object for diagnostics."""
    try:
        d = getattr(obj, "__dict__", None)
        if d:
            return f"{type(obj).__name__} {dict(d)!r}"[:600]
        attrs = [a for a in dir(obj) if not a.startswith("_")]
        return f"{type(obj).__name__} attrs={attrs}"[:600]
    except Exception:  # noqa: BLE001
        return repr(obj)[:600]


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

    # ── RESEARCH tier: Claude + web_search tool ──────────────────────────────
    def deep_research(
        self,
        *,
        brief: str,
        on_event: ResearchCallback,
        max_mode: bool = False,
        timeout_s: int = 900,
    ) -> ProviderResult:
        """Claude-driven web research using the server-side web_search tool. Falls
        back to plain reasoning if the tool isn't enabled for the account."""
        model = self._settings.model_deep_anthropic
        on_event("status", f"web research via {model} + web_search tool")
        try:
            client = self._get_client()
            try:
                resp = client.messages.create(
                    model=model,
                    max_tokens=8192,
                    tools=[{"type": "web_search_20250305", "name": "web_search", "max_uses": 10}],
                    messages=[{"role": "user", "content": brief}],
                )
                text = "".join(
                    b.text for b in resp.content if getattr(b, "type", None) == "text"
                )
                if text.strip():
                    return ProviderResult(text=text, model=f"{model}+web_search")
            except Exception as exc:  # noqa: BLE001
                log.warning("web_search tool failed", exc_info=True)
                on_event("status", f"web_search tool unavailable ({exc}); plain reasoning")
            resp = client.messages.create(
                model=model, max_tokens=8192, messages=[{"role": "user", "content": brief}]
            )
            text = "".join(b.text for b in resp.content if getattr(b, "type", None) == "text")
            return ProviderResult(text=text, model=model)
        except Exception as exc:  # noqa: BLE001 — never crash the run
            log.warning("anthropic research unavailable", exc_info=True)
            on_event("status", f"research unavailable ({type(exc).__name__}: {exc})")
            return ProviderResult(text="", model="research-failed")


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

    # ── RESEARCH tier: autonomous Gemini Deep Research agent ─────────────────
    def deep_research(
        self,
        *,
        brief: str,
        on_event: ResearchCallback,
        max_mode: bool = False,
        timeout_s: int = 900,
    ) -> ProviderResult:
        """Run the Gemini Deep Research agent (web-grounded, multi-step) and stream
        its thoughts via `on_event`. NEVER raises — degrades to google_search-grounded
        generation, then to empty, so a research hiccup can't crash the agent run."""
        try:
            client = self._get_client()
            agent_id = self._settings.model_research_google
            if max_mode and "max" not in agent_id:
                agent_id = agent_id.replace("deep-research-preview", "deep-research-max-preview")

            if getattr(client, "interactions", None) is not None:
                try:
                    result = self._run_interactions(client, agent_id, brief, on_event, timeout_s)
                    if result.text.strip():
                        return result
                    on_event("status", "Deep Research returned no text; using google_search grounding")
                except Exception as exc:  # noqa: BLE001
                    log.warning("Deep Research interactions failed", exc_info=True)
                    on_event(
                        "status",
                        f"Deep Research API failed ({type(exc).__name__}: {exc}); "
                        "falling back to google_search grounding",
                    )
            else:
                on_event(
                    "status", "Deep Research API not in this SDK build; using google_search grounding"
                )
            return self._grounded_research(brief, on_event)
        except Exception as exc:  # noqa: BLE001 — last-resort guard
            log.warning("research unavailable", exc_info=True)
            on_event(
                "status",
                f"research unavailable ({type(exc).__name__}: {exc}); "
                "proceeding with a derived skeleton",
            )
            return ProviderResult(text="", model="research-failed")

    def _run_interactions(
        self, client: Any, agent_id: str, brief: str, on_event: ResearchCallback, timeout_s: int
    ) -> ProviderResult:
        """Stream the Deep Research interaction live (thought summaries + report text),
        reconnecting by interaction_id + last_event_id if the stream drops — exactly
        the pattern from the Gemini Deep Research streaming docs."""
        import time as _time

        config = {
            "type": "deep-research",
            "thinking_summaries": "auto",  # required to receive intermediate thoughts
            "collaborative_planning": False,  # approve + start research immediately
        }
        state: dict[str, Any] = {"id": None, "last_event": None, "done": False}
        report_parts: list[str] = []
        counts: dict[str, int] = {"events": 0, "thought": 0, "text": 0, "other": 0}

        def process_stream(stream: Any) -> None:
            for event in stream:
                counts["events"] += 1
                # The SDK may give event_type / delta.type as enums — normalize to str.
                etype = _enum_str(getattr(event, "event_type", None) or getattr(event, "type", None))
                # Dump the first few raw events so we can verify the actual shape.
                if counts["events"] <= 6:
                    log.debug("DR raw event #%d: %s", counts["events"], _describe(event))
                if etype == "interaction.created":
                    interaction = getattr(event, "interaction", None)
                    state["id"] = getattr(interaction, "id", None) or state["id"]
                if getattr(event, "event_id", None):
                    state["last_event"] = event.event_id
                if etype == "step.delta":
                    delta = getattr(event, "delta", None)
                    dtype = _enum_str(getattr(delta, "type", None))
                    text = _delta_text(delta)
                    if dtype == "text":  # part of the final report, streamed live
                        counts["text"] += 1
                        report_parts.append(text)
                        on_event("text", text)
                    elif dtype == "thought":  # intermediate reasoning step
                        counts["thought"] += 1
                        log.debug("DR thought: %s", text[:200])
                        on_event("thought", text)
                    else:
                        counts["other"] += 1
                        log.debug("DR step.delta other type=%r text=%r", dtype, text[:120])
                elif etype in ("interaction.completed", "error", "interaction.failed"):
                    state["done"] = True
                elif etype:
                    log.debug("DR event type=%s", etype)

        on_event("status", f"starting Gemini Deep Research ({agent_id}) with google_search")
        stream = client.interactions.create(
            input=brief,
            agent=agent_id,
            tools=[{"type": "google_search"}],
            background=True,
            stream=True,
            agent_config=config,
        )
        process_stream(stream)

        # The streaming connection can drop/expire on long tasks — poll status and
        # reconnect from the last event until the interaction finishes.
        deadline = _time.monotonic() + timeout_s
        while not state["done"] and state["id"] and _time.monotonic() < deadline:
            status = client.interactions.get(state["id"])
            st = _enum_str(getattr(status, "status", None))
            if st not in ("in_progress", "queued", "running", None):
                if st == "failed":
                    on_event("status", f"Deep Research failed: {getattr(status, 'error', '')}")
                if not report_parts and getattr(status, "output_text", None):
                    report_parts.append(status.output_text)
                break
            on_event("status", "researching… (reconnecting to stream)")
            stream = client.interactions.get(
                id=state["id"], stream=True, last_event_id=state["last_event"]
            )
            process_stream(stream)

        report = "".join(report_parts).strip()
        if not report and state["id"]:
            final = client.interactions.get(state["id"])
            report = getattr(final, "output_text", "") or ""
        log.info(
            "Deep Research stream summary",
            extra={
                "events": counts["events"],
                "thoughts": counts["thought"],
                "text_deltas": counts["text"],
                "other_deltas": counts["other"],
                "report_chars": len(report),
            },
        )
        on_event(
            "status",
            f"Deep Research complete — {counts['thought']} thoughts, {len(report)} report chars",
        )
        return ProviderResult(text=report, model=agent_id)

    def _grounded_research(self, brief: str, on_event: ResearchCallback) -> ProviderResult:
        from google.genai import types as gt

        client = self._get_client()
        model = self._settings.model_deep_google
        on_event("status", f"web-grounded research via {model} + google_search")
        try:
            cfg = gt.GenerateContentConfig(
                tools=[gt.Tool(google_search=gt.GoogleSearch())],
                temperature=0.4,
                max_output_tokens=8192,
            )
            resp = client.models.generate_content(model=model, contents=brief, config=cfg)
            if (resp.text or "").strip():
                return ProviderResult(text=resp.text or "", model=f"{model}+google_search")
        except Exception as exc:  # noqa: BLE001
            log.warning("google_search grounding failed", exc_info=True)
            on_event("status", f"google_search grounding failed ({exc}); plain generation")
        # Last resort: plain generation (no tools).
        try:
            resp = client.models.generate_content(
                model=model,
                contents=brief,
                config=gt.GenerateContentConfig(temperature=0.4, max_output_tokens=8192),
            )
            return ProviderResult(text=resp.text or "", model=model)
        except Exception as exc:  # noqa: BLE001
            log.warning("plain generation failed", exc_info=True)
            on_event("status", f"plain generation failed ({type(exc).__name__}: {exc})")
            return ProviderResult(text="", model="research-failed")


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

    def deep_research(
        self,
        *,
        brief: str,
        on_event: ResearchCallback,
        max_mode: bool = False,
        timeout_s: int = 900,
    ) -> ProviderResult:
        on_event("status", "offline: no live research — the agent will reproduce the seed graph")
        return ProviderResult(text="", model="offline:deep-research")


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
