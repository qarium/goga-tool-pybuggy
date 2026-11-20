"""Console formatter of the prettyplay log events — human-readable events render without extras.

The five execution-context events already carry their context in the message; every other event
keeps its structured extras visible as sorted ``key=value`` pairs. The installer touches only the
``prettyplay`` logger and is idempotent.
"""

import logging
import sys
from typing import Final

_RESERVED_RECORD_FIELDS: Final[frozenset[str]] = frozenset(
    logging.LogRecord("probe", 0, "probe", 0, "probe", (), None).__dict__
) | {"message", "asctime"}
_HUMAN_READABLE_EVENTS: Final[frozenset[str]] = frozenset(
    ["step_results_declared", "step_inputs", "step_candidate_code", "step_cached_code", "step_captured"]
)
_FORMAT: Final[str] = "%(asctime)s %(levelname)-7s %(message)s"
_DATEFMT: Final[str] = "%H:%M:%S"


class EventLogFormatter(logging.Formatter):
    """Render prettyplay log records for the console without payload duplication.

    The human-readable events return the plain message; other events append their non-reserved
    extras as sorted ``key=value`` pairs.

    Args:
        fmt: The logging format string applied to every record.
        datefmt: The date format string rendering the record timestamp.
    """

    def format(self, record: logging.LogRecord) -> str:
        """Render the record, appending sorted extras unless the event is human-readable.

        Args:
            record: The log record, including its structured context.

        Returns:
            The formatted console text — the plain message for the human-readable events, the
            message with `` | key=value`` extras appended otherwise.
        """
        message = super().format(record)

        event = getattr(record, "event", None)

        if event in _HUMAN_READABLE_EVENTS:
            return message

        # The event key is the discriminator consumed above, not payload — it never renders.
        extras = {
            key: value
            for key, value in record.__dict__.items()
            if key != "event" and key not in _RESERVED_RECORD_FIELDS and not key.startswith("_")
        }

        if not extras:
            return message

        payload = " ".join(f"{key}={value!r}" for key, value in sorted(extras.items()))

        return f"{message} | {payload}"


def install_event_log_formatter() -> None:
    """Install the prettyplay event log formatter on the console.

    Sets the ``prettyplay`` logger to INFO and attaches a stdout stream handler carrying the
    event formatter; a repeated installation adds no duplicate handler.
    """
    logger = logging.getLogger("prettyplay")

    for handler in logger.handlers:
        if isinstance(handler.formatter, EventLogFormatter):
            return

    logger.setLevel(logging.INFO)

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(EventLogFormatter(_FORMAT, _DATEFMT))
    logger.addHandler(handler)
