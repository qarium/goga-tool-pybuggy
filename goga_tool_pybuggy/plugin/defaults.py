"""Plugin-cell defaults.

Implementation-hint constants (not contract types); ``None`` defaults make assert polling opt-in via config/CLI.
"""

from typing import Final

CONFIG_FILE: Final[str] = ".goga/tools/pybuggy/api.yml"

SANDBOX_CONFIG_FILE: Final[str] = ".goga/tools/pybuggy/sandbox.yml"

WEB_CONFIG_FILE: Final[str] = ".goga/tools/pybuggy/web.yml"

ASSERT_TIMEOUT: Final[int | None] = None
ASSERT_DELAY: Final[int | float | None] = None
