"""Seed loader: build the AI Data Centers graph in Staging, then publish it into
Production through the REAL validation gate — exactly the path an admin follows.
Idempotent: re-running rebuilds + republishes. Run: `python -m app.seed.load`."""
from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select

from ..db import session_scope
from ..db.init import init_db
from ..graph import StagingGraphRepo
from ..models import Theme
from ..publish import PublishBlocked, publish_graph
from . import dataset


def load_seed() -> None:
    init_db()

    with session_scope() as s:
        theme = s.scalars(select(Theme).where(Theme.name == dataset.THEME_NAME)).first()
        if theme is None:
            theme = Theme(
                name=dataset.THEME_NAME,
                depth_max=3,
                status="building",
                model_assignment={
                    "RESEARCH": "google",
                    "DEEP": "anthropic",
                    "MEDIUM": "anthropic",
                    "LOW": "google",
                },
            )
            s.add(theme)
            s.flush()
        theme_id = theme.id

    repo = StagingGraphRepo()
    repo.ensure_constraints()
    repo.clear_theme(theme_id)
    graph = dataset.build_graph()
    repo.write_graph(theme_id, graph["nodes"], graph["edges"])
    staged = repo.count(theme_id)
    print(f"Staged '{dataset.THEME_NAME}' → {staged['nodes']} nodes / {staged['edges']} flows")

    try:
        result = publish_graph(theme_id)
    except PublishBlocked as exc:
        print("✗ Publish BLOCKED by validation gate:")
        for f in exc.report.failures[:20]:
            print(f"   - {f.ref}: missing {', '.join(f.missing)}")
        raise SystemExit(1) from exc

    with session_scope() as s:
        theme = s.get(Theme, theme_id)
        if theme:
            theme.version += 1
            theme.status = "published"
            theme.published_at = datetime.now(UTC)
            version = theme.version

    print(
        f"✓ Published v{version}: {result.report.passed}/{result.report.total} figures verified → "
        f"Production has {result.counts['nodes']} nodes / {result.counts['edges']} flows"
    )
    print(f"  theme_id = {theme_id}")


if __name__ == "__main__":
    load_seed()
