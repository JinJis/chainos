"""Prompt + JSON-schema builders for the agent's LLM calls. All calls go through
the central router; these only shape the request/response contract."""
from __future__ import annotations

from typing import Any

RESEARCH_SYSTEM = (
    "You are Chainos' value-chain research agent. Given an industry theme, "
    "discover LISTED companies worldwide (KR/US/JP/CN/TW...) that participate in "
    "its value chain, from mega-cap leaders down to lower-tier equipment makers. "
    "Assign each a `tier` (1 = mega-cap/flagship, higher = smaller upstream vendor)."
)

RESEARCH_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "companies": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "string"},
                    "ticker": {"type": "string"},
                    "name": {"type": "string"},
                    "country": {"type": "string"},
                    "exchange": {"type": "string"},
                    "sector": {"type": "string"},
                    "tier": {"type": "integer"},
                },
                "required": ["id", "ticker", "name", "country", "exchange", "sector", "tier"],
            },
        }
    },
    "required": ["companies"],
}

DEEP_SYSTEM = (
    "You are Chainos' deep value-chain reasoner. For the given companies, lay out "
    "the value each provides: divisions, products, and the SUPPLIES relationships "
    "(who ships which product to whom, with an allocation_pct when known). Infer "
    "hidden 2nd/3rd-tier vendors. If you cannot ground a figure in a disclosure, "
    "leave allocation_pct null — it will become a Need-Fact request."
)

DEEP_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "divisions": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "string"},
                    "name": {"type": "string"},
                    "parent_company": {"type": "string"},
                    "revenue_share": {"type": "number"},
                },
                "required": ["id", "name", "parent_company"],
            },
        },
        "products": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "string"},
                    "name": {"type": "string"},
                    "category": {"type": "string"},
                    "division": {"type": "string"},
                },
                "required": ["id", "name", "category"],
            },
        },
        "supplies": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "from": {"type": "string"},
                    "to": {"type": "string"},
                    "product_ref": {"type": "string"},
                    "allocation_pct": {"type": "number"},
                },
                "required": ["from", "to", "product_ref"],
            },
        },
    },
    "required": ["divisions", "products", "supplies"],
}


def research_user(theme_name: str, depth_max: int, seed_tickers: list[str]) -> str:
    seed = f" Seed tickers to include: {', '.join(seed_tickers)}." if seed_tickers else ""
    return (
        f"Industry theme: {theme_name}. Explore to depth {depth_max} "
        f"(tier 1..{depth_max}).{seed} Return the constituent companies."
    )


def deep_user(theme_name: str, candidates: list[dict[str, Any]]) -> str:
    names = ", ".join(f"{c['name']} ({c.get('ticker', '')})" for c in candidates)
    return (
        f"Theme: {theme_name}. Companies: {names}. "
        "Produce divisions, products, and SUPPLIES edges among these companies."
    )
