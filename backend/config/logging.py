import json
import logging
from datetime import datetime, timezone


class StructuredJsonFormatter(logging.Formatter):
    """Render log records as flat JSON objects for ingestion jobs."""

    _RESERVED_ATTRS = set(vars(logging.makeLogRecord({})).keys()) | {"message", "asctime"}

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        event = getattr(record, "event", None)
        if event:
            payload["event"] = event

        context = getattr(record, "context", None)
        if isinstance(context, dict):
            payload.update(context)

        for key, value in record.__dict__.items():
            if key in self._RESERVED_ATTRS or key in {"event", "context"}:
                continue
            if key.startswith("_"):
                continue
            payload[key] = value

        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)

        return json.dumps(payload, default=str)
