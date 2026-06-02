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


# ── live-path structuring (the DEEP step turning research JSON → graph) ───────
_STRUCTURED = {
    "companies": [
        {"id": "nvda", "ticker": "NVDA", "name": "Nvidia", "country": "US",
         "exchange": "NASDAQ", "sector": "Semiconductors", "tier": 1, "market_cap": 3.3e12},
        {"id": "skhynix", "ticker": "000660.KS", "name": "SK hynix", "country": "KR",
         "exchange": "KRX", "sector": "Semiconductors", "tier": 2},
    ],
    "divisions": [{"id": "nvda-dc", "name": "Data Center", "parent_company": "nvda", "revenue_share": 87.0}],
    "products": [{"id": "b200", "name": "Blackwell B200", "category": "GPU", "division": "nvda-dc", "revenue": 4e10}],
    "supplies": [{"from": "skhynix", "to": "nvda", "product_ref": "HBM3E", "allocation_pct": 50.0,
                  "confidence": "verified", "source": "SK hynix 26Q1 10-Q"}],
    "revenue_flows": [{"from": "nvda", "to": "skhynix", "amount": 1e10, "currency": "USD", "period": "26Q1"}],
    "invests_in": [{"from": "nvda", "to": "skhynix", "amount": 8e9}],
    "competes_with": [{"from": "nvda", "to": "skhynix", "overlap_score": 0.3}],
}


def test_build_from_structured_emits_all_node_and_edge_types() -> None:
    from app.agent.loop import _build_from_structured

    nodes, edges = _build_from_structured(_STRUCTURED)
    labels = {n["label"] for n in nodes}
    assert {"Company", "Division", "Product"} <= labels
    types = {e["type"] for e in edges}
    assert {"HAS_DIVISION", "PRODUCES", "SUPPLIES", "REVENUE_FLOW", "INVESTS_IN", "COMPETES_WITH"} <= types
    sup = next(e for e in edges if e["type"] == "SUPPLIES")
    # quantitative edge gets trust meta stamped; the raw "source" hint is dropped.
    assert sup["allocation_pct"] == 50.0 and sup["confidence"] == "verified"
    assert sup.get("base_date") and sup.get("next_update")
    assert "source" not in sup


def test_convert_llm_ticket_maps_and_validates() -> None:
    from app.agent.loop import _convert_llm_ticket

    edge = _convert_llm_ticket(
        {"metric": "CoWoS allocation", "target_ref": "tsmc→nvda", "reason": "unsourced",
         "priority": 1, "kind": "edge", "type": "SUPPLIES", "from": "tsmc", "to": "nvda",
         "product_ref": "CoWoS", "field": "allocation_pct"}
    )
    assert edge and edge["payload"]["kind"] == "edge" and edge["payload"]["from"] == "tsmc"
    node = _convert_llm_ticket(
        {"metric": "market cap", "target_ref": "skhynix", "reason": "missing",
         "priority": 2, "kind": "node", "label": "Company", "node_id": "skhynix", "field": "market_cap"}
    )
    assert node and node["payload"]["node_id"] == "skhynix"
    # invalid (no endpoints) is dropped
    assert _convert_llm_ticket({"metric": "x", "target_ref": "y", "reason": "z", "kind": "edge", "field": "f"}) is None
