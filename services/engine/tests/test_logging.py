"""Structured logging tests."""
from __future__ import annotations

import json
import logging

from app.logging_config import (
    JsonFormatter,
    TextFormatter,
    _extras,
    configure_logging,
    get_logger,
)


def _record(**extra) -> logging.LogRecord:
    rec = logging.LogRecord(
        name="chainos.agent", level=logging.INFO, pathname=__file__, lineno=1,
        msg="node %s", args=("RESEARCH",), exc_info=None,
    )
    for k, v in extra.items():
        setattr(rec, k, v)
    return rec


def test_extras_excludes_standard_fields() -> None:
    rec = _record(theme_id="t1", count=17)
    extras = _extras(rec)
    assert extras == {"theme_id": "t1", "count": 17}
    assert "msg" not in extras and "levelname" not in extras


def test_text_formatter_includes_message_and_extras() -> None:
    out = TextFormatter().format(_record(theme_id="t1", count=17))
    assert "node RESEARCH" in out
    assert "INFO" in out and "chainos.agent" in out
    assert "theme_id=t1" in out and "count=17" in out


def test_json_formatter_is_valid_json_with_fields() -> None:
    out = JsonFormatter().format(_record(theme_id="t1"))
    obj = json.loads(out)
    assert obj["level"] == "INFO"
    assert obj["logger"] == "chainos.agent"
    assert obj["msg"] == "node RESEARCH"
    assert obj["theme_id"] == "t1"


def test_configure_logging_sets_level_and_namespace() -> None:
    configure_logging("DEBUG", "text")
    assert logging.getLogger("chainos").level == logging.DEBUG
    assert get_logger("agent").name == "chainos.agent"
    # third-party noise stays capped even at DEBUG
    assert logging.getLogger("neo4j").level >= logging.INFO
    configure_logging("INFO", "text")  # restore


def test_reserved_extra_keys_do_not_crash() -> None:
    """`extra={'name': ...}` would raise KeyError on a plain Logger; the SafeLogger
    renames collisions to x_<key> instead of crashing the request."""
    logger = get_logger("test.safe")
    logger.setLevel(logging.INFO)
    # Must not raise.
    logger.info("collision", extra={"name": "x", "module": "y", "theme_id": "t1"})
    rec = logging.LogRecord("chainos.test", logging.INFO, __file__, 1, "m", None, None)
    rec.__dict__["x_name"] = "x"
    out = TextFormatter().format(rec)
    assert "x_name=x" in out
