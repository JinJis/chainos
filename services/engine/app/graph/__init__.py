"""Neo4j knowledge-graph layer with Two-Track separation.

The graph is partitioned by a `track` property ('staging' | 'production'). The
StagingGraphRepo is where the agent works; the ProductionGraphRepo is the
read-only snapshot the Terminal consumes. Terminal-facing code MUST only ever
construct a ProductionGraphRepo — that is how invariant #1 (Terminal reads
Production only) is enforced in code. (On Neo4j Community a single instance
cannot host multiple named databases, so we emulate the two physical DBs with
this track partition; on Enterprise these map to real separate databases.)"""

from .client import get_driver
from .repo import GraphRepo, ProductionGraphRepo, StagingGraphRepo

__all__ = ["get_driver", "GraphRepo", "StagingGraphRepo", "ProductionGraphRepo"]
