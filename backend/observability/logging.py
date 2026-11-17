"""Structured logging and correlation context for TrainBench."""
import contextvars
import json
import logging
import sys
from datetime import datetime, timezone
from typing import Any, Dict, Optional
import uuid

# Context variable for request / execution correlation ID
correlation_id_ctx: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar(
    "correlation_id", default=None
)


def get_correlation_id() -> str:
    cid = correlation_id_ctx.get()
    if not cid:
        cid = str(uuid.uuid4())
        correlation_id_ctx.set(cid)
    return cid


def set_correlation_id(cid: str) -> None:
    correlation_id_ctx.set(cid)


class JSONFormatter(logging.Formatter):
    """Outputs log records formatted as single-line JSON."""

    def format(self, record: logging.LogRecord) -> str:
        log_entry: Dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "correlation_id": correlation_id_ctx.get() or "-",
        }

        for attr in ("run_id", "project_id", "duration_ms", "error_code"):
            value = getattr(record, attr, None)
            if value is not None:
                log_entry[attr] = value

        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_entry)


def setup_logging(level: str = "INFO") -> logging.Logger:
    logger = logging.getLogger("trainbench")
    logger.setLevel(level)

    # Avoid duplicate handlers if re-called
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(JSONFormatter())
        logger.addHandler(handler)

    return logger


logger = setup_logging()
