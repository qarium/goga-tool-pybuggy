"""Environment-variable names consumed by the ``ApiPlugin`` options.

Env-var sources in the pluginator chain: ``base_url`` falls back to ``BASE_URL``, ``timeout`` to ``API_TIMEOUT``.
"""

from typing import Final

BASE_URL: Final[str] = "BASE_URL"
API_TIMEOUT: Final[str] = "API_TIMEOUT"
