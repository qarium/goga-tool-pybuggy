"""Environment-variable names consumed by the ``ApiPlugin`` options.

These are the env-var sources in the pluginator option-resolution chain
(``plugin_config_key -> env_var -> command_line -> default_from``): the
``base_url`` option falls back to ``QA_BASE_URL`` and the ``timeout`` option to
``QA_API_TIMEOUT``.
"""

from typing import Final

QA_BASE_URL: Final[str] = "QA_BASE_URL"
QA_API_TIMEOUT: Final[str] = "QA_API_TIMEOUT"
