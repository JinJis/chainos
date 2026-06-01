"""Router unit tests — run offline, no keys needed."""
from __future__ import annotations

from app.config import Settings
from app.llm.router import LlmRouter
from app.llm.types import Provider, Tier


def _offline_router() -> LlmRouter:
    return LlmRouter(Settings(LLM_OFFLINE=True))


def test_model_resolution_per_tier_and_provider() -> None:
    r = _offline_router()
    assert r.model_id(Tier.DEEP, Provider.ANTHROPIC) == "claude-opus-4-8"
    assert r.model_id(Tier.MEDIUM, Provider.ANTHROPIC) == "claude-sonnet-4-6"
    assert r.model_id(Tier.LOW, Provider.GOOGLE) == "gemini-3.1-flash-lite"
    # RESEARCH reuses the DEEP model id.
    assert r.model_id(Tier.RESEARCH, Provider.GOOGLE) == r.model_id(Tier.DEEP, Provider.GOOGLE)


def test_offline_completion_is_deterministic() -> None:
    r = _offline_router()
    a = r.prompt(Tier.LOW, "hello chainos")
    b = r.prompt(Tier.LOW, "hello chainos")
    assert a.text == b.text
    assert a.model.startswith("offline:")


def test_json_schema_request_parses_into_data() -> None:
    r = _offline_router()
    schema = {
        "type": "object",
        "properties": {"allocation_pct": {"type": "number"}, "note": {"type": "string"}},
    }
    resp = r.prompt(Tier.MEDIUM, "extract allocation", json_schema=schema)
    assert resp.data is not None
    assert "allocation_pct" in resp.data


def test_provider_defaults_to_settings() -> None:
    r = LlmRouter(Settings(LLM_OFFLINE=True, LLM_DEFAULT_PROVIDER="google"))
    resp = r.prompt(Tier.DEEP, "skeleton")
    # offline provider used, but the resolved model id reflects google deep
    assert "gemini" in resp.model
