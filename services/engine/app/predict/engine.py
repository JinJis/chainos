"""Predict pipeline: entity-link news → score sentiment/impact → momentum → Redis.

Reads Production (read-only) to know the universe of nodes. The result is cached;
the Terminal overlay reads the cache. Production is never modified."""
from __future__ import annotations

from typing import Any

from ..config import get_settings
from ..graph import ProductionGraphRepo
from ..llm import Provider, Tier, get_router
from ..logging_config import get_logger
from . import momentum as m
from .cache import read_momentum, write_momentum

log = get_logger("predict")

# Entity-link confidence floor: contributions to unknown nodes are dropped.
RELEVANCE_FLOOR = 0.0


def _alias_map(nodes: list[dict[str, Any]]) -> dict[str, str]:
    """Build a name/ticker → company_id dictionary for entity linking."""
    aliases: dict[str, str] = {}
    for n in nodes:
        cid = n["id"]
        aliases[cid.lower()] = cid
        if n.get("name"):
            aliases[n["name"].lower()] = cid
            aliases[n["name"].split()[0].lower()] = cid
        if n.get("ticker"):
            aliases[n["ticker"].lower()] = cid
            aliases[n["ticker"].split(".")[0].lower()] = cid
    return aliases


def _link(entity: str, node_ids: set[str], aliases: dict[str, str]) -> str | None:
    if entity in node_ids:
        return entity
    return aliases.get(entity.lower())


def compute_and_cache(theme_id: str, news: list[dict[str, Any]]) -> dict[str, Any]:
    """Score `news` into per-node momentum for the published theme and cache it."""
    nodes = ProductionGraphRepo().get_graph(theme_id, labels=["Company"])["nodes"]
    node_ids = {n["id"] for n in nodes}
    names = {n["id"]: n.get("name", n["id"]) for n in nodes}
    aliases = _alias_map(nodes)
    log.info("compute momentum", extra={"theme_id": theme_id, "nodes": len(node_ids),
                                        "news": len(news)})
    if not node_ids:
        log.warning("predict on empty/unpublished theme", extra={"theme_id": theme_id})

    # LOW-tier model id powering the analysis (shown in the tooltip).
    engine_label = get_router().model_id(Tier.LOW, Provider(get_settings().llm_default_provider))

    acc: dict[str, dict[str, Any]] = {}
    linked = 0
    for item in news:
        weight = float(item.get("weight", 1.0))
        decay = m.recency_decay(float(item.get("hours_ago", 6)))
        for impact in item.get("impacts", []):
            node_id = _link(str(impact["entity"]), node_ids, aliases)
            if node_id is None:
                # entity-linking threshold: unmatched → excluded from Predict
                log.debug("entity unlinked", extra={"entity": impact.get("entity")})
                continue
            linked += 1
            polarity = float(impact.get("polarity", 0.0))
            contribution = polarity * weight * decay
            bucket = acc.setdefault(
                node_id, {"momentum": 0.0, "evidence": []}
            )
            bucket["momentum"] += contribution
            bucket["evidence"].append(
                {
                    "headline": item["headline"],
                    "source": item.get("source", ""),
                    "reason": impact.get("reason", ""),
                    "polarity": polarity,
                }
            )

    out_nodes: dict[str, Any] = {}
    for node_id, bucket in acc.items():
        mom = bucket["momentum"]
        out_nodes[node_id] = {
            "name": names.get(node_id, node_id),
            "momentum": round(mom, 4),
            "expansion_ratio": round(m.expansion_ratio(mom), 4),
            "expected_delta_pct": m.expected_delta_pct(mom),
            "direction": "expand" if mom > 0 else "contract" if mom < 0 else "flat",
            "evidence": sorted(bucket["evidence"], key=lambda e: -abs(e["polarity"]))[:5],
            "engine": engine_label,
        }

    payload = {
        "theme_id": theme_id,
        "news_count": len(news),
        "links": linked,
        "nodes": out_nodes,
    }
    write_momentum(theme_id, payload)
    log.info("momentum cached", extra={"theme_id": theme_id, "links": linked,
                                       "scored_nodes": len(out_nodes)})
    return payload


def load_momentum(theme_id: str) -> dict[str, Any]:
    cached = read_momentum(theme_id)
    if cached is None:
        log.debug("momentum cache miss", extra={"theme_id": theme_id})
        return {"theme_id": theme_id, "news_count": 0, "links": 0, "nodes": {}}
    return cached
