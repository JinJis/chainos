"""Validation gate + extractor tests (offline, no Neo4j)."""
from __future__ import annotations

from app.agent.extract import parse_evidence
from app.publish.validate import validate_theme


class FakeRepo:
    def __init__(self, graph: dict) -> None:
        self._graph = graph

    def export_theme(self, theme_id: str) -> dict:
        return self._graph


def _company(cid: str, **kw):
    base = {
        "label": "Company",
        "id": cid,
        "market_cap": 1e12,
        "base_date": "26 Q1",
        "next_update": "26 Q2",
    }
    base.update(kw)
    return base


def test_gate_passes_when_fully_sourced() -> None:
    graph = {
        "nodes": [
            _company("a"),
            _company("b"),
            {"label": "Source", "id": "src-1"},
        ],
        "edges": [
            {
                "type": "SUPPLIES",
                "from": "a",
                "to": "b",
                "product_ref": "X",
                "allocation_pct": 30.0,
                "source_id": "src-1",
                "base_date": "26 Q1",
                "next_update": "26 Q2",
                "confidence": "verified",
            }
        ],
    }
    report = validate_theme("t", FakeRepo(graph))  # type: ignore[arg-type]
    assert report.ok
    assert len(report.failures) == 0 and report.passed == report.total


def test_gate_fails_on_missing_source_and_dangling_ref() -> None:
    graph = {
        "nodes": [_company("a"), _company("b", market_cap=None)],
        "edges": [
            {
                "type": "SUPPLIES",
                "from": "a",
                "to": "b",
                "allocation_pct": 30.0,
                "source_id": "ghost",  # no such Source node
                "base_date": "26 Q1",
                # next_update missing
                "confidence": "verified",
            }
        ],
    }
    report = validate_theme("t", FakeRepo(graph))  # type: ignore[arg-type]
    assert not report.ok
    edge_fail = next(f for f in report.failures if f.kind == "edge")
    assert "next_update" in edge_fail.missing
    assert any("not found" in m for m in edge_fail.missing)
    # company b is missing its market cap
    assert any("market_cap" in f.missing for f in report.failures if f.kind == "node")


def test_extractor_regex_fallback_offline() -> None:
    # Offline: no model figure → regex pulls the percentage from the text.
    out = parse_evidence(
        content_text="Per the 10-Q, allocation share to the customer was 62% in the period.",
        field="allocation_pct",
    )
    assert out["value"] == 62.0
    assert out["found"]
    assert "offline:" in out["extracted_by"]
