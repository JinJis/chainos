"""The Chainos value-chain agent.

Pipeline (PRD §6.2):
  RESEARCH  — autonomous, web-grounded deep research discovers the whole value chain
              (Gemini Deep Research agent / Claude + web_search). Streams thoughts live.
  DEEP      — structures the research briefing into the graph schema (companies,
              divisions, products, SUPPLIES / REVENUE_FLOW / INVESTS_IN / COMPETES_WITH),
              inferring hidden 2nd/3rd-tier vendors.
  PERSIST   — writes the draft graph to the Staging DB.
  GAPS      — interrogates the graph (LLM + rules) and raises Need-Fact tickets for
              every missing or weakly-sourced figure.

The agent is driven via an `emit(AgentEvent)` callback so RESEARCH can stream its
thinking to the Studio console live (the caller runs the agent in a worker thread).
Offline (no keys), RESEARCH is skipped and DEEP reproduces the AI Data Centers seed
so the loop stays demonstrable."""
from __future__ import annotations

from collections.abc import Callable
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
    GAPS_SCHEMA,
    GAPS_SYSTEM,
    STRUCTURE_SCHEMA,
    STRUCTURE_SYSTEM,
    gaps_user,
    research_brief,
    structure_user,
)
from .state import AgentState

logger = get_logger("agent")

BASE_DATE = dataset.BASE_DATE
NEXT_UPDATE = dataset.NEXT_UPDATE


@dataclass
class AgentEvent:
    seq: int
    kind: str  # start|research|deep|persist|gaps|done|error
    message: str
    data: dict[str, Any] = field(default_factory=dict)
    # Ephemeral events (streamed research thoughts) are shown live but NOT persisted
    # as JobEvents, so a long research run doesn't flood the database.
    ephemeral: bool = False


EmitFn = Callable[[AgentEvent], None]


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
    nodes = [n for n in nodes if not (n["label"] == "Product" and n["id"] not in produced)]
    kept_ids = {n["id"] for n in nodes}

    edges: list[dict[str, Any]] = []
    for e in g["edges"]:
        if e.get("from") in kept_ids and e.get("to") in kept_ids:
            edges.append(e)
    return {"nodes": nodes, "edges": edges}


# ── RESEARCH ──────────────────────────────────────────────────────────────────
def _do_research(
    *,
    theme_name: str,
    depth_max: int,
    seed_tickers: list[str],
    providers: dict[str, str],
    offline: bool,
    on_event: Callable[[str, str], None],
) -> str:
    """Run the RESEARCH tier and return the grounded briefing text. Streams progress
    via on_event(kind, text)."""
    brief = research_brief(theme_name, depth_max, seed_tickers)
    logger.debug("RESEARCH BRIEF\n%s", brief)
    if offline:
        on_event("status", "offline — reproducing the seed graph (no live web research)")
        return ""
    resp = get_router().research(
        brief, provider=_provider(providers, Tier.RESEARCH), on_event=on_event
    )
    logger.debug("RESEARCH REPORT (%d chars)\n%s", len(resp.text), resp.text[:8000])
    return resp.text


# ── DEEP: structure the briefing into the graph ──────────────────────────────
def _build_from_structured(data: dict[str, Any]) -> tuple[list[dict], list[dict]]:
    nodes: list[dict[str, Any]] = []
    edges: list[dict[str, Any]] = []

    for c in data.get("companies", []):
        node = {k: v for k, v in c.items() if v is not None}
        node.setdefault("base_date", c.get("base_date") or BASE_DATE)
        node.setdefault("next_update", NEXT_UPDATE)
        nodes.append({"label": "Company", **node})
    for d in data.get("divisions", []):
        node = {k: v for k, v in d.items() if v is not None}
        nodes.append({"label": "Division", **node})
        if d.get("parent_company") and d.get("id"):
            edges.append({"type": "HAS_DIVISION", "from": d["parent_company"], "to": d["id"]})
    for p in data.get("products", []):
        node = {k: v for k, v in p.items() if v is not None and k != "division"}
        nodes.append({"label": "Product", **node})
        if p.get("division") and p.get("id"):
            edges.append({"type": "PRODUCES", "from": p["division"], "to": p["id"]})

    def _flow(items: list[dict], etype: str, extra: dict | None = None) -> None:
        for it in items:
            if not it.get("from") or not it.get("to"):
                continue
            props = {k: v for k, v in it.items() if v is not None and k != "source"}
            props.setdefault("confidence", it.get("confidence") or "derived")
            if etype in QUANTITATIVE_EDGE_TYPES:
                props.setdefault("base_date", it.get("base_date") or BASE_DATE)
                props.setdefault("next_update", NEXT_UPDATE)
            edges.append({"type": etype, **(extra or {}), **props})

    _flow(data.get("supplies", []), "SUPPLIES", {"direction": "downstream"})
    _flow(data.get("revenue_flows", []), "REVENUE_FLOW")
    _flow(data.get("invests_in", []), "INVESTS_IN")
    _flow(data.get("competes_with", []), "COMPETES_WITH")
    return nodes, edges


def _structure(state: AgentState) -> AgentState:
    offline = bool(state.get("offline"))
    report = state.get("research_report", "") or ""
    logger.info(
        "node DEEP start",
        extra={"theme_id": state.get("theme_id"), "report_chars": len(report), "offline": offline},
    )
    if offline or not report.strip():
        g = _filter_seed_by_depth(state["depth_max"])
        nodes, edges = g["nodes"], g["edges"]
        logger.debug("DEEP: structuring from seed dataset (offline or empty report)")
    else:
        resp = get_router().prompt(
            Tier.DEEP,
            structure_user(state["theme_name"], state["depth_max"], report),
            system=STRUCTURE_SYSTEM,
            provider=_provider(state["providers"], Tier.DEEP),
            json_schema=STRUCTURE_SCHEMA,
            max_tokens=8192,
        )
        data = resp.data if isinstance(resp.data, dict) else None
        if not data:
            logger.warning(
                "DEEP structuring returned no JSON; falling back to seed",
                extra={"raw_preview": resp.text[:300]},
            )
            g = _filter_seed_by_depth(state["depth_max"])
            nodes, edges = g["nodes"], g["edges"]
        else:
            nodes, edges = _build_from_structured(data)

    n_co = sum(1 for n in nodes if n["label"] == "Company")
    n_sup = sum(1 for e in edges if e["type"] == "SUPPLIES")
    divisions = [n["name"] for n in nodes if n["label"] == "Division"]
    products = [n["name"] for n in nodes if n["label"] == "Product"]
    supplies = [
        f"{e['from']}→{e['to']} ({e.get('product_ref', '?')} {e.get('allocation_pct', '?')}%)"
        for e in edges
        if e["type"] == "SUPPLIES"
    ]
    logger.info(
        "node DEEP done",
        extra={"companies": n_co, "nodes": len(nodes), "edges": len(edges), "supplies": n_sup},
    )
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
            "message": (
                f"DEEP: structured {n_co} companies, {len(nodes)} nodes, "
                f"{len(edges)} flows ({n_sup} supply links)"
            ),
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
    repo.clear_theme(state["theme_id"])  # idempotent re-run
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


# ── GAPS: interrogate for missing/weak figures → Need-Fact tickets ───────────
def _rule_based_gaps(nodes: list[dict], edges: list[dict]) -> list[dict[str, Any]]:
    specs: list[dict[str, Any]] = []
    for e in edges:
        if e["type"] not in QUANTITATIVE_EDGE_TYPES:
            continue
        weak = not e.get("source_id") or e.get("confidence") == "estimated" or (
            e["type"] == "SUPPLIES" and e.get("allocation_pct") is None
        )
        if weak:
            field_name = "allocation_pct" if e["type"] == "SUPPLIES" else "amount"
            specs.append(
                {
                    "metric": f"{e['type']} {e.get('product_ref', e.get('period', ''))}".strip(),
                    "target_ref": f"{e['from']} → {e['to']}",
                    "reason": (
                        "No filing-grade source for this figure — please upload evidence "
                        f"as of {BASE_DATE}."
                    ),
                    "priority": 1,
                    "payload": {
                        "kind": "edge",
                        "type": e["type"],
                        "from": e["from"],
                        "to": e["to"],
                        "product_ref": e.get("product_ref"),
                        "field": field_name,
                    },
                }
            )
    for n in nodes:
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
    return specs


def _convert_llm_ticket(t: dict[str, Any]) -> dict[str, Any] | None:
    try:
        if t.get("kind") == "node":
            payload = {
                "kind": "node",
                "label": t.get("label", "Company"),
                "node_id": t.get("node_id"),
                "field": t.get("field", "market_cap"),
            }
            if not payload["node_id"]:
                return None
        else:
            payload = {
                "kind": "edge",
                "type": t.get("type", "SUPPLIES"),
                "from": t.get("from"),
                "to": t.get("to"),
                "product_ref": t.get("product_ref"),
                "field": t.get("field", "allocation_pct"),
            }
            if not payload["from"] or not payload["to"]:
                return None
        return {
            "metric": str(t["metric"])[:200],
            "target_ref": str(t["target_ref"])[:200],
            "reason": str(t["reason"]),
            "priority": max(1, min(3, int(t.get("priority", 2)))),
            "payload": payload,
        }
    except (KeyError, TypeError, ValueError):
        return None


def _graph_summary(nodes: list[dict], edges: list[dict]) -> str:
    companies = [n for n in nodes if n["label"] == "Company"]
    lines = ["COMPANIES:"]
    for c in companies[:120]:
        lines.append(
            f"  {c['id']} — {c.get('name')} ({c.get('ticker')}) tier {c.get('tier')} "
            f"mcap={c.get('market_cap')}"
        )
    lines.append("SUPPLY/REVENUE/INVEST FLOWS:")
    for e in edges:
        if e["type"] in QUANTITATIVE_EDGE_TYPES:
            val = e.get("allocation_pct", e.get("amount"))
            lines.append(
                f"  {e['type']} {e['from']}→{e['to']} {e.get('product_ref', '')} "
                f"value={val} conf={e.get('confidence')} sourced={bool(e.get('source_id'))}"
            )
    text = "\n".join(lines)
    return text[:7000]


def _gaps(state: AgentState) -> AgentState:
    offline = bool(state.get("offline"))
    nodes = state.get("nodes", [])
    edges = state.get("edges", [])
    specs = _rule_based_gaps(nodes, edges)

    if not offline:
        try:
            resp = get_router().prompt(
                Tier.DEEP,
                gaps_user(state["theme_name"], _graph_summary(nodes, edges)),
                system=GAPS_SYSTEM,
                provider=_provider(state["providers"], Tier.DEEP),
                json_schema=GAPS_SCHEMA,
                max_tokens=4096,
            )
            llm_tickets = (resp.data or {}).get("tickets", []) if isinstance(resp.data, dict) else []
            converted = [c for t in llm_tickets if (c := _convert_llm_ticket(t))]
            # Merge, de-duplicating by target_ref + field.
            seen = {(s["target_ref"], s["payload"].get("field")) for s in specs}
            for c in converted:
                key = (c["target_ref"], c["payload"].get("field"))
                if key not in seen:
                    specs.append(c)
                    seen.add(key)
            logger.info(
                "GAPS interrogation",
                extra={"rule_based": len(specs) - len(converted), "llm": len(converted)},
            )
        except Exception:  # noqa: BLE001
            logger.warning("GAPS llm interrogation failed; using rule-based only", exc_info=True)

    specs.sort(key=lambda s: s.get("priority", 2))
    logger.info("node GAPS done", extra={"theme_id": state.get("theme_id"), "tickets": len(specs)})
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
    g.add_node("deep", _structure)
    g.add_node("persist", _persist)
    g.add_node("gaps", _gaps)
    g.add_edge(START, "deep")
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
    emit: EmitFn,
    seed_tickers: list[str] | None = None,
) -> None:
    """Run the full pipeline, emitting an AgentEvent per step (and per streamed
    research thought). The caller runs this in a worker thread and streams events
    to the Studio console + persists them."""
    settings = get_settings()
    offline = settings.offline
    counter = {"seq": 0}

    def ev(kind: str, message: str, data: dict | None = None, ephemeral: bool = False) -> None:
        emit(AgentEvent(counter["seq"], kind, message, data or {}, ephemeral))
        counter["seq"] += 1

    logger.info(
        "agent run START",
        extra={
            "theme_id": theme_id,
            "theme": theme_name,
            "depth": depth_max,
            "offline": offline,
            "providers": providers or {},
        },
    )
    ev(
        "start",
        f"Agent started for '{theme_name}' (depth {depth_max}) — "
        f"{'offline seed' if offline else 'live web research'}",
    )

    # ── RESEARCH (streaming) ──────────────────────────────────────────────────
    # Stream the Deep Research agent's thought summaries live, plus a lightweight
    # "drafting report" progress as the final report text streams in.
    text_progress = {"chars": 0, "emitted": 0}

    def on_research(kind: str, text: str) -> None:
        if not text:
            return
        if kind == "thought":
            logger.debug("research thought: %s", text)
            ev("research", f"🔍 {text.strip()}", ephemeral=True)
        elif kind == "text":
            text_progress["chars"] += len(text)
            if text_progress["chars"] - text_progress["emitted"] >= 600:
                text_progress["emitted"] = text_progress["chars"]
                ev("research", f"📝 drafting report… {text_progress['chars']} chars", ephemeral=True)
        else:  # status
            logger.info("research: %s", text)
            ev("research", f"· {text}")

    report = ""
    try:
        report = _do_research(
            theme_name=theme_name,
            depth_max=depth_max,
            seed_tickers=seed_tickers or [],
            providers=providers,
            offline=offline,
            on_event=on_research,
        )
    except Exception as exc:  # research failed — fall through to seed/empty
        logger.exception("RESEARCH failed", extra={"theme_id": theme_id})
        ev("research", f"⚠ research failed ({type(exc).__name__}: {exc}); using seed/derived skeleton")
    ev(
        "research",
        f"RESEARCH complete — {len(report)} chars of grounded findings"
        if report
        else "RESEARCH skipped (offline) — using seed dataset",
        {"chars": len(report)},
    )

    # ── DEEP → PERSIST → GAPS (LangGraph) ─────────────────────────────────────
    initial: AgentState = {
        "theme_id": theme_id,
        "theme_name": theme_name,
        "depth_max": depth_max,
        "providers": providers or {},
        "offline": offline,
        "research_report": report,
    }
    final: AgentState = {}
    try:
        for step in _build_graph().stream(initial):
            for node_name, update in step.items():
                final.update(update)
                logger.debug("graph step", extra={"node": node_name, "theme_id": theme_id})
                log = update.get("log")
                if log:
                    ev(log["kind"], log["message"], log.get("data", {}))
    except Exception as exc:  # noqa: BLE001 — surface to the console + logs, then stop
        logger.exception("agent run FAILED", extra={"theme_id": theme_id})
        ev("error", f"Agent error: {type(exc).__name__}: {exc}")
        return

    tickets = final.get("ticket_specs", [])
    logger.info("agent run DONE", extra={"theme_id": theme_id, "tickets": len(tickets)})
    ev(
        "done",
        "Agent finished. Draft graph staged; review Need-Fact tickets, then Publish.",
        {"tickets": tickets},
    )
