"""Redis access for the momentum cache + job queue (PRD §8)."""
from __future__ import annotations

import os
from functools import lru_cache

import redis


@lru_cache
def get_redis() -> redis.Redis:
    url = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
    return redis.Redis.from_url(url, decode_responses=True)


MOMENTUM_KEY = "chainos:momentum:{theme}"
