"""Dev bootstrap: create all relational tables. For production, prefer the
Alembic migrations under services/engine/migrations (`alembic upgrade head`)."""
from __future__ import annotations

from .. import models  # noqa: F401  (register mappers)
from .base import Base
from .session import get_engine


def init_db() -> None:
    Base.metadata.create_all(bind=get_engine())


if __name__ == "__main__":
    init_db()
    print("Chainos: relational tables ready.")
