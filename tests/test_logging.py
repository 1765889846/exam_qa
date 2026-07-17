"""Logging formatter tests."""

from __future__ import annotations

import logging

from src.utils.logging import ColoredFormatter, setup_logging


def test_colored_formatter_without_color():
    formatter = ColoredFormatter(color=False)
    record = logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="hello",
        args=(),
        exc_info=None,
    )
    assert "hello" in formatter.format(record)


def test_setup_logging_is_idempotent():
    setup_logging(debug=False)
    setup_logging(debug=False)
    assert logging.getLogger().level == logging.INFO


def test_apply_log_level_updates_root():
    from src.utils.logging import apply_log_level

    setup_logging(level="INFO")
    apply_log_level("WARNING")
    assert logging.getLogger().level == logging.WARNING
    apply_log_level("DEBUG")
    assert logging.getLogger().level == logging.DEBUG
