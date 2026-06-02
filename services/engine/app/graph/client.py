"""Neo4j driver singleton."""
from __future__ import annotations

from functools import lru_cache

from neo4j import Driver, GraphDatabase

from ..config import get_settings


@lru_cache
def get_driver() -> Driver:
    s = get_settings()
    return GraphDatabase.driver(
        s.neo4j_uri,
        auth=(s.neo4j_user, s.neo4j_password),
        # Silence cosmetic "unknown label/property" notices on first-touch queries.
        notifications_min_severity="OFF",
    )
