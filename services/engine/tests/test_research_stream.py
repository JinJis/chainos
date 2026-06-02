"""Deep Research streaming parser tests — verify thoughts + report text are pulled
out of the interaction stream whether the SDK gives string or enum event types."""
from __future__ import annotations

from enum import Enum
from types import SimpleNamespace

from app.config import Settings
from app.llm.providers import GoogleProvider, _delta_text, _enum_str


class _EType(Enum):
    CREATED = "interaction.created"
    DELTA = "step.delta"
    DONE = "interaction.completed"


def _evt(event_type, event_id=None, **kw):
    return SimpleNamespace(event_type=event_type, event_id=event_id, **kw)


class _FakeInteractions:
    def __init__(self, events):
        self._events = events

    def create(self, **kw):
        return iter(self._events)

    def get(self, id=None, stream=False, last_event_id=None):  # noqa: A002
        if stream:
            return iter([])
        return SimpleNamespace(status="completed", output_text="", error=None)


class _FakeClient:
    def __init__(self, events):
        self.interactions = _FakeInteractions(events)


def _run(events):
    provider = GoogleProvider(Settings(GOOGLE_API_KEY="x"))
    collected: list[tuple[str, str]] = []
    result = provider._run_interactions(
        _FakeClient(events), "deep-research-preview", "brief", lambda k, t: collected.append((k, t)), 5
    )
    return collected, result


def test_enum_str_unwraps_enums_and_strings() -> None:
    assert _enum_str("step.delta") == "step.delta"
    assert _enum_str(_EType.DELTA) == "step.delta"
    assert _enum_str(None) is None


def test_delta_text_handles_multiple_shapes() -> None:
    assert _delta_text(SimpleNamespace(text="a")) == "a"
    assert _delta_text(SimpleNamespace(thought="b")) == "b"
    assert _delta_text({"content": "c"}) == "c"


def test_stream_parses_string_event_types() -> None:
    events = [
        _evt("interaction.created", event_id="e1", interaction=SimpleNamespace(id="abc")),
        _evt("step.delta", event_id="e2", delta=SimpleNamespace(type="thought", text="thinking about HBM")),
        _evt("step.delta", event_id="e3", delta=SimpleNamespace(type="text", text="Nvidia buys HBM. ")),
        _evt("step.delta", event_id="e4", delta=SimpleNamespace(type="text", text="TSMC packages it.")),
        _evt("interaction.completed", event_id="e5"),
    ]
    collected, result = _run(events)
    assert ("thought", "thinking about HBM") in collected
    assert result.text == "Nvidia buys HBM. TSMC packages it."


def test_stream_parses_enum_event_types() -> None:
    """The real bug: event_type / delta.type are enums, so == 'step.delta' fails and
    thoughts/text silently vanish (report only survives via output_text fallback)."""
    events = [
        _evt(_EType.CREATED, event_id="e1", interaction=SimpleNamespace(id="abc")),
        _evt(_EType.DELTA, event_id="e2",
             delta=SimpleNamespace(type=SimpleNamespace(value="thought"), text="enum thought")),
        _evt(_EType.DELTA, event_id="e3",
             delta=SimpleNamespace(type=SimpleNamespace(value="text"), text="enum report")),
        _evt(_EType.DONE, event_id="e4"),
    ]
    collected, result = _run(events)
    assert ("thought", "enum thought") in collected
    assert result.text == "enum report"
