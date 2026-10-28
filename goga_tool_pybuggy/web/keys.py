"""The fixed key set of the web config document (`WebConfigKeys` + `CONFIG_FILE`).

The canonical key set of ``web.yml``: the file name plus the 19 config keys mirroring the
``PrettyConfig`` field names 1:1 — consumed data-driven by the init survey, the commented-example
documentation, the validation alignment, and the installation gate.
"""

import typing as t
from enum import Enum


class WebConfigKeys(str, Enum):
    """Fixed value set of the web config keys — the canonical key set of ``web.yml``.

    Members map to the lowercase ``web.yml`` key strings; ``FILENAME`` names the document file.
    Member order is contract order (the documenter walks it). Fixed set: do not add, remove, or
    rename members or change their values — the init survey, the example documentation, the
    validation alignment, and the installation gate depend on the exact key set.
    """

    FILENAME = "web.yml"
    PROVIDER = "provider"
    BASE_URL = "base_url"
    MODEL = "model"
    GENERATION_MODEL = "generation_model"
    CLASSIFICATION_MODEL = "classification_model"
    GENERATION_PROMPT = "generation_prompt"
    CLASSIFICATION_PROMPT = "classification_prompt"
    STRICT = "strict"
    INTERACTIVE = "interactive"
    POLLING_TIMEOUT = "polling_timeout"
    POLLING_DELAY = "polling_delay"
    GENERATION_ATTEMPTS = "generation_attempts"
    HEALING_ATTEMPTS = "healing_attempts"
    LLM_REQUEST_ATTEMPTS = "llm_request_attempts"
    SEND_SCREENSHOTS = "send_screenshots"
    GENERATION_APPROVE = "generation_approve"
    PROBE_TIMEOUT = "probe_timeout"
    CACHE_ROOT = "cache_root"
    BROWSER = "browser"


# Standard platform path of the web config document — the `@define.plugin` config path and the
# error-naming source of the web cell.
CONFIG_FILE: t.Final[str] = f".goga/tools/pybuggy/{WebConfigKeys.FILENAME.value}"
