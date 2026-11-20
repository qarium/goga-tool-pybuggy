"""Tests for the `goga_tool_pybuggy.web.logging_setup` module (the console event formatter)."""

import logging
import sys

import goga_tool_pybuggy.web.logging_setup as logging_setup_module
import pytest
from goga_tool_pybuggy.web.logging_setup import EventLogFormatter, install_event_log_formatter


def _record(message: str, event: str | None = None, **extras: object) -> logging.LogRecord:
    """Build a prettyplay-style log record carrying structured extras.

    Args:
        message: The record message.
        event: The structured event name, or None for a record without one.
        extras: The structured extras set as record attributes.

    Returns:
        The constructed log record.
    """
    record = logging.LogRecord("prettyplay", logging.INFO, "p", 1, message, (), None)

    if event is not None:
        record.event = event

    for key, value in extras.items():
        setattr(record, key, value)

    return record


class TestEventLogFormatterContract:
    """Contract tests for the formatter and the installer surface."""

    def test_event_log_formatter_is_formatter_subclass_constructible_with_fmt_datefmt(self):
        """`EventLogFormatter` subclasses `logging.Formatter` and constructs with `(fmt, datefmt)`."""
        formatter = EventLogFormatter("%(asctime)s %(levelname)-7s %(message)s", "%H:%M:%S")

        assert isinstance(formatter, logging.Formatter)

    def test_install_event_log_formatter_is_module_level_callable(self):
        """`install_event_log_formatter` is a callable on the `web.logging_setup` module."""
        assert callable(logging_setup_module.install_event_log_formatter)
        assert logging_setup_module.install_event_log_formatter is install_event_log_formatter


class TestEventLogFormatterLogic:
    """Logic tests for the plain rendering, the sorted extras, and the idempotent installer."""

    def test_install_event_log_formatter_idempotent(self):
        """Two installations leave exactly one stdout handler carrying the event formatter."""
        logger = logging.getLogger("prettyplay")

        # Snapshot and restore — the global logger state must not leak across tests.
        handlers_before = logger.handlers[:]
        level_before = logger.level

        logger.handlers.clear()

        try:
            install_event_log_formatter()
            install_event_log_formatter()

            assert len(logger.handlers) == 1

            handler = logger.handlers[0]

            assert isinstance(handler, logging.StreamHandler)
            assert handler.stream is sys.stdout
            assert isinstance(handler.formatter, EventLogFormatter)
            assert logger.level == logging.INFO
        finally:
            logger.handlers[:] = handlers_before
            logger.setLevel(level_before)

    def test_install_event_log_formatter_keeps_foreign_handlers(self):
        """A pre-existing non-event handler survives; the installer adds its own beside it."""
        logger = logging.getLogger("prettyplay")

        handlers_before = logger.handlers[:]
        level_before = logger.level
        foreign = logging.StreamHandler()

        logger.handlers[:] = [foreign]

        try:
            install_event_log_formatter()

            assert foreign in logger.handlers
            assert len(logger.handlers) == 2

            event_handlers = [
                handler for handler in logger.handlers if isinstance(handler.formatter, EventLogFormatter)
            ]

            assert len(event_handlers) == 1

            install_event_log_formatter()  # idempotent even beside the foreign handler

            assert len(logger.handlers) == 2
        finally:
            logger.handlers[:] = handlers_before
            logger.setLevel(level_before)

    @pytest.mark.parametrize(
        "event",
        [
            "step_results_declared",
            "step_inputs",
            "step_candidate_code",
            "step_cached_code",
            "step_captured",
        ],
    )
    def test_event_log_formatter_human_readable_events_render_plain(self, event):
        """Each of the five human-readable events renders the message without its extras."""
        formatter = EventLogFormatter("%(asctime)s %(levelname)-7s %(message)s", "%H:%M:%S")

        record = _record("step cached", event, step="open")

        rendered = formatter.format(record)

        assert "step cached" in rendered
        assert "step=" not in rendered

    def test_event_log_formatter_appends_sorted_extras(self):
        """Other events append their extras sorted with repr rendering; reserved keys never show."""
        formatter = EventLogFormatter("%(asctime)s %(levelname)-7s %(message)s", "%H:%M:%S")

        record = _record("llm request", "llm_request", b=2, a=1, _private="hidden")

        rendered = formatter.format(record)

        assert rendered.endswith(" | a=1 b=2")
        assert "levelname=" not in rendered
        assert "message=" not in rendered
        assert "asctime=" not in rendered
        assert "_private" not in rendered

    def test_event_log_formatter_record_without_event(self):
        """A record without an event attribute still renders with its extras appended."""
        formatter = EventLogFormatter("%(asctime)s %(levelname)-7s %(message)s", "%H:%M:%S")

        record = _record("llm call done", None, model="glm")

        rendered = formatter.format(record)

        assert rendered.endswith(" | model='glm'")

    def test_event_log_formatter_unknown_event_without_extras_renders_plain(self):
        """A non-human-readable event carrying no extras renders the message with no tail."""
        formatter = EventLogFormatter("%(asctime)s %(levelname)-7s %(message)s", "%H:%M:%S")

        record = _record("plain event", "other_event")

        rendered = formatter.format(record)

        assert "plain event" in rendered
        assert " | " not in rendered
