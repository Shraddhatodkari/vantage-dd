"""Structured JSON logging with request correlation IDs."""
from __future__ import annotations

import contextvars
import json
import logging
import sys
import time

request_id_var: contextvars.ContextVar[str] = contextvars.ContextVar("request_id", default="-")


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        data = {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(record.created)),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
            "request_id": request_id_var.get(),
        }
        for key in ("deal_id", "run_id", "agent", "latency_ms", "user"):
            if hasattr(record, key):
                data[key] = getattr(record, key)
        if record.exc_info:
            data["exc"] = self.formatException(record.exc_info)
        return json.dumps(data)


def configure_logging(level: str = "INFO") -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(level)


log = logging.getLogger("vantage")
