"""Application logging: console output aligned with uvicorn."""

from __future__ import annotations

import copy
import logging
import sys
from typing import Any

RESET = "\033[0m"
DIM = "\033[2m"
CYAN = "\033[36m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
RED = "\033[31m"
MAGENTA = "\033[35m"
BRIGHT = "\033[1m"

CONSOLE_FMT = "%(asctime)s │ %(levelname)s │ %(message)s"
ACCESS_FMT = '%(asctime)s │ %(levelname)s │ %(client_addr)s "%(request_line)s" %(status_code)s'
DATE_FMT = "%H:%M:%S"

LEVEL_STYLE: dict[int, tuple[str, str, str]] = {
    logging.DEBUG: (CYAN, "◎", "DEBUG"),
    logging.INFO: (GREEN, "●", "INFO"),
    logging.WARNING: (YELLOW, "⚠", "WARN"),
    logging.ERROR: (RED, "✖", "ERROR"),
    logging.CRITICAL: (MAGENTA + BRIGHT, "‼", "CRIT"),
}
ACCESS_STYLE = (CYAN, "⇢", "ACCESS")


def use_color() -> bool:
    stream = sys.stderr
    return hasattr(stream, "isatty") and stream.isatty()


class ColoredFormatter(logging.Formatter):
    """Time │ icon level │ message — same layout for app and uvicorn logs."""

    def __init__(
        self,
        fmt: str = CONSOLE_FMT,
        datefmt: str = DATE_FMT,
        *,
        color: bool | None = None,
        access: bool = False,
    ) -> None:
        super().__init__(fmt=fmt, datefmt=datefmt)
        self._use_color = color if color is not None else use_color()
        self._access = access

    def format(self, record: logging.LogRecord) -> str:
        original = record.levelname
        if self._use_color:
            colored = copy.copy(record)
            if self._access:
                color, icon, label = ACCESS_STYLE
            else:
                color, icon, label = LEVEL_STYLE.get(
                    record.levelno,
                    ("", "•", original),
                )
            colored.levelname = f"{color}{icon} {label:<5}{RESET}"
            return super().format(colored)
        if self._access:
            record.levelname = f"{ACCESS_STYLE[1]} ACCESS"
        else:
            _, icon, label = LEVEL_STYLE.get(record.levelno, ("", "•", original))
            record.levelname = f"{icon} {label:<5}"
        try:
            return super().format(record)
        finally:
            record.levelname = original


_QUIET_LOGGERS = (
    "asyncio",
    "chromadb",
    "httpcore",
    "httpx",
    "huggingface_hub",
    "openai",
    "sentence_transformers",
    "torch",
    "transformers",
    "urllib3",
    "watchfiles",
)


def quiet_third_party_loggers() -> None:
    for name in _QUIET_LOGGERS:
        logging.getLogger(name).setLevel(logging.WARNING)


def _resolve_level(*, debug: bool = False, level: str | None = None) -> int:
    if level:
        return getattr(logging, level.strip().upper(), logging.INFO)
    return logging.DEBUG if debug else logging.INFO


def apply_log_level(level: str) -> None:
    """热更新根 logger 及已有 handler 级别（不重建 handler）。"""
    lvl = _resolve_level(level=level)
    root = logging.getLogger()
    root.setLevel(lvl)
    for handler in root.handlers:
        handler.setLevel(lvl)
    quiet_third_party_loggers()


def setup_logging(*, debug: bool = False, level: str | None = None) -> None:
    lvl = _resolve_level(debug=debug, level=level)
    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(lvl)
    handler.setFormatter(ColoredFormatter())
    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(lvl)
    quiet_third_party_loggers()


def get_uvicorn_log_config(*, debug: bool = False, level: str | None = None) -> dict[str, Any]:
    lvl_name = (level or ("DEBUG" if debug else "INFO")).strip().upper()
    formatter = {
        "()": "src.utils.logging.ColoredFormatter",
        "fmt": CONSOLE_FMT,
        "datefmt": DATE_FMT,
    }
    access_formatter = {
        "()": "src.utils.logging.ColoredFormatter",
        "fmt": ACCESS_FMT,
        "datefmt": DATE_FMT,
        "access": True,
    }
    third_party = {
        name: {"level": "WARNING", "propagate": True} for name in _QUIET_LOGGERS
    }
    return {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "default": formatter,
            "access": access_formatter,
        },
        "handlers": {
            "default": {
                "formatter": "default",
                "class": "logging.StreamHandler",
                "stream": "ext://sys.stdout",
            },
            "access": {
                "formatter": "access",
                "class": "logging.StreamHandler",
                "stream": "ext://sys.stdout",
            },
        },
        "loggers": {
            "uvicorn": {"handlers": ["default"], "level": "WARNING", "propagate": False},
            "uvicorn.error": {"level": "WARNING", "handlers": ["default"], "propagate": False},
            "uvicorn.access": {"handlers": ["access"], "level": "WARNING", "propagate": False},
            **third_party,
            "": {"handlers": ["default"], "level": lvl_name},
        },
    }
