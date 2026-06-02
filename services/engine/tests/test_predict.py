"""Predict momentum math tests (pure, no DB/Redis)."""
from __future__ import annotations

from app.predict import momentum as m


def test_recency_decay_half_life() -> None:
    assert m.recency_decay(0) == 1.0
    assert abs(m.recency_decay(12) - 0.5) < 1e-9
    assert m.recency_decay(24) < m.recency_decay(12)


def test_expansion_ratio_is_clamped() -> None:
    assert m.expansion_ratio(0) == 1.0
    assert m.expansion_ratio(1000) <= 1.4
    assert m.expansion_ratio(-1000) >= 0.7
    # positive momentum expands, negative contracts
    assert m.expansion_ratio(1.0) > 1.0
    assert m.expansion_ratio(-1.0) < 1.0


def test_expected_delta_sign_tracks_momentum() -> None:
    assert m.expected_delta_pct(0.5) > 0
    assert m.expected_delta_pct(-0.5) < 0
    assert abs(m.expected_delta_pct(2.0)) <= m.MAX_DELTA_PCT
