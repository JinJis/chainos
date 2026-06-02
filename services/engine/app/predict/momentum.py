"""Momentum scoring math (PRD §8.3).

momentum(node) = Σ_news [ polarity · source_weight · recency_decay ]
expansion_ratio = clamp(1.0 + k · normalize(momentum), 0.7, 1.4)
"""
from __future__ import annotations

import math

HALF_LIFE_HOURS = 12.0
K = 0.4  # visual sensitivity
SCALE = 2.0  # momentum → normalize scale
MAX_DELTA_PCT = 18.0


def recency_decay(hours_ago: float, half_life: float = HALF_LIFE_HOURS) -> float:
    return 0.5 ** (max(0.0, hours_ago) / half_life)


def normalize(momentum: float) -> float:
    """Squash to [-1, 1]."""
    return math.tanh(momentum / SCALE)


def expansion_ratio(momentum: float) -> float:
    ratio = 1.0 + K * normalize(momentum)
    return max(0.7, min(1.4, ratio))


def expected_delta_pct(momentum: float) -> float:
    return round(normalize(momentum) * MAX_DELTA_PCT, 1)
