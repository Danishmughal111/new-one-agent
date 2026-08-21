"""Structured logging configuration.

Provides a single ``configure_logging`` entry point and a JSON-aware
formatter. Secrets must never be logged; callers are responsible for not
passing sensitive values into log statements.
"""

import json
import logging
import sys

from app.core.config import settings


class JsonFormatter(logging.Formatter):
    """JSON log formatter for machine-readable structured logs."""

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload)


def get_logger(name: str) -> logging.Logger:
    """Return a named logger (configured by ``configure_logging``)."""
    return logging.getLogger(name)


def configure_logging() -> None:
    """Configure the root logger once at application startup."""
    level = getattr(logging, settings.log_level.upper(), logging.INFO)

    root = logging.getLogger()
    if root.handlers:  # already configured
        return

    root.setLevel(level)
    handler = logging.StreamHandler(sys.stdout)

    if settings.log_format == "json":
        handler.setFormatter(JsonFormatter())
    else:
        handler.setFormatter(
            logging.Formatter(
                "%(asctime)s %(levelname)s %(name)s %(message)s"
            )
        )

    root.addHandler(handler)