"""Plugin-cell defaults.

Implementation-hint constants (not contract types): the yaml config-file path
read by ``pluginator``'s ``plugin_config`` for the ``ApiPlugin`` options, and
the ``default_from`` sources for the ``assert_timeout``/``assert_delay`` options
(``None`` — polling is opt-in via config/CLI). The config file is tolerated
when absent (``plugin_config`` returns ``default_config`` or ``{}``).
"""

from typing import Final

CONFIG_FILE: Final[str] = ".goga/tools/pybuggy/config.yml"

ASSERT_TIMEOUT: Final[int | None] = None
ASSERT_DELAY: Final[int | float | None] = None
