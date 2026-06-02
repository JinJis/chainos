"""Neo4j driver singleton."""
from __future__ import annotations

from functools import lru_cache

from neo4j import Driver, GraphDatabase

from ..config import get_settings
from ..logging_config import get_logger

log = get_logger("graph.client")


@lru_cache
def get_driver() -> Driver:
    s = get_settings()
    log.info("connecting Neo4j driver", extra={"uri": s.neo4j_uri, "user": s.neo4j_user})
    return GraphDatabase.driver(
        s.neo4j_uri,
        auth=(s.neo4j_user, s.neo4j_password),
        # Silence cosmetic "unknown label/property" notices on first-touch queries.
        notifications_min_severity="OFF",
    )
