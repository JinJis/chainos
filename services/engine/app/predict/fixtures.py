"""Sample real-time news for the AI Data Centers theme, so Predict is demoable
without a live news feed. Each item carries per-entity impacts (what a LOW model
would extract: which node, what polarity, why). Hidden beneficiaries (e.g.
water-cooling substitution) are included to show the 'discover the beneficiary'
effect described in PRD §7 Step 4."""
from __future__ import annotations

from typing import Any

SAMPLE_NEWS: list[dict[str, Any]] = [
    {
        "id": "n1",
        "headline": "Nvidia next-gen chip thermal issues spark water-cooling substitution demand",
        "source": "Reuters",
        "weight": 1.0,
        "hours_ago": 3,
        "impacts": [
            {"entity": "nvda", "polarity": -0.35, "reason": "thermal concerns on next-gen GPUs"},
            {"entity": "vrt", "polarity": 0.7, "reason": "water-cooling substitution demand"},
        ],
    },
    {
        "id": "n2",
        "headline": "SK hynix HBM3E 12-Hi yields ahead of schedule; lead customer raises orders",
        "source": "DigiTimes",
        "weight": 0.9,
        "hours_ago": 6,
        "impacts": [
            {"entity": "skhynix", "polarity": 0.8, "reason": "HBM yield ramp + order increase"},
            {"entity": "nvda", "polarity": 0.2, "reason": "secured memory supply"},
        ],
    },
    {
        "id": "n3",
        "headline": "TSMC expands CoWoS advanced-packaging capacity 2x for AI accelerators",
        "source": "Bloomberg",
        "weight": 1.0,
        "hours_ago": 10,
        "impacts": [
            {"entity": "tsmc", "polarity": 0.6, "reason": "CoWoS capacity expansion"},
            {"entity": "disco", "polarity": 0.5, "reason": "more dicing/grinding tools needed"},
        ],
    },
    {
        "id": "n4",
        "headline": "Samsung HBM qualification at top GPU vendor reportedly slips a quarter",
        "source": "Korea Economic Daily",
        "weight": 0.85,
        "hours_ago": 8,
        "impacts": [
            {"entity": "samsung", "polarity": -0.5, "reason": "HBM qualification delay"},
            {"entity": "skhynix", "polarity": 0.3, "reason": "share gains from rival's delay"},
        ],
    },
    {
        "id": "n5",
        "headline": "Hyperscaler capex guidance raised; AI data-center buildout accelerates",
        "source": "WSJ",
        "weight": 0.95,
        "hours_ago": 14,
        "impacts": [
            {"entity": "msft", "polarity": 0.4, "reason": "raised AI capex"},
            {"entity": "nvda", "polarity": 0.45, "reason": "more GPU demand"},
            {"entity": "vrt", "polarity": 0.4, "reason": "more cooling/power infra"},
        ],
    },
    {
        "id": "n6",
        "headline": "Custom ASIC momentum: Alphabet deepens TPU program with Broadcom",
        "source": "The Information",
        "weight": 0.8,
        "hours_ago": 5,
        "impacts": [
            {"entity": "avgo", "polarity": 0.6, "reason": "expanded TPU ASIC engagement"},
            {"entity": "googl", "polarity": 0.25, "reason": "custom silicon cost leverage"},
            {"entity": "nvda", "polarity": -0.15, "reason": "in-house accelerator substitution"},
        ],
    },
]
