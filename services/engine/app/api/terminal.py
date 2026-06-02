"""Terminal (user) read API — PRODUCTION ONLY.

Every handler here constructs a ProductionGraphRepo and nothing else. This is the
code-level enforcement of invariant #1: user-facing reads can never touch Staging
or agent intermediates (CLAUDE.md §1, PRD §4)."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import select

from ..db import session_scope
from ..graph import ProductionGraphRepo
from ..graph_schema import FLOW_VIEW_EDGES
from ..logging_config import get_logger
from ..models import Theme

router = APIRouter(prefix="/terminal", tags=["terminal"])
log = get_logger("api.terminal")

# Company↔company flows that the macro canvas can render.
_MACRO_EDGE_TYPES = ["SUPPLIES", "REVENUE_FLOW", "INVESTS_IN", "COMPETES_WITH"]


@router.get("/themes")
def published_themes() -> list[dict]:
    """Only published themes are visible to users."""
    with session_scope() as s:
        themes = s.scalars(
            select(Theme).where(Theme.status == "published").order_by(Theme.name)
        ).all()
        log.debug("published themes", extra={"count": len(themes)})
        return [
            {"id": t.id, "name": t.name, "version": t.version, "depth_max": t.depth_max}
            for t in themes
        ]


@router.get("/graph/{theme_id}")
def macro_graph(
    theme_id: str,
    depth: int | None = Query(default=None),
    views: list[str] | None = Query(default=None),
) -> dict:
    """Macro view: Company nodes (size = market cap) + the company↔company flows
    for the selected views, filtered by depth. Production only."""
    edge_types = (
        sorted({et for v in views for et in FLOW_VIEW_EDGES.get(v, [])})
        if views
        else _MACRO_EDGE_TYPES
    )
    repo = ProductionGraphRepo()
    graph = repo.get_graph(
        theme_id, depth=depth, edge_types=edge_types, labels=["Company"]
    )
    log.debug(
        "macro graph",
        extra={"theme_id": theme_id, "depth": depth, "views": views,
               "nodes": len(graph["nodes"]), "edges": len(graph["edges"])},
    )
    if not graph["nodes"]:
        log.info("macro graph empty (theme not published?)", extra={"theme_id": theme_id})
    return graph


@router.get("/companies/{theme_id}/{company_id}")
def company_detail(theme_id: str, company_id: str) -> dict:
    """Micro view (drill-down): divisions → products + key customers. Production only."""
    detail = ProductionGraphRepo().get_company_detail(theme_id, company_id)
    if detail is None:
        log.warning("company not found in production",
                    extra={"theme_id": theme_id, "company_id": company_id})
        raise HTTPException(404, "company not found in production")
    log.debug("company detail", extra={"theme_id": theme_id, "company_id": company_id,
                                       "divisions": len(detail["divisions"]),
                                       "customers": len(detail["customers"])})
    return detail
