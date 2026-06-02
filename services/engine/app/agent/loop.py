"""The agent loop, wired as a LangGraph StateGraph and streamed event-by-event
to the Studio console. Offline, it reproduces the believable AI Data Centers
graph from the seed dataset so the loop is demonstrable without API keys."""
from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import Any

from langgraph.graph import END, START, StateGraph

from ..config import get_settings
from ..graph import StagingGraphRepo
from ..graph_schema import QUANTITATIVE_EDGE_TYPES
from ..llm import Provider, Tier, get_router
from ..logging_config import get_logger
from ..seed import dataset
from .prompts import (
    DEEP_SCHEMA,
    DEEP_SYSTEM,
    RESEARCH_SCHEMA,
    RESEARCH_SYSTEM,
    deep_user,
    research_user,
)
from .state import AgentState

logger = get_logger("agent")


@dataclass
class AgentEvent:
    seq: int
    kind: str  # start|research|deep|persist|gaps|done|error
    message: str
    data: dict[str, Any] = field(default_factory=dict)


def _provider(providers: dict[str, str], tier: Tier) -> Provider | None:
    name = providers.get(tier.value)
    return Provider(name) if name in ("anthropic", "google") else None


def _filter_seed_by_depth(depth: int) -> dict[str, list[dict[str, Any]]]:
    g = dataset.build_graph()
    kept_company = {
        n["id"] for n in g["nodes"] if n["label"] == "Company" and n.get("tier", 1) <= depth
    }
    produced: set[str] = set()
    for e in g["edges"]:
        if e["type"] == "PRODUCES":
            produced.add(e["to"])

    nodes: list[dict[str, Any]] = []
    for n in g["nodes"]:
        lbl = n["label"]
        if lbl == "Company" and n["id"] not in kept_company:
            continue
        if lbl == "Division" and n.get("parent_company") not in kept_company:
            continue
        nodes.append(n)
    kept_ids = {n["id"] for n in nodes}
    # keep products that a kept division produces
    nodes = [n for n in nodes if not (n["label"] == "Product" and n["id"] not in produced)]
    kept_ids = {n["id"] for n in nodes}

    edges: list[dict[str, Any]] = []
    for e in g["edges"]:
        if e.get("from") in kept_ids and e.get("to") in kept_ids:
            edges.append(e)
    return {"nodes": nodes, "edges": edges}


# ── graph nodes ──────────────────────────────────────────────────────────────
def _research(state: AgentState) -> AgentState:
    router = get_router()
    offline = bool(state.get("offline"))
    logger.info(
        "node RESEARCH start",
        extra={"theme_id": state.get("theme_id"), "depth": state["depth_max"], "offline": offline},
    )
    research_prompt = research_user(state["theme_name"], state["depth_max"], [])
    if offline:
        # Offline bypasses the model; show the prompt that WOULD be sent so the
        # console still surfaces "the prompts used".
        logger.debug(
            "RESEARCH PROMPT (offline — reproducing seed, not sent to a model)\n"
            "--- system ---\n%s\n--- user ---\n%s",
            RESEARCH_SYSTEM,
            research_prompt,
        )
        slice_ = _filter_seed_by_depth(state["depth_max"])
        companies = [n for n in slice_["nodes"] if n["label"] == "Company"]
        candidates = [
            {k: c.get(k) for k in ("id", "ticker", "name", "country", "exchange", "sector", "tier")}
            for c in companies
        ]
    else:
        # Live: the router logs the full prompt/response/result for this call.
        resp = router.prompt(
            Tier.RESEARCH,
            research_prompt,
            system=RESEARCH_SYSTEM,
            provider=_provider(state["providers"], Tier.RESEARCH),
            json_schema=RESEARCH_SCHEMA,
        )
        candidates = (resp.data or {}).get("companies", [])
        if not candidates:
            logger.warning(
                "RESEARCH returned no candidates",
                extra={"theme_id": state.get("theme_id"), "raw_preview": resp.text[:200]},
            )
    logger.debug(
        "RESEARCH RESULT — %d companies: %s",
        len(candidates),
        ", ".join(f"{c.get('name')} ({c.get('ticker')})" for c in candidates),
    )
    return {
        "candidates": candidates,
        "log": {
            "kind": "research",
            "message": f"RESEARCH: discovered {len(candidates)} candidate companies",
            "data": {"count": len(candidates)},
        },
    }


def _deep(state: AgentState) -> AgentState:
    router = get_router()
    offline = bool(state.get("offline"))
    logger.info(
        "node DEEP start",
        extra={"theme_id": state.get("theme_id"), "candidates": len(state.get("candidates", []))},
    )
    if offline:
        g = _filter_seed_by_depth(state["depth_max"])
        nodes, edges = g["nodes"], g["edges"]
        offline_companies = [
            {"name": n.get("name"), "ticker": n.get("ticker")}
            for n in nodes
            if n["label"] == "Company"
        ]
        logger.debug(
            "DEEP PROMPT (offline — reproducing seed, not sent to a model)\n"
            "--- system ---\n%s\n--- user ---\n%s",
            DEEP_SYSTEM,
            deep_user(state["theme_name"], offline_companies),
        )
    else:
        candidates = state.get("candidates", [])
        nodes = [{"label": "Company", **c} for c in candidates]
        # Live: the router logs the full prompt/response/result for this call.
        resp = router.prompt(
            Tier.DEEP,
            deep_user(state["theme_name"], candidates),
            system=DEEP_SYSTEM,
            provider=_provider(state["providers"], Tier.DEEP),
            json_schema=DEEP_SCHEMA,
            max_tokens=8192,
        )
        data = resp.data or {}
        for d in data.get("divisions", []):
            nodes.append({"label": "Division", **d})
        for p in data.get("products", []):
            node = {k: v for k, v in p.items() if k != "division"}
            nodes.append({"label": "Product", **node})
        edges = []
        for d in data.get("divisions", []):
            edges.append({"type": "HAS_DIVISION", "from": d["parent_company"], "to": d["id"]})
        for p in data.get("products", []):
            if p.get("division"):
                edges.append({"type": "PRODUCES", "from": p["division"], "to": p["id"]})
        for sup in data.get("supplies", []):
            edges.append({"type": "SUPPLIES", "confidence": "derived", **sup})
    n_co = sum(1 for n in nodes if n["label"] == "Company")
    n_sup = sum(1 for e in edges if e["type"] == "SUPPLIES")
    logger.info(
        "node DEEP done",
        extra={"companies": n_co, "nodes": len(nodes), "edges": len(edges), "supplies": n_sup},
    )
    # Detailed RESULT — divisions, products, supply links the agent drafted.
    divisions = [n["name"] for n in nodes if n["label"] == "Division"]
    products = [n["name"] for n in nodes if n["label"] == "Product"]
    supplies = [
        f"{e['from']}→{e['to']} ({e.get('product_ref', '?')} {e.get('allocation_pct', '?')}%)"
        for e in edges
        if e["type"] == "SUPPLIES"
    ]
    logger.debug(
        "DEEP RESULT\n  divisions: %s\n  products: %s\n  supplies:\n    %s",
        ", ".join(divisions) or "(none)",
        ", ".join(products) or "(none)",
        "\n    ".join(supplies) or "(none)",
    )
    return {
        "nodes": nodes,
        "edges": edges,
        "log": {
            "kind": "deep",
            "message": f"DEEP: drafted skeleton — {n_co} companies, {len(nodes)} nodes, {n_sup} supply links",
            "data": {"nodes": len(nodes), "edges": len(edges)},
        },
    }


def _persist(state: AgentState) -> AgentState:
    repo = StagingGraphRepo()
    logger.info(
        "node PERSIST start",
        extra={
            "theme_id": state.get("theme_id"),
            "nodes": len(state.get("nodes", [])),
            "edges": len(state.get("edges", [])),
        },
    )
    repo.ensure_constraints()
    repo.write_graph(state["theme_id"], state.get("nodes", []), state.get("edges", []))
    counts = repo.count(state["theme_id"])
    logger.info("node PERSIST done", extra={"theme_id": state.get("theme_id"), **counts})
    return {
        "log": {
            "kind": "persist",
            "message": f"PERSIST: wrote {counts['nodes']} nodes / {counts['edges']} flows to Staging",
            "data": counts,
        }
    }


def _gaps(state: AgentState) -> AgentState:
    """Issue Need-Fact tickets where an authoritative figure is weak/missing."""
    specs: list[dict[str, Any]] = []
    for e in state.get("edges", []):
        if e["type"] not in QUANTITATIVE_EDGE_TYPES:
            continue
        weak = not e.get("source_id") or e.get("confidence") == "estimated"
        if weak:
            field = "allocation_pct" if e["type"] == "SUPPLIES" else "amount"
            specs.append(
                {
                    "metric": f"{e['type']} {e.get('product_ref', e.get('period', ''))}".strip(),
                    "target_ref": f"{e['from']} → {e['to']}",
                    "reason": (
                        "No filing-grade source for this allocation — please upload evidence "
                        f"as of {dataset.BASE_DATE}."
                        if not e.get("source_id")
                        else "Figure is only an estimate; firmer disclosure evidence requested."
                    ),
                    "priority": 1 if not e.get("source_id") else 2,
                    "payload": {
                        "kind": "edge",
                        "type": e["type"],
                        "from": e["from"],
                        "to": e["to"],
                        "product_ref": e.get("product_ref"),
                        "field": field,
                    },
                }
            )
    for n in state.get("nodes", []):
        if n["label"] == "Company" and n.get("market_cap") is None:
            specs.append(
                {
                    "metric": "market_cap",
                    "target_ref": n["id"],
                    "reason": "Missing live market cap for node sizing.",
                    "priority": 2,
                    "payload": {
                        "kind": "node",
                        "label": "Company",
                        "node_id": n["id"],
                        "field": "market_cap",
                    },
                }
            )
    logger.info(
        "node GAPS done",
        extra={"theme_id": state.get("theme_id"), "tickets": len(specs)},
    )
    for spec in specs:
        logger.debug("need-fact ticket", extra={"metric": spec["metric"], "target": spec["target_ref"]})
    return {
        "ticket_specs": specs,
        "log": {
            "kind": "gaps",
            "message": f"NEED-FACT: raised {len(specs)} data-gap tickets for admin review",
            "data": {"tickets": specs},
        },
    }


def _build_graph():
    g = StateGraph(AgentState)
    g.add_node("research", _research)
    g.add_node("deep", _deep)
    g.add_node("persist", _persist)
    g.add_node("gaps", _gaps)
    g.add_edge(START, "research")
    g.add_edge("research", "deep")
    g.add_edge("deep", "persist")
    g.add_edge("persist", "gaps")
    g.add_edge("gaps", END)
    return g.compile()


def run_agent(
    *,
    theme_id: str,
    theme_name: str,
    depth_max: int,
    providers: dict[str, str],
    seed_tickers: list[str] | None = None,
) -> Iterator[AgentEvent]:
    """Run the loop, yielding an AgentEvent per step. Writes the draft graph to
    the Staging DB as it goes; the caller persists job events + tickets."""
    settings = get_settings()
    seq = 0
    logger.info(
        "agent run START",
        extra={
            "theme_id": theme_id,
            "theme": theme_name,
            "depth": depth_max,
            "offline": settings.offline,
            "providers": providers or {},
        },
    )
    yield AgentEvent(seq, "start", f"Agent started for theme '{theme_name}' (depth {depth_max})")
    seq += 1

    initial: AgentState = {
        "theme_id": theme_id,
        "theme_name": theme_name,
        "depth_max": depth_max,
        "providers": providers or {},
        "offline": settings.offline,
    }
    final: AgentState = {}
    graph = _build_graph()
    try:
        for step in graph.stream(initial):
            for node_name, update in step.items():
                final.update(update)
                logger.debug("graph step", extra={"node": node_name, "theme_id": theme_id})
                log = update.get("log")
                if log:
                    yield AgentEvent(seq, log["kind"], log["message"], log.get("data", {}))
                    seq += 1
    except Exception as exc:  # surface failures into the console + server logs
        logger.exception("agent run FAILED", extra={"theme_id": theme_id, "seq": seq})
        yield AgentEvent(seq, "error", f"Agent error: {type(exc).__name__}: {exc}")
        raise

    tickets = final.get("ticket_specs", [])
    logger.info(
        "agent run DONE",
        extra={"theme_id": theme_id, "tickets": len(tickets), "events": seq},
    )
    yield AgentEvent(
        seq,
        "done",
        "Agent finished. Draft graph staged; review Need-Fact tickets, then Publish.",
        {"tickets": tickets},
    )
