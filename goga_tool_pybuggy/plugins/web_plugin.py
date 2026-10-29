"""WebPlugin entity: the pluginator activation of the web test kind — the ``web`` fixture."""

import logging
import os
import typing as t

import pytest
from pluginator import CommandLine, define
from prettyplay import PrettyConfig, PrettyPlay
from yaml import YAMLError

from ..web import allure_hooks
from ..web.allure_hooks import AllureStepHooks
from ..web.config import validate_web_config
from ..web.keys import WebConfigKeys
from ..web.logging_setup import install_event_log_formatter
from ..web.pretty import build_pretty_config
from . import defaults

logger = logging.getLogger(__name__)

# Prefix of the library's env layer — every matching variable is scrubbed at configphase.
_PRETTYPLAY_ENV_PREFIX: t.Final[str] = "PRETTYPLAY_"


def _scrub_prettyplay_env() -> None:
    """Remove every ``PRETTYPLAY_`` environment variable of the process.

    ``web.yml`` is the single configuration source of a web run — the library's env layer must
    never override it. The scrub is permanent for the run and race-free: configphase is
    single-threaded.
    """
    names = sorted(name for name in os.environ if name.startswith(_PRETTYPLAY_ENV_PREFIX))

    for name in names:
        os.environ.pop(name, None)

    if names:
        logger.info("prettyplay env layer scrubbed", extra={"variables": names})
    else:
        logger.debug("prettyplay env layer scrubbed", extra={"variables": names})


def web_cache_path(item: pytest.Item) -> str:
    """Compute the per-test step-cache path from the requesting test item.

    Args:
        item: The pytest item of the requesting test.

    Returns:
        The posix-relative subdirectory inside the cache root —
        ``<module_stem>/<ClassName>/<test_name>`` with a class, ``<module_stem>/<test_name>``
        without.
    """
    segments = [item.path.stem]

    original = getattr(item, "originalname", None) or item.name

    cls = getattr(item, "cls", None)
    if cls is not None:
        segments.append(cls.__name__)

    segments.append(original)

    return "/".join(segments)


@define.plugin("pybuggy-web", config=defaults.WEB_CONFIG_FILE)
class WebPlugin:
    """Pluginator plugin exposing the ``web`` fixture of the web test kind.

    The web config document is the plugin's config: pluginator reads ``web.yml`` into
    ``plugin_config``, and ``configure()`` validates it into the activation — an invalid document
    fails the run at configphase, before any collection or browser. The strict and interactive
    options resolve from the document and the ``--strict-mode`` / ``--interactive`` flags; a typed
    flag forces its mode on (the CLI authority applied in ``configure``), and the resolved modes
    always mirror the validated activation — never the raw parse.

    Attributes:
        plugin_config: Anchor declaration; ``BasePlugin`` supplies the parsed document dict.
        strict: Resolved strict mode — replay-only, zero LLM calls; a cache miss fails.
        interactive: Resolved interactive step healing mode.
        activation: The validated web config — the library ``PrettyConfig``; set by ``configure``,
            ``None`` before it.
    """

    plugin_config: dict

    strict = define.option(
        bool,
        plugin_config_key=WebConfigKeys.STRICT,
        command_line=CommandLine("--strict-mode", action="store_true", help="Strict mode for using cache only"),
    )
    interactive = define.option(
        bool,
        plugin_config_key=WebConfigKeys.INTERACTIVE,
        command_line=CommandLine("--interactive", action="store_true", help="Interactive step healing mode"),
    )

    def __init__(self) -> None:
        """Initialize the plugin; the activation arrives with ``configure``."""
        super().__init__()

        self.activation: PrettyConfig | None = None

    def configure(self) -> None:
        """Validate the document into the activation and ready the runtime environment.

        Pluginator lifecycle callback at pytest configphase, before any collection. The typed CLI
        flags carry authority over the document's explicit values; the document read stays under a
        parse guard; the library's env layer is scrubbed so ``web.yml`` is the single source; the
        console formatter lands unconditionally — it is not allure-gated.

        The resolved strict and interactive options re-store from the validated document plus the
        CLI flags — never from the raw parse the option descriptors would cast: a string-typed
        ``"false"``/``"no"`` the model coerces to false must not surface as true through the
        descriptor's bare ``bool()`` cast.

        Raises:
            ValueError: The document is unparsable or invalid; the message names the document
                location (the pydantic detail chained).
        """
        strict_flag = bool(self.pytest_config.getoption("strict_mode", default=False))
        interactive_flag = bool(self.pytest_config.getoption("interactive", default=False))

        try:
            document = self.plugin_config
        except YAMLError as exc:
            raise ValueError(f"{defaults.WEB_CONFIG_FILE}: unparsable document: {exc}") from exc

        self.activation = validate_web_config(dict(document))

        self.strict = self.activation.strict or strict_flag
        self.interactive = self.activation.interactive or interactive_flag

        _scrub_prettyplay_env()

        install_event_log_formatter()

    @pytest.fixture
    def web(self, request: pytest.FixtureRequest) -> t.Iterator[PrettyPlay]:
        """Build the per-test prettyplay runtime and close it after the test.

        The cache address derives from the requesting item itself — the root is the activation's
        ``cache_root`` when set, otherwise the absolute directory of the test's own module file
        (never the cwd); the path is parametrize-agnostic, the key parametrize-aware. Cleanup is
        disabled: the persistence mode of the committed-cache workflow keeps every cached file of
        the test's key.

        Args:
            request: The fixture request of the test being set up.

        Yields:
            The opened prettyplay runtime — ``step`` / ``expect`` / ``group`` / ``run_on_page``.
        """
        activation = self._require_activation()

        item = request.node
        root = activation.cache_root or str(item.path.parent.resolve())

        config = build_pretty_config(activation, self.strict, self.interactive)

        if not activation.cache_root:
            config = config.model_copy(update={"cache_root": root})

        runtime = PrettyPlay(item.name, web_cache_path(item), cleanup=False, config=config)

        if allure_hooks.allure is not None:
            runtime.add_hooks(AllureStepHooks(runtime))

        logger.debug("web runtime built", extra={"cache_key": item.name, "cache_root": config.cache_root})

        with runtime as play:
            yield play

    def _require_activation(self) -> PrettyConfig:
        """The validated activation the web fixture builds the runtime from.

        Returns:
            The configuration built by ``configure``.

        Raises:
            RuntimeError: ``configure`` has not run — the fixture only works on a configured
                plugin.
        """
        if self.activation is None:
            raise RuntimeError("the web plugin is not configured — configure() did not run")

        return self.activation
