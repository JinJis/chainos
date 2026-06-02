"""Structured logging for the Chainos Engine.

Configured once at startup from settings (LOG_LEVEL, LOG_FORMAT). Every app logger
lives under the `chainos.*` namespace. Set `LOG_LEVEL=DEBUG` in .env for verbose
troubleshooting — those records also stream into the Studio agent console (see
api/agent.py's SSE log capture).

Two formats:
  - text  (default): `<ts> <LEVEL> <logger> <message>  k=v k=v` + traceback
  - json:            one JSON object per line, with structured `extra` fields
"""
from __future__ import annotations

import json
import logging
import sys
from datetime import UTC, datetime

# Standard LogRecord attributes; anything else attached to a record (via
# `logger.info(..., extra={...})`) is rendered as structured context.
_RESERVED = set(logging.makeLogRecord({}).__dict__) | {"message", "asctime", "taskName"}

# Chatty third-party loggers — capped so app logs stay readable even at DEBUG.
_NOISY = (
    "neo4j",
    "httpx",
    "httpcore",
    "urllib3",
    "sqlalchemy.engine",
    "watchfiles",
    "asyncio",
)


def _extras(record: logging.LogRecord) -> dict[str, object]:
    return {k: v for k, v in record.__dict__.items() if k not in _RESERVED and not k.startswith("_")}


def _ts(record: logging.LogRecord) -> str:
    dt = datetime.fromtimestamp(record.created, tz=UTC)
    return dt.strftime("%Y-%m-%dT%H:%M:%S") + f".{int(record.msecs):03d}Z"


class TextFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        line = f"{_ts(record)} {record.levelname:<5} {record.name:<22} {record.getMessage()}"
        extras = _extras(record)
        if extras:
            line += "  " + " ".join(f"{k}={v}" for k, v in extras.items())
        if record.exc_info:
            line += "\n" + self.formatException(record.exc_info)
        return line


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, object] = {
            "ts": _ts(record),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        payload.update(_extras(record))
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


def _resolve_level(level: str) -> int:
    try:
        return logging.getLevelNamesMapping()[level.upper()]
    except (KeyError, AttributeError):
        value = getattr(logging, level.upper(), logging.INFO)
        return value if isinstance(value, int) else logging.INFO


def configure_logging(level: str = "INFO", fmt: str = "text") -> None:
    """(Re)configure root logging. Idempotent — safe to call at import and again
    in the app lifespan so it wins over uvicorn's own setup."""
    lvl = _resolve_level(level)
    formatter: logging.Formatter = JsonFormatter() if fmt.lower() == "json" else TextFormatter()

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    root = logging.getLogger()
    for existing in list(root.handlers):
        root.removeHandler(existing)
    root.addHandler(handler)
    root.setLevel(lvl)

    logging.getLogger("chainos").setLevel(lvl)

    # We log requests ourselves (see main.py middleware); silence uvicorn access.
    access = logging.getLogger("uvicorn.access")
    access.handlers.clear()
    access.propagate = False
    access.setLevel(logging.WARNING)
    logging.getLogger("uvicorn.error").setLevel(logging.INFO)

    # Third-party libs stay at WARNING even when verbose, so "DEBUG" surfaces the
    # app's own `chainos.*` trace rather than SQL echo / bolt chatter.
    for name in _NOISY:
        logging.getLogger(name).setLevel(logging.WARNING)

    logging.getLogger("chainos").debug(
        "logging configured", extra={"level": logging.getLevelName(lvl), "format": fmt}
    )


def get_logger(name: str) -> logging.Logger:
    """Return a logger under the chainos namespace, e.g. get_logger('agent')."""
    return logging.getLogger(f"chainos.{name}")
