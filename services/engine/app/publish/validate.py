"""The validation gate (CLAUDE.md §1.3, PRD §6.2 Step 6).

Every exposed figure must carry `source_id` + `base_date` + `next_update`, and the
referenced Source must exist. A theme that fails ANY check cannot be published."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ..graph import StagingGraphRepo
from ..graph_schema import (
    QUANTITATIVE_EDGE_FIELDS,
    QUANTITATIVE_EDGE_TYPES,
)
from ..logging_config import get_logger

log = get_logger("publish.validate")

_REQUIRED_TRUST = ("source_id", "base_date", "next_update", "confidence")


@dataclass
class Failure:
    ref: str
    kind: str  # edge | node
    missing: list[str]


@dataclass
class ValidationReport:
    ok: bool
    total: int
    passed: int
    failures: list[Failure] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "total": self.total,
            "passed": self.passed,
            "failed": len(self.failures),
            "failures": [
                {"ref": f.ref, "kind": f.kind, "missing": f.missing} for f in self.failures
            ],
        }


def validate_theme(theme_id: str, repo: StagingGraphRepo | None = None) -> ValidationReport:
    repo = repo or StagingGraphRepo()
    graph = repo.export_theme(theme_id)
    source_ids = {n["id"] for n in graph["nodes"] if n.get("label") == "Source"}

    total = 0
    passed = 0
    failures: list[Failure] = []

    # ── quantitative edges ────────────────────────────────────────────────────
    for e in graph["edges"]:
        etype = e.get("type")
        if etype not in QUANTITATIVE_EDGE_TYPES:
            continue
        total += 1
        missing: list[str] = []

        value_fields = QUANTITATIVE_EDGE_FIELDS.get(etype, [])
        if value_fields and all(e.get(f) is None for f in value_fields):
            missing.append(f"value ({'/'.join(value_fields)})")

        for key in _REQUIRED_TRUST:
            if not e.get(key):
                missing.append(key)
        sid = e.get("source_id")
        if sid and sid not in source_ids:
            missing.append(f"source[{sid}] not found")

        ref = f"{etype} {e.get('from')}→{e.get('to')} {e.get('product_ref', '')}".strip()
        if missing:
            failures.append(Failure(ref=ref, kind="edge", missing=missing))
        else:
            passed += 1

    # ── company nodes (market cap / as-of badges) ─────────────────────────────
    for n in graph["nodes"]:
        if n.get("label") != "Company":
            continue
        total += 1
        missing = []
        for key in ("base_date", "next_update"):
            if not n.get(key):
                missing.append(key)
        if n.get("market_cap") is None:
            missing.append("market_cap")
        ref = f"Company {n.get('id')}"
        if missing:
            failures.append(Failure(ref=ref, kind="node", missing=missing))
        else:
            passed += 1

    report = ValidationReport(ok=not failures, total=total, passed=passed, failures=failures)
    log.info(
        "validation gate",
        extra={"theme_id": theme_id, "ok": report.ok, "passed": passed, "total": total,
               "failed": len(failures)},
    )
    for f in failures:
        log.debug("gate failure", extra={"ref": f.ref, "missing": ",".join(f.missing)})
    return report
