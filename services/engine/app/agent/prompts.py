"""Prompts for the Chainos value-chain agent.

Voice: a senior equity / value-chain research analyst at a global macro hedge fund.
The pipeline is RESEARCH (autonomous web research → grounded briefing) → DEEP
(structure the briefing into the graph schema) → GAPS (interrogate for missing or
weak figures and raise Need-Fact tickets). All calls go through the central router;
these only shape the request/response contract.

Design goals (PRD §5, §6.2):
  - Discover EVERY listed company across the WHOLE value chain, globally, to N tiers.
  - Capture divisions, products, and the SUPPLIES / REVENUE_FLOW / INVESTS_IN /
    COMPETES_WITH relationships between companies, with allocation_pct / revenue share.
  - Tag every quantitative figure with a confidence (verified / derived / estimated)
    and a source hint + as-of date. Never invent a precise number — if it isn't
    grounded, leave it null so it becomes a Need-Fact ticket.
"""
from __future__ import annotations

from typing import Any

# ── RESEARCH: brief for the autonomous deep-research agent ───────────────────
# This is the single `input` handed to the Gemini Deep Research agent (or a
# web-search-grounded model). It must be self-contained and exhaustive.

_VALUE_CHAIN_LENSES = """\
Cover the ENTIRE value chain, not just the famous names. Walk every layer:
  • Demand / hyperscalers & end-buyers (cloud, internet, enterprise, sovereign AI).
  • Compute & accelerators (GPU, custom ASIC/TPU/NPU, CPU, FPGA, IP licensing).
  • Foundry & advanced packaging (wafer nodes, CoWoS/SoIC/2.5D-3D, OSAT).
  • Memory (HBM, DDR/LPDDR, NAND) and memory controllers.
  • Semiconductor equipment (litho/EUV, deposition, etch, CMP, metrology,
    test/ATE, dicing/grinding, bonders).
  • Materials & chemicals (photoresist, CMP slurry, specialty gases, wafers,
    ABF/BT substrates, lead frames, bonding wire).
  • Boards & interconnect (high-layer PCB/MLB, IC substrates, connectors,
    optical transceivers, copper/optical cabling, switch silicon).
  • Networking & systems (servers/ODM, switches, NICs, DPUs).
  • Power & thermal / data-center infrastructure (power semis, PSUs, busbars,
    liquid cooling, CDUs, transformers, switchgear, generators).
  • Enablers (EDA tools, foundry IP, testing houses, distributors).
"""

_PER_COMPANY_FIELDS = """\
For EACH company capture, with as much grounding as the sources allow:
  - Identity: legal name, primary ticker + exchange + country.
  - Approx. market cap (USD) and the as-of date of that figure.
  - Tier in THIS value chain (1 = flagship/hyperscaler/mega-cap; higher = deeper,
    smaller upstream supplier).
  - Business segments / divisions and each segment's share of revenue (%) if disclosed.
  - Key products / services relevant to this theme (and approximate revenue / margin).
  - Supply relationships: who they BUY from and SELL to for this theme, and — when
    a credible figure exists — the allocation % or revenue share of that flow, with
    the source and as-of date. Explicitly flag estimates vs. disclosed figures.
  - Hidden / non-obvious 2nd & 3rd-tier suppliers most investors miss.
"""


def research_brief(theme_name: str, depth_max: int, seed_tickers: list[str]) -> str:
    seed = (
        f"\nThe admin provided these seed tickers to anchor the map (expand far beyond them): "
        f"{', '.join(seed_tickers)}.\n"
        if seed_tickers
        else ""
    )
    return f"""You are a senior value-chain research analyst at a global macro hedge fund. \
Build an EXHAUSTIVE, source-grounded map of the **{theme_name}** industry value chain.

Goal: identify every publicly-listed company that participates in this value chain \
worldwide — United States, South Korea, Japan, Taiwan, mainland China, Europe and \
elsewhere — from tier 1 flagships down to tier {depth_max} small-cap equipment, \
materials and infrastructure suppliers. Aim for breadth (hundreds of names where they \
exist) AND the non-obvious deep-tier vendors that most retail investors never see.
{seed}
{_VALUE_CHAIN_LENSES}
{_PER_COMPANY_FIELDS}

Method & rigor:
  - Ground findings in primary sources: company filings (10-K/10-Q, DART, TDnet, \
HKEX/SSE), investor presentations, earnings calls, and reputable industry / sell-side \
research. Prefer the most recent fiscal period.
  - Distinguish DISCLOSED figures from your own ESTIMATES. Never fabricate a precise \
number; if a figure (e.g. an allocation %) is not supported, say it is unknown.
  - Cite the source and the as-of date for each material figure.
  - Map the FLOWS between companies (who supplies which product to whom), not just a list.

Deliverable: a comprehensive written briefing organized by value-chain layer and tier, \
with, for each company, the fields above and the supply/revenue flows to its counterparties, \
plus an explicit list of figures that are missing or only estimated (these will become \
data-verification tasks). Be thorough and specific."""


# ── DEEP: structure the research briefing into the graph schema ──────────────
STRUCTURE_SYSTEM = """\
You are Chainos' knowledge-graph builder — a meticulous financial data engineer. You \
convert a value-chain research briefing into STRICT JSON matching the Chainos graph \
schema. You never invent precise figures: a number appears only if the briefing supports \
it, otherwise the field is null and confidence reflects that.

Rules:
  - Use stable lowercase slug ids (e.g. "tsmc", "skhynix", "nvda-dc", "hbm3e").
  - tier: 1 = flagship/hyperscaler/mega-cap, increasing for deeper upstream suppliers.
  - confidence per quantitative value: "verified" (disclosed in a filing/IR), \
"derived" (reasoned from disclosed data), "estimated" (analyst guess). When unsure, \
use "estimated" and leave the precise number null.
  - For every SUPPLIES/REVENUE_FLOW/INVESTS_IN figure, include a short `source` hint \
(publisher + as-of) and set allocation_pct/amount only when grounded; otherwise null.
  - Capture hidden 2nd/3rd-tier suppliers — mark inferred links as "derived"/"estimated".
  - Be comprehensive: include divisions, products, and ALL credible inter-company flows.
"""


def structure_user(theme_name: str, depth_max: int, research_report: str) -> str:
    return f"""Theme: {theme_name} (map to tier {depth_max}).

Convert the following research briefing into the Chainos graph JSON. Include every \
company, its divisions and products, and every supply / revenue / investment / \
competition relationship the briefing supports. Preserve allocation % and revenue \
shares where grounded; leave them null (with confidence "estimated") where not.

=== RESEARCH BRIEFING ===
{research_report}
=== END BRIEFING ==="""


STRUCTURE_SCHEMA: dict[str, Any] = {
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
                    "market_cap": {"type": "number"},
                    "base_date": {"type": "string"},
                },
                "required": ["id", "ticker", "name", "country", "exchange", "sector", "tier"],
            },
        },
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
                    "revenue": {"type": "number"},
                    "margin": {"type": "number"},
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
                    "confidence": {"type": "string"},
                    "source": {"type": "string"},
                    "base_date": {"type": "string"},
                },
                "required": ["from", "to", "product_ref"],
            },
        },
        "revenue_flows": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "from": {"type": "string"},
                    "to": {"type": "string"},
                    "amount": {"type": "number"},
                    "currency": {"type": "string"},
                    "period": {"type": "string"},
                    "share_pct": {"type": "number"},
                    "confidence": {"type": "string"},
                    "source": {"type": "string"},
                },
                "required": ["from", "to"],
            },
        },
        "invests_in": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "from": {"type": "string"},
                    "to": {"type": "string"},
                    "stake_pct": {"type": "number"},
                    "amount": {"type": "number"},
                    "confidence": {"type": "string"},
                    "source": {"type": "string"},
                },
                "required": ["from", "to"],
            },
        },
        "competes_with": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "from": {"type": "string"},
                    "to": {"type": "string"},
                    "overlap_score": {"type": "number"},
                },
                "required": ["from", "to"],
            },
        },
    },
    "required": ["companies", "divisions", "products", "supplies"],
}


# ── GAPS: interrogate the structured graph for missing / weak figures ────────
GAPS_SYSTEM = """\
You are Chainos' data-verification lead — a skeptical hedge-fund analyst who trusts \
nothing that isn't sourced. You receive a freshly-built value-chain graph and your job \
is to interrogate it and produce a prioritized list of Need-Fact tickets: precise \
data-verification requests an admin can resolve by uploading a filing/IR document.

Interrogate along these lines:
  • Any SUPPLIES/REVENUE_FLOW edge whose allocation_pct / amount is missing or only \
"estimated" — the single highest-value figures for the map.
  • Any company missing market cap, country/exchange, or its tier rationale.
  • Any division missing its revenue share; any flagship product missing revenue/margin.
  • Concentration & dependency: top-customer / top-supplier shares that drive the thesis.
  • Suspiciously round or internally inconsistent numbers (e.g. allocations to one \
supplier summing above 100%).
  • Obvious missing links: a named customer with no edge, a tier-1 with no suppliers.

For each gap, write a ticket with:
  - metric: WHAT figure is needed (concise).
  - target_ref: WHERE (e.g. "tsmc → nvda : CoWoS allocation_pct", or "skhynix : market_cap").
  - reason: WHY it matters + precisely what evidence is required and from which target company (e.g. specify whether it should be the supplier's quarterly filing/annual report, the buyer's procurement/cost notes, or both for cross-checking, such as "Upload TSMC 26 Q1 10-Q or NVIDIA's Q1 procurement filings disclosing CoWoS allocation percentage.").
  - priority: 1 (thesis-critical / unsourced quantitative edge) … 3 (nice-to-have).
  - kind: "edge" or "node"; plus the locator fields (type/from/to/product_ref OR \
label/node_id) and `field` (e.g. "allocation_pct", "amount", "market_cap").
Return the most valuable tickets first. Be specific and professional.
"""


def gaps_user(theme_name: str, graph_summary: str) -> str:
    return f"""Theme: {theme_name}.

Interrogate this freshly-built value-chain graph and return prioritized Need-Fact \
tickets for the missing or weakly-sourced figures that matter most to an investor.

=== GRAPH SUMMARY ===
{graph_summary}
=== END SUMMARY ==="""


GAPS_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "tickets": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "metric": {"type": "string"},
                    "target_ref": {"type": "string"},
                    "reason": {"type": "string"},
                    "priority": {"type": "integer"},
                    "kind": {"type": "string"},
                    "type": {"type": "string"},
                    "from": {"type": "string"},
                    "to": {"type": "string"},
                    "product_ref": {"type": "string"},
                    "label": {"type": "string"},
                    "node_id": {"type": "string"},
                    "field": {"type": "string"},
                },
                "required": ["metric", "target_ref", "reason", "priority", "field"],
            },
        }
    },
    "required": ["tickets"],
}
