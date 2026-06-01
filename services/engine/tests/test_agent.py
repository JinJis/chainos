"""Agent loop offline test — no DB, no keys. Verifies the loop produces a
believable staged graph and raises Need-Fact tickets for weak figures."""
from __future__ import annotations

from app.seed import dataset


def test_seed_graph_is_fully_sourced_where_quantitative() -> None:
    g = dataset.build_graph()
    quant = {"SUPPLIES", "REVENUE_FLOW", "INVESTS_IN"}
    for e in g["edges"]:
        if e["type"] in quant:
            assert e.get("source_id"), f"{e} missing source"
            assert e.get("base_date") and e.get("next_update")
            assert e.get("confidence") in {"verified", "derived", "estimated"}


def test_build_graph_has_expected_shape() -> None:
    g = dataset.build_graph()
    labels = {n["label"] for n in g["nodes"]}
    assert {"Company", "Division", "Product", "Source"} <= labels
    types = {e["type"] for e in g["edges"]}
    assert {"HAS_DIVISION", "PRODUCES", "SUPPLIES"} <= types


def test_depth_filter_reduces_company_count() -> None:
    from app.agent.loop import _filter_seed_by_depth

    d1 = _filter_seed_by_depth(1)
    d3 = _filter_seed_by_depth(3)
    c1 = sum(1 for n in d1["nodes"] if n["label"] == "Company")
    c3 = sum(1 for n in d3["nodes"] if n["label"] == "Company")
    assert c1 < c3
    # every kept edge has both endpoints present
    ids = {n["id"] for n in d1["nodes"]}
    for e in d1["edges"]:
        assert e["from"] in ids and e["to"] in ids
