"""Staging → Production publish (M3). The ONLY path that writes Production.

Publish is gated: it runs the validation gate first and refuses on any failure.
The copy is an atomic snapshot replace, so the Terminal never sees a half-applied
graph. Publish is invoked by an explicit admin action — never automatically."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ..graph import ProductionGraphRepo, StagingGraphRepo
from ..logging_config import get_logger
from .validate import ValidationReport, validate_theme

log = get_logger("publish")


class PublishBlocked(Exception):
    def __init__(self, report: ValidationReport) -> None:
        super().__init__("validation gate failed")
        self.report = report


@dataclass
class PublishResult:
    counts: dict[str, int]
    report: ValidationReport


def publish_graph(theme_id: str) -> PublishResult:
    """Validate Staging, then atomically snapshot it into Production."""
    log.info("publish requested", extra={"theme_id": theme_id})
    report = validate_theme(theme_id)
    if not report.ok:
        log.warning(
            "publish BLOCKED by validation gate",
            extra={"theme_id": theme_id, "failed": len(report.failures)},
        )
        raise PublishBlocked(report)
    export = StagingGraphRepo().export_theme(theme_id)
    counts = ProductionGraphRepo().replace_theme(theme_id, export["nodes"], export["edges"])
    log.info("publish DONE", extra={"theme_id": theme_id, **counts})
    return PublishResult(counts=counts, report=report)


def _edge_key(e: dict[str, Any]) -> str:
    return f"{e.get('type')}:{e.get('from')}:{e.get('to')}:{e.get('product_ref', e.get('period', ''))}"


def diff_theme(theme_id: str) -> dict[str, Any]:
    """Preview what Publish would change: nodes/edges added vs removed."""
    staging = StagingGraphRepo().export_theme(theme_id)
    production = ProductionGraphRepo().export_theme(theme_id)

    st_nodes = {n["id"] for n in staging["nodes"]}
    pr_nodes = {n["id"] for n in production["nodes"]}
    st_edges = {_edge_key(e) for e in staging["edges"]}
    pr_edges = {_edge_key(e) for e in production["edges"]}

    return {
        "staging_counts": {"nodes": len(st_nodes), "edges": len(staging["edges"])},
        "production_counts": {"nodes": len(pr_nodes), "edges": len(production["edges"])},
        "added_nodes": sorted(st_nodes - pr_nodes)[:50],
        "removed_nodes": sorted(pr_nodes - st_nodes)[:50],
        "added_edges": len(st_edges - pr_edges),
        "removed_edges": len(pr_edges - st_edges),
    }
