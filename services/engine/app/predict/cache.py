"""Redis-backed momentum cache."""
from __future__ import annotations

import json
from functools import lru_cache
from typing import Any

import redis

from ..config import get_settings

_MOMENTUM_KEY = "chainos:momentum:{theme}"
_TTL_SECONDS = 60 * 30  # momentum is short-lived by nature


@lru_cache
def get_redis() -> redis.Redis:
    return redis.Redis.from_url(get_settings().redis_url, decode_responses=True)


def write_momentum(theme_id: str, payload: dict[str, Any]) -> None:
    get_redis().set(_MOMENTUM_KEY.format(theme=theme_id), json.dumps(payload), ex=_TTL_SECONDS)


def read_momentum(theme_id: str) -> dict[str, Any] | None:
    raw = get_redis().get(_MOMENTUM_KEY.format(theme=theme_id))
    return json.loads(raw) if raw else None
