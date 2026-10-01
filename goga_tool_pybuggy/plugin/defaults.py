"""Plugin-cell defaults.

Implementation-hint constants (not contract types); ``None`` defaults make assert polling opt-in via config/CLI.
"""

from typing import Final

CONFIG_FILE: Final[str] = ".goga/tools/pybuggy/config.yml"

ASSERT_TIMEOUT: Final[int | None] = None
ASSERT_DELAY: Final[int | float | None] = None
