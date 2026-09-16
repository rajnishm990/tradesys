import logging
import json

_STD_KEYS = {
    "args", "msg", "levelname", "levelno", "name", "pathname", "filename",
    "module", "exc_info", "exc_text", "stack_info", "lineno", "funcName",
    "created", "msecs", "relativeCreated", "thread", "threadName",
    "processName", "process", "message",
}


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {"level": record.levelname, "logger": record.name, "msg": record.getMessage()}
        payload.update({k: v for k, v in record.__dict__.items() if k not in _STD_KEYS})
        return json.dumps(payload)


def configure(path: str = None) -> None:
    handler = logging.StreamHandler() if path is None else logging.FileHandler(path, mode="w")
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger("tradesys")
    root.handlers = [handler]
    root.setLevel(logging.INFO)
    root.propagate = False
