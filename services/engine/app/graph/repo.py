"""Track-partitioned Neo4j repository.

Nodes/edges carry internal `_uid`, `_track`, `_theme` properties. Public reads
strip the `_`-prefixed internals and return plain dicts shaped like the shared
graph-schema. Labels/relationship types are validated against the generated
schema before being interpolated into Cypher (they cannot be parameterized)."""
from __future__ import annotations

import hashlib
from typing import Any

from neo4j import Driver

from ..graph_schema import EDGE_TYPES, NODE_LABELS
from .client import get_driver

_NODE_LABELS = set(NODE_LABELS)
_EDGE_TYPES = set(EDGE_TYPES)
# Fields that distinguish otherwise-parallel edges between the same two nodes.
_EDGE_KEY_FIELDS = ("product_ref", "period", "currency")


def _strip(props: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in props.items() if not k.startswith("_")}


class GraphRepo:
    """Base repo bound to one track. Use the Staging/Production subclasses."""

    track: str = "staging"

    def __init__(self, driver: Driver | None = None) -> None:
        self._driver = driver or get_driver()

    # ── identity helpers ──────────────────────────────────────────────────────
    def _uid(self, theme_id: str, node_id: str) -> str:
        return f"{self.track}:{theme_id}:{node_id}"

    def _ekey(self, theme_id: str, edge: dict[str, Any]) -> str:
        parts = [edge["type"], edge["from"], edge["to"]]
        parts += [str(edge.get(f, "")) for f in _EDGE_KEY_FIELDS]
        raw = "|".join(parts)
        return hashlib.sha1(raw.encode()).hexdigest()[:16]

    # ── schema setup ──────────────────────────────────────────────────────────
    def ensure_constraints(self) -> None:
        with self._driver.session() as s:
            s.run("CREATE CONSTRAINT chainos_uid IF NOT EXISTS "
                  "FOR (n:Company) REQUIRE n._uid IS UNIQUE")

    # ── writes ────────────────────────────────────────────────────────────────
    def upsert_node(self, theme_id: str, node: dict[str, Any]) -> None:
        label = node.get("label")
        if label not in _NODE_LABELS:
            raise ValueError(f"Unknown node label: {label!r}")
        node_id = node["id"]
        props = {k: v for k, v in node.items() if v is not None}
        uid = self._uid(theme_id, node_id)
        cypher = (
            f"MERGE (n:`{label}` {{_uid: $uid}}) "
            "SET n += $props, n._uid = $uid, n._track = $track, n._theme = $theme"
        )
        with self._driver.session() as s:
            s.run(cypher, uid=uid, props=props, track=self.track, theme=theme_id)

    def upsert_edge(self, theme_id: str, edge: dict[str, Any]) -> None:
        etype = edge.get("type")
        if etype not in _EDGE_TYPES:
            raise ValueError(f"Unknown edge type: {etype!r}")
        from_uid = self._uid(theme_id, edge["from"])
        to_uid = self._uid(theme_id, edge["to"])
        props = {
            k: v
            for k, v in edge.items()
            if k not in ("type", "from", "to") and v is not None
        }
        ekey = self._ekey(theme_id, edge)
        cypher = (
            "MATCH (a {_uid: $from_uid}), (b {_uid: $to_uid}) "
            f"MERGE (a)-[r:`{etype}` {{_ekey: $ekey}}]->(b) "
            "SET r += $props, r._track = $track, r._theme = $theme, "
            "r.`from` = $from_id, r.to = $to_id"
        )
        with self._driver.session() as s:
            s.run(
                cypher,
                from_uid=from_uid,
                to_uid=to_uid,
                ekey=ekey,
                props=props,
                track=self.track,
                theme=theme_id,
                from_id=edge["from"],
                to_id=edge["to"],
            )

    def write_graph(self, theme_id: str, nodes: list[dict], edges: list[dict]) -> None:
        for n in nodes:
            self.upsert_node(theme_id, n)
        for e in edges:
            self.upsert_edge(theme_id, e)

    def clear_theme(self, theme_id: str) -> None:
        with self._driver.session() as s:
            s.run(
                "MATCH (n {_theme: $theme, _track: $track}) DETACH DELETE n",
                theme=theme_id,
                track=self.track,
            )

    # ── reads ─────────────────────────────────────────────────────────────────
    def get_graph(
        self,
        theme_id: str,
        *,
        depth: int | None = None,
        edge_types: list[str] | None = None,
        labels: list[str] | None = None,
    ) -> dict[str, list[dict[str, Any]]]:
        with self._driver.session() as s:
            node_rows = s.run(
                "MATCH (n {_theme: $theme, _track: $track}) "
                "RETURN labels(n) AS labels, properties(n) AS props",
                theme=theme_id,
                track=self.track,
            ).data()
            edge_rows = s.run(
                "MATCH (a {_theme: $theme, _track: $track})-[r]->(b {_theme: $theme, _track: $track}) "
                "RETURN type(r) AS type, properties(r) AS props",
                theme=theme_id,
                track=self.track,
            ).data()

        nodes: list[dict[str, Any]] = []
        for row in node_rows:
            label = next((lbl for lbl in row["labels"] if lbl in _NODE_LABELS), None)
            props = _strip(row["props"])
            props["label"] = label
            if labels and label not in labels:
                continue
            if depth is not None and label == "Company" and props.get("tier", 1) > depth:
                continue
            nodes.append(props)

        kept_ids = {n["id"] for n in nodes}
        edges: list[dict[str, Any]] = []
        for row in edge_rows:
            etype = row["type"]
            if etype == "SOURCED_FROM":
                continue
            if edge_types and etype not in edge_types:
                continue
            props = _strip(row["props"])
            props["type"] = etype
            # When depth-filtering, drop edges whose endpoints were culled.
            if depth is not None and (props.get("from") not in kept_ids or props.get("to") not in kept_ids):
                continue
            edges.append(props)
        return {"nodes": nodes, "edges": edges}

    def count(self, theme_id: str) -> dict[str, int]:
        with self._driver.session() as s:
            rec = s.run(
                "MATCH (n {_theme: $theme, _track: $track}) "
                "WITH count(n) AS nodes "
                "MATCH (:`Company` {_theme: $theme, _track: $track})"
                "-[r]->(:`Company` {_theme: $theme, _track: $track}) "
                "RETURN nodes, count(r) AS edges",
                theme=theme_id,
                track=self.track,
            ).single()
            if rec is None:
                return {"nodes": 0, "edges": 0}
            return {"nodes": rec["nodes"], "edges": rec["edges"]}

    # ── verification loop: lock figures to evidence (M2) ──────────────────────
    def upsert_source_node(self, theme_id: str, source: dict[str, Any]) -> None:
        self.upsert_node(theme_id, {"label": "Source", **source})

    def lock_edge(
        self, theme_id: str, payload: dict[str, Any], updates: dict[str, Any]
    ) -> int:
        """Set the locked value + trust meta on the targeted SUPPLIES/REVENUE_FLOW/
        INVESTS_IN edge. Returns the number of edges updated."""
        etype = payload["type"]
        if etype not in _EDGE_TYPES:
            raise ValueError(f"Unknown edge type: {etype!r}")
        from_uid = self._uid(theme_id, payload["from"])
        to_uid = self._uid(theme_id, payload["to"])
        where_product = ""
        params: dict[str, Any] = {
            "from_uid": from_uid,
            "to_uid": to_uid,
            "updates": updates,
        }
        if payload.get("product_ref"):
            where_product = "AND r.product_ref = $product_ref "
            params["product_ref"] = payload["product_ref"]
        cypher = (
            f"MATCH (a {{_uid: $from_uid}})-[r:`{etype}`]->(b {{_uid: $to_uid}}) "
            f"WHERE true {where_product}"
            "SET r += $updates "
            "RETURN count(r) AS n"
        )
        with self._driver.session() as s:
            rec = s.run(cypher, **params).single()
            return rec["n"] if rec else 0

    def lock_node_field(
        self,
        theme_id: str,
        label: str,
        node_id: str,
        updates: dict[str, Any],
        *,
        source_id: str | None = None,
    ) -> None:
        """Set a quantitative node field + (optionally) a SOURCED_FROM link to its
        evidence Source node."""
        if label not in _NODE_LABELS:
            raise ValueError(f"Unknown node label: {label!r}")
        uid = self._uid(theme_id, node_id)
        with self._driver.session() as s:
            s.run(
                f"MATCH (n:`{label}` {{_uid: $uid}}) SET n += $updates",
                uid=uid,
                updates=updates,
            )
            if source_id:
                s.run(
                    "MATCH (n {_uid: $uid}), (src:`Source` {_uid: $src_uid}) "
                    "MERGE (n)-[:`SOURCED_FROM`]->(src)",
                    uid=uid,
                    src_uid=self._uid(theme_id, source_id),
                )

    def has_source_node(self, theme_id: str, source_id: str) -> bool:
        with self._driver.session() as s:
            rec = s.run(
                "MATCH (src:`Source` {_uid: $uid}) RETURN count(src) AS n",
                uid=self._uid(theme_id, source_id),
            ).single()
            return bool(rec and rec["n"])

    # ── company drill-down (Micro view, M5) ───────────────────────────────────
    def get_company_detail(self, theme_id: str, company_id: str) -> dict[str, Any] | None:
        uid = self._uid(theme_id, company_id)
        with self._driver.session() as s:
            company = s.run(
                "MATCH (c:`Company` {_uid: $uid}) RETURN properties(c) AS props", uid=uid
            ).single()
            if company is None:
                return None
            divisions = s.run(
                "MATCH (c:`Company` {_uid: $uid})-[:`HAS_DIVISION`]->(d:`Division`)"
                "-[:`PRODUCES`]->(p:`Product`) "
                "RETURN properties(d) AS division, collect(properties(p)) AS products",
                uid=uid,
            ).data()
            customers = s.run(
                "MATCH (c:`Company` {_uid: $uid})-[r:`SUPPLIES`]->(cust:`Company`) "
                "RETURN cust.id AS id, cust.name AS name, properties(r) AS edge",
                uid=uid,
            ).data()
        return {
            "company": _strip(company["props"]),
            "divisions": [
                {
                    "division": _strip(d["division"]),
                    "products": [_strip(p) for p in d["products"]],
                }
                for d in divisions
            ],
            "customers": [
                {"id": c["id"], "name": c["name"], "edge": _strip(c["edge"])}
                for c in customers
            ],
        }

    # ── atomic snapshot replace (publish, M3) ─────────────────────────────────
    def replace_theme(
        self, theme_id: str, nodes: list[dict[str, Any]], edges: list[dict[str, Any]]
    ) -> dict[str, int]:
        """Atomically swap this track's subgraph for `theme_id`: delete then rebuild
        in a SINGLE transaction. Used by Publish to snapshot Staging → Production
        with no partially-visible intermediate state (PRD §4 invariant)."""
        with self._driver.session() as s, s.begin_transaction() as tx:
            tx.run(
                "MATCH (n {_theme: $theme, _track: $track}) DETACH DELETE n",
                theme=theme_id,
                track=self.track,
            )
            for node in nodes:
                label = node.get("label")
                if label not in _NODE_LABELS:
                    raise ValueError(f"Unknown node label: {label!r}")
                props = {k: v for k, v in node.items() if v is not None}
                uid = self._uid(theme_id, node["id"])
                tx.run(
                    f"MERGE (n:`{label}` {{_uid: $uid}}) "
                    "SET n += $props, n._uid = $uid, n._track = $track, n._theme = $theme",
                    uid=uid,
                    props=props,
                    track=self.track,
                    theme=theme_id,
                )
            for edge in edges:
                etype = edge.get("type")
                if etype not in _EDGE_TYPES:
                    raise ValueError(f"Unknown edge type: {etype!r}")
                props = {
                    k: v for k, v in edge.items() if k not in ("type", "from", "to") and v is not None
                }
                tx.run(
                    "MATCH (a {_uid: $from_uid}), (b {_uid: $to_uid}) "
                    f"MERGE (a)-[r:`{etype}` {{_ekey: $ekey}}]->(b) "
                    "SET r += $props, r._track = $track, r._theme = $theme, "
                    "r.`from` = $from_id, r.to = $to_id",
                    from_uid=self._uid(theme_id, edge["from"]),
                    to_uid=self._uid(theme_id, edge["to"]),
                    ekey=self._ekey(theme_id, edge),
                    props=props,
                    track=self.track,
                    theme=theme_id,
                    from_id=edge["from"],
                    to_id=edge["to"],
                )
            tx.commit()
        return self.count(theme_id)

    # ── publish support (M3) ──────────────────────────────────────────────────
    def export_theme(self, theme_id: str) -> dict[str, list[dict[str, Any]]]:
        """Full dump including Source nodes + SOURCED_FROM, used by publish."""
        with self._driver.session() as s:
            node_rows = s.run(
                "MATCH (n {_theme: $theme, _track: $track}) "
                "RETURN labels(n) AS labels, properties(n) AS props",
                theme=theme_id,
                track=self.track,
            ).data()
            edge_rows = s.run(
                "MATCH (a {_theme: $theme, _track: $track})-[r]->(b {_theme: $theme, _track: $track}) "
                "RETURN type(r) AS type, properties(r) AS props",
                theme=theme_id,
                track=self.track,
            ).data()
        nodes = []
        for row in node_rows:
            label = next((lbl for lbl in row["labels"] if lbl in _NODE_LABELS), None)
            props = _strip(row["props"])
            props["label"] = label
            nodes.append(props)
        edges = []
        for row in edge_rows:
            props = _strip(row["props"])
            props["type"] = row["type"]
            edges.append(props)
        return {"nodes": nodes, "edges": edges}


class StagingGraphRepo(GraphRepo):
    track = "staging"


class ProductionGraphRepo(GraphRepo):
    """Read-only snapshot the Terminal consumes. Writes only happen via Publish."""

    track = "production"
