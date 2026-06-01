"""Verification step: turn uploaded evidence into a locked, sourced figure.

MEDIUM extracts the exact value + span from the disclosure; LOW normalizes it to
the schema. The result is written back into Staging with a SOURCED_FROM link
(`extracted_value` + `extracted_by`), satisfying the trust contract so the figure
can pass the publish validation gate (PRD §6.2 Step 4, CLAUDE.md §4)."""
from __future__ import annotations

import re
from typing import Any

from ..config import get_settings
from ..graph import StagingGraphRepo
from ..llm import Provider, Tier, get_router
from ..seed.dataset import NEXT_UPDATE

EXTRACT_SYSTEM = (
    "You extract a single quantitative figure from a disclosure. Return the exact "
    "numeric value and the verbatim span you took it from. Do not infer — if the "
    "figure is not explicitly present, return value=null."
)

EXTRACT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "value": {"type": "number"},
        "span": {"type": "string"},
        "unit": {"type": "string"},
    },
    "required": ["value", "span"],
}

_PCT = re.compile(r"(\d+(?:\.\d+)?)\s*%")
_NUM = re.compile(r"(\d+(?:[.,]\d+)?)")


def _regex_value(text: str, field: str) -> tuple[float | None, str | None]:
    """Deterministic fallback used offline or when the model returns nothing."""
    if not text:
        return None, None
    if field.endswith("pct"):
        m = _PCT.search(text)
        if m:
            return float(m.group(1)), m.group(0)
    m = _NUM.search(text.replace(",", ""))
    if m:
        return float(m.group(1)), m.group(0)
    return None, None


def parse_evidence(
    *, content_text: str | None, field: str, provider: Provider | None = None
) -> dict[str, Any]:
    """MEDIUM extraction + LOW normalization. Returns a preview the admin approves."""
    router = get_router()
    settings = get_settings()
    text = content_text or ""
    resp = router.prompt(
        Tier.MEDIUM,
        f"Field to extract: {field}.\n\nDisclosure text:\n{text[:6000]}",
        system=EXTRACT_SYSTEM,
        provider=provider,
        json_schema=EXTRACT_SCHEMA,
    )
    extracted_by = resp.model
    value: float | None = None
    span: str | None = None
    data = resp.data if isinstance(resp.data, dict) else None
    # Live models do the extraction. Offline, the deterministic provider can't
    # read the document, so we ground the figure in a regex over the pasted text.
    if not settings.offline and data and isinstance(data.get("value"), int | float):
        value = float(data["value"])
        span = str(data.get("span") or "")
    if value is None:
        value, span = _regex_value(text, field)
    return {
        "field": field,
        "value": value,
        "span": span or "",
        "extracted_by": extracted_by,
        "confidence": "verified" if value is not None else "estimated",
        "found": value is not None,
    }


def apply_lock(
    *,
    theme_id: str,
    payload: dict[str, Any],
    source_meta: dict[str, Any],
    preview: dict[str, Any],
    repo: StagingGraphRepo | None = None,
) -> dict[str, Any]:
    """Create the Source node and write the locked value + trust meta into Staging."""
    repo = repo or StagingGraphRepo()
    source_id = source_meta["id"]
    base_date = source_meta.get("as_of_date") or "unspecified"
    confidence = source_meta.get("confidence") or preview.get("confidence", "verified")
    value = preview["value"]
    field = payload["field"]

    repo.upsert_source_node(
        theme_id,
        {
            "id": source_id,
            "type": source_meta.get("type", "filing"),
            "url": source_meta.get("url", ""),
            "publisher": source_meta.get("publisher", ""),
            "as_of_date": base_date,
            "confidence": confidence,
        },
    )

    trust = {
        "source_id": source_id,
        "base_date": base_date,
        "next_update": NEXT_UPDATE,
        "confidence": confidence,
        "extracted_value": preview.get("span", ""),
        "extracted_by": preview.get("extracted_by", ""),
    }
    if payload["kind"] == "edge":
        updated = repo.lock_edge(theme_id, payload, {field: value, **trust})
        return {"locked": updated, "field": field, "value": value, "source_id": source_id}

    repo.lock_node_field(
        theme_id,
        payload["label"],
        payload["node_id"],
        {field: value, **trust},
        source_id=source_id,
    )
    return {"locked": 1, "field": field, "value": value, "source_id": source_id}
