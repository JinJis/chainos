"""SQLAlchemy engine + session management."""
from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from functools import lru_cache

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from ..config import get_settings
from ..logging_config import get_logger

log = get_logger("db")


@lru_cache
def get_engine() -> Engine:
    url = get_settings().database_url
    # Redact credentials before logging the DSN.
    safe = url.split("@")[-1] if "@" in url else url
    log.info("creating SQLAlchemy engine", extra={"target": safe})
    return create_engine(url, pool_pre_ping=True, future=True)


@lru_cache
def _maker() -> sessionmaker[Session]:
    return sessionmaker(bind=get_engine(), expire_on_commit=False, future=True)


def get_session() -> Session:
    return _maker()()


@contextmanager
def session_scope() -> Iterator[Session]:
    """Transactional scope — commits on success, rolls back on error."""
    session = get_session()
    try:
        yield session
        session.commit()
    except Exception as exc:
        session.rollback()
        # HTTPException (404 etc.) is expected control flow; log real DB errors loudly.
        if exc.__class__.__name__ == "HTTPException":
            log.debug("session rollback (handled)", extra={"reason": str(exc)})
        else:
            log.exception("session rollback (db error)")
        raise
    finally:
        session.close()
