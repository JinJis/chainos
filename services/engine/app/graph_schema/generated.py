# ─────────────────────────────────────────────────────────────────────────────
# AUTO-GENERATED from packages/graph-schema/src/spec.ts. DO NOT EDIT BY HAND.
# Regenerate: pnpm --filter @chainos/graph-schema gen
# ─────────────────────────────────────────────────────────────────────────────
from __future__ import annotations

from enum import Enum
from typing import Literal, Optional, Union

from pydantic import BaseModel, ConfigDict, Field


class Confidence(str, Enum):
    VERIFIED = "verified"
    DERIVED = "derived"
    ESTIMATED = "estimated"


class SourceType(str, Enum):
    FILING = "filing"
    IR = "IR"
    REPORT = "report"
    NEWS = "news"


class SupplyDirection(str, Enum):
    UPSTREAM = "upstream"
    DOWNSTREAM = "downstream"


class _Base(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")


class TrustMeta(_Base):
    base_date: str
    next_update: str
    confidence: Confidence


class Theme(_Base):
    """Industry / theme, e.g. "AI Data Centers"."""
    label: Literal["Theme"] = "Theme"
    id: str
    name: str
    depth_max: int
    version: int
    published_at: Optional[str] = Field(default=None)


class Company(_Base):
    """A listed company. Node size in the Terminal binds to market_cap."""
    label: Literal["Company"] = "Company"
    id: str
    ticker: str
    name: str
    country: str
    exchange: str
    sector: str
    tier: int
    market_cap: Optional[float] = Field(default=None)
    base_date: str
    next_update: str


class Division(_Base):
    """A business unit, e.g. Samsung DS."""
    label: Literal["Division"] = "Division"
    id: str
    name: str
    parent_company: str
    revenue_share: Optional[float] = Field(default=None)


class Product(_Base):
    """A product / service, e.g. HBM3E 12-Hi."""
    label: Literal["Product"] = "Product"
    id: str
    name: str
    category: str
    unit_price: Optional[float] = Field(default=None)
    revenue: Optional[float] = Field(default=None)
    margin: Optional[float] = Field(default=None)


class Source(_Base):
    """Evidence backing a figure. Every number links to one via SOURCED_FROM."""
    label: Literal["Source"] = "Source"
    id: str
    type: SourceType
    url: str
    publisher: str
    as_of_date: str
    confidence: Confidence


GraphNode = Union[Theme, Company, Division, Product, Source]


class HasDivision(_Base):
    """Company owns a division. (Company -> Division)"""
    type: Literal["HAS_DIVISION"] = "HAS_DIVISION"
    from_: str = Field(alias="from")
    to: str
    base_date: Optional[str] = None
    next_update: Optional[str] = None
    confidence: Optional[Confidence] = None
    source_id: Optional[str] = None


class Produces(_Base):
    """Division produces a product. (Division -> Product)"""
    type: Literal["PRODUCES"] = "PRODUCES"
    from_: str = Field(alias="from")
    to: str
    base_date: Optional[str] = None
    next_update: Optional[str] = None
    confidence: Optional[Confidence] = None
    source_id: Optional[str] = None
    capacity: Optional[str] = Field(default=None)
    yield_: Optional[float] = Field(default=None, alias="yield")


class Supplies(_Base):
    """Supply relationship (product flow) between two companies. (Company -> Company)"""
    type: Literal["SUPPLIES"] = "SUPPLIES"
    from_: str = Field(alias="from")
    to: str
    base_date: Optional[str] = None
    next_update: Optional[str] = None
    confidence: Optional[Confidence] = None
    source_id: Optional[str] = None
    product_ref: str
    allocation_pct: float
    direction: Optional[SupplyDirection] = Field(default=None)


class RevenueFlow(_Base):
    """Flow of revenue / money between two companies. (Company -> Company)"""
    type: Literal["REVENUE_FLOW"] = "REVENUE_FLOW"
    from_: str = Field(alias="from")
    to: str
    base_date: Optional[str] = None
    next_update: Optional[str] = None
    confidence: Optional[Confidence] = None
    source_id: Optional[str] = None
    amount: float
    currency: str
    period: str
    share_pct: Optional[float] = Field(default=None)


class InvestsIn(_Base):
    """Equity stake / CAPEX from one company into another. (Company -> Company)"""
    type: Literal["INVESTS_IN"] = "INVESTS_IN"
    from_: str = Field(alias="from")
    to: str
    base_date: Optional[str] = None
    next_update: Optional[str] = None
    confidence: Optional[Confidence] = None
    source_id: Optional[str] = None
    stake_pct: Optional[float] = Field(default=None)
    amount: Optional[float] = Field(default=None)


class CompetesWith(_Base):
    """Competition between two companies (undirected in meaning). (Company -> Company)"""
    type: Literal["COMPETES_WITH"] = "COMPETES_WITH"
    from_: str = Field(alias="from")
    to: str
    base_date: Optional[str] = None
    next_update: Optional[str] = None
    confidence: Optional[Confidence] = None
    source_id: Optional[str] = None
    overlap_score: Optional[float] = Field(default=None)


class SourcedFrom(_Base):
    """Links any numeric edge/value to its evidence Source. (Edge -> Source)"""
    type: Literal["SOURCED_FROM"] = "SOURCED_FROM"
    from_: str = Field(alias="from")
    to: str
    base_date: Optional[str] = None
    next_update: Optional[str] = None
    confidence: Optional[Confidence] = None
    source_id: Optional[str] = None
    extracted_value: str
    extracted_by: str


NODE_LABELS = ["Theme", "Company", "Division", "Product", "Source"]
EDGE_TYPES = ["HAS_DIVISION", "PRODUCES", "SUPPLIES", "REVENUE_FLOW", "INVESTS_IN", "COMPETES_WITH", "SOURCED_FROM"]
QUANTITATIVE_EDGE_TYPES = ["SUPPLIES", "REVENUE_FLOW", "INVESTS_IN"]

QUANTITATIVE_NODE_FIELDS = {
    "Company": ["market_cap"],
    "Division": ["revenue_share"],
    "Product": ["unit_price", "revenue", "margin"],
}

QUANTITATIVE_EDGE_FIELDS = {
    "PRODUCES": ["yield"],
    "SUPPLIES": ["allocation_pct"],
    "REVENUE_FLOW": ["amount", "share_pct"],
    "INVESTS_IN": ["stake_pct", "amount"],
}

FLOW_VIEWS = ["supply", "revenue", "investment", "cost", "rnd"]
FLOW_VIEW_EDGES = {
    "supply": ["SUPPLIES"],
    "revenue": ["REVENUE_FLOW"],
    "investment": ["INVESTS_IN"],
    "cost": ["SUPPLIES"],
    "rnd": ["PRODUCES"],
}
