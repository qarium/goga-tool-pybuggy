"""Environment-variable names consumed by the ``ApiPlugin`` options.

These are the env-var sources in the pluginator option-resolution chain
(``plugin_config_key -> env_var -> command_line -> default_from``): the
``base_url`` option falls back to ``BASE_URL`` and the ``timeout`` option to
``API_TIMEOUT``.
"""

from typing import Final

BASE_URL: Final[str] = "BASE_URL"
API_TIMEOUT: Final[str] = "API_TIMEOUT"
