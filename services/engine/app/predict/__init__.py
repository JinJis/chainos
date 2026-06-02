"""Predict: real-time, news-driven momentum simulation (PRD §8, §7 Step 4).

Reads Production to know the nodes, scores incoming news into a per-node momentum,
and caches the result in Redis. It NEVER writes Production — Predict is an overlay,
not a mutation (CLAUDE.md §6)."""

from .engine import compute_and_cache, load_momentum

__all__ = ["compute_and_cache", "load_momentum"]
