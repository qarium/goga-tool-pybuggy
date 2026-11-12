"""WebPlugin entity: the pluginator activation of the web test kind — the ``web`` fixture.

Owns the fixed ``web.yml`` key set (``WebConfigKeys``): the file name plus the 20 config keys
mirroring the ``PrettyConfig`` field names 1:1 — every config key binds the ``plugin_config_key``
of its directive option (the standard pluginator loading resolves the values), and the set is
consumed data-driven by the init survey, the commented-example documentation, and the
installation gate.
"""

import logging
import os
import re
import typing as t
import warnings
from enum import Enum

import pytest
from pluginator import CommandLine, define
from prettyplay import PrettyConfig, PrettyPlay
from pydantic import ValidationError
from yaml import YAMLError

from ..web import allure_hooks
from ..web.allure_hooks import AllureStepHooks
from ..web.logging_setup import install_event_log_formatter
from ..web.pretty import build_pretty_config
from . import defaults
from .discovery import LOADER_SECTION, load_fixture_plugins, loader_section_of
from .loaders import BaseLoader

logger = logging.getLogger(__name__)


class WebConfigKeys(str, Enum):
    """Fixed value set of the web config keys — the canonical key set of ``web.yml``.

    Members map to the lowercase ``web.yml`` key strings; ``FILENAME`` names the document file;
    the plugins-cell ``defaults.WEB_CONFIG_FILE`` constant (``.goga/tools/pybuggy/`` plus the
    file name) binds the ``@define.plugin`` config and gates the installation; every config
    member binds the ``plugin_config_key`` of its directive option of the plugin. Member order is
    contract order (the documenter walks it). Fixed set: do not add, remove, or rename members or
    change their values — the init survey, the example documentation, the validation alignment,
    and the installation gate depend on the exact key set.
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
    REQUEST_MAX_TOKENS = "request_max_tokens"
    SEND_SCREENSHOTS = "send_screenshots"
    GENERATION_APPROVE = "generation_approve"
    PROBE_TIMEOUT = "probe_timeout"
    CACHE_ROOT = "cache_root"
    BROWSER = "browser"


# Prefix of the library's env layer — every matching variable is scrubbed at configphase.
_PRETTYPLAY_ENV_PREFIX: t.Final[str] = "PRETTYPLAY_"

# Characters unsafe as one path segment of the node-name tail — both separators, the
# Windows-forbidden set, and whitespace; every run flattens to a single dash, so a parametrize
# id never nests directories, escapes the cache root, or carries spaces.
_FLATTENED_CHARS: t.Final[re.Pattern[str]] = re.compile(r'[/\\:*?"<>|\s]+')

# Help line of the per-test generation-instruction marker — registered at configphase so
# applying it in test modules stays warning-free.
_GENERATION_PROMPT_MARKER_HELP: t.Final[str] = (
    "pybuggy_generation_prompt: per-test extra generation instructions (applied by the pybuggy web plugin)"
)


def _scrub_prettyplay_env() -> None:
    """Remove every ``PRETTYPLAY_`` environment variable of the process.

    ``web.yml`` is the single configuration source of a web run (the typed ``--browser-endpoint``
    flag — the single CLI exception — lands on the document copy before the validation) — the
    library's env layer must never override it. The scrub is permanent for the run and race-free:
    configphase is single-threaded.
    """
    names = sorted(name for name in os.environ if name.startswith(_PRETTYPLAY_ENV_PREFIX))

    for name in names:
        os.environ.pop(name, None)

    if names:
        logger.info("prettyplay env layer scrubbed", extra={"variables": names})
    else:
        logger.debug("prettyplay env layer scrubbed", extra={"variables": names})


def _readable_node_name(name: str) -> str:
    """Decode the pytest ASCII escape of a non-latin node name back into readable characters.

    pytest escapes every non-ASCII id through ``unicode_escape`` (``имя`` becomes
    ``\\u0438\\u043c\\u044f``) — this restores the characters, so a Cyrillic parameter case
    keeps a readable cache directory instead of a ``-u0438-`` tail. A name that never went
    through the escape (pure ASCII without a backslash, or an escaping-disabled run keeping
    the real letters) returns unchanged; an undecodable one returns unchanged too — the
    readable form is cosmetic, never a failure of the run.

    Args:
        name: The item's node name.

    Returns:
        The name with pytest's escape sequences restored to characters.
    """
    if "\\" not in name or not name.isascii():
        return name

    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")  # a lone un-escaped backslash passes through
            return name.encode("ascii").decode("unicode_escape")
    except (UnicodeError, ValueError):
        return name


def web_cache_path(item: pytest.Item) -> str:
    """Compute the per-test step-cache path from the requesting test item.

    Args:
        item: The pytest item of the requesting test.

    Returns:
        The posix-relative subdirectory inside the cache root —
        ``<module_stem>/<ClassName>/<test_name>`` with a class, ``<module_stem>/<test_name>``
        without; ``<test_name>`` is the item's node name with pytest's ASCII escape of a
        non-latin id decoded back, so a parametrized test addresses
        ``<test_name>[<param_id>]`` — one readable directory per parameter case.
    """
    segments = [item.path.stem]

    cls = getattr(item, "cls", None)
    if cls is not None:
        segments.append(cls.__name__)

    segments.append(_FLATTENED_CHARS.sub("-", _readable_node_name(item.name)))

    return "/".join(segments)


@define.plugin("pybuggy-web", config=defaults.WEB_CONFIG_FILE)
class WebPlugin:
    """Pluginator plugin exposing the ``web`` fixture of the web test kind.

    Every ``web.yml`` directive loads through its own plugin option — the standard pluginator
    chain (the document key, then the CLI layer of the three flags, then ``default_from``)
    resolves each value. The directive options route their values without casting
    (``strict=False``): the library ``PrettyConfig`` stays the single caster and validator — the
    bare descriptor cast would flip a string-typed ``"false"`` boolean to true, coerce shapes the
    model must reject, and miss the library defaults of the numeric directives. The directives
    whose empty option fallback would diverge from the library default carry a ``default_from``
    computed from the model — the model is the single default source.

    ``configure()`` performs only what the standard loading cannot: the document gates (the parse
    guard, the mapping and the empty rejection), the CLI authority of the mode flags (the chain
    resolves the document before the CLI; a typed flag forces its mode on), the typed
    ``--browser-endpoint`` injection into the browser group (a nested document path no flat
    option key addresses), and the validation of the composed option values into the activation —
    the single gate carrying the library validators, with the unknown document keys riding along
    to its forbid rule; an invalid configuration fails the run at configphase, before any
    collection or browser. The foreign ``pipelines`` section — the web autonomy axis, read by the
    tool's own resolver, never by the plugin — never rides along, and neither does the
    ``loader:`` section: the external fixture packages/modules a project wires in feed the shared
    fixture discovery at construction (`discovery`), the one install-time step besides the
    activation. The library's env layer is scrubbed so ``web.yml`` is the single configuration
    source; the console formatter lands unconditionally — it is not allure-gated.

    Attributes:
        plugin_config: Anchor declaration; ``BasePlugin`` supplies the parsed document dict.
        provider: The LLM provider directive — ``{openai, anthropic}``; default ``openai``.
        base_url: The custom LLM API endpoint directive; default ``""``.
        model: The shared LLM model directive; default ``""``.
        generation_model: The generation model override directive; default ``""``.
        classification_model: The classification model override directive; default ``""``.
        generation_prompt: The extra generation instructions directive; default ``""``.
        classification_prompt: The extra classification instructions directive; default ``""``.
        strict: The replay-only mode directive — zero LLM calls, a cache miss fails — plus the
            ``--strict-mode`` flag authority.
        interactive: The interactive step healing directive plus the ``--interactive`` flag
            authority.
        polling_timeout: The settle-window directive; nullable — ``None`` keeps polling off.
        polling_delay: The settle-pause directive; default ``0.5``.
        generation_attempts: The generation attempt budget directive; default ``3``.
        healing_attempts: The healing attempt budget directive; default ``2``.
        llm_request_attempts: The LLM request attempt budget directive; default ``3``.
        request_max_tokens: The anthropic completion cap directive; default ``16384``.
        send_screenshots: The screenshot attachment directive; default ``False``.
        generation_approve: The compliance gate directive; default ``True``.
        probe_timeout: The probe bound directive; default ``0``.
        cache_root: The step-cache root directive; default ``""``.
        browser: The nested browser group directive — the raw section mapping; default ``{}``.
        browser_endpoint: The typed ``--browser-endpoint`` CLI value — a remote Playwright endpoint
            overriding the ``browser.endpoint`` directive at the configure-time injection;
            ``None`` when the flag is not typed.
        activation: The validated web config — the library ``PrettyConfig``; set by ``configure``,
            ``None`` before it.
    """

    plugin_config: dict

    provider = define.option(
        str, plugin_config_key=WebConfigKeys.PROVIDER, default_from="_default_provider", strict=False
    )
    base_url = define.option(str, plugin_config_key=WebConfigKeys.BASE_URL, strict=False)
    model = define.option(str, plugin_config_key=WebConfigKeys.MODEL, strict=False)
    generation_model = define.option(str, plugin_config_key=WebConfigKeys.GENERATION_MODEL, strict=False)
    classification_model = define.option(str, plugin_config_key=WebConfigKeys.CLASSIFICATION_MODEL, strict=False)
    generation_prompt = define.option(str, plugin_config_key=WebConfigKeys.GENERATION_PROMPT, strict=False)
    classification_prompt = define.option(str, plugin_config_key=WebConfigKeys.CLASSIFICATION_PROMPT, strict=False)
    strict = define.option(
        bool,
        plugin_config_key=WebConfigKeys.STRICT,
        command_line=CommandLine("--strict-mode", action="store_true", help="Strict mode for using cache only"),
        strict=False,
    )
    interactive = define.option(
        bool,
        plugin_config_key=WebConfigKeys.INTERACTIVE,
        command_line=CommandLine("--interactive", action="store_true", help="Interactive step healing mode"),
        strict=False,
    )
    polling_timeout = define.option(float, plugin_config_key=WebConfigKeys.POLLING_TIMEOUT, nullable=True, strict=False)
    polling_delay = define.option(
        float, plugin_config_key=WebConfigKeys.POLLING_DELAY, default_from="_default_polling_delay", strict=False
    )
    generation_attempts = define.option(
        int,
        plugin_config_key=WebConfigKeys.GENERATION_ATTEMPTS,
        default_from="_default_generation_attempts",
        strict=False,
    )
    healing_attempts = define.option(
        int, plugin_config_key=WebConfigKeys.HEALING_ATTEMPTS, default_from="_default_healing_attempts", strict=False
    )
    llm_request_attempts = define.option(
        int,
        plugin_config_key=WebConfigKeys.LLM_REQUEST_ATTEMPTS,
        default_from="_default_llm_request_attempts",
        strict=False,
    )
    request_max_tokens = define.option(
        int,
        plugin_config_key=WebConfigKeys.REQUEST_MAX_TOKENS,
        default_from="_default_request_max_tokens",
        strict=False,
    )
    send_screenshots = define.option(bool, plugin_config_key=WebConfigKeys.SEND_SCREENSHOTS, strict=False)
    generation_approve = define.option(
        bool,
        plugin_config_key=WebConfigKeys.GENERATION_APPROVE,
        default_from="_default_generation_approve",
        strict=False,
    )
    probe_timeout = define.option(float, plugin_config_key=WebConfigKeys.PROBE_TIMEOUT, strict=False)
    cache_root = define.option(str, plugin_config_key=WebConfigKeys.CACHE_ROOT, strict=False)
    browser = define.option(dict, plugin_config_key=WebConfigKeys.BROWSER, strict=False)
    browser_endpoint = define.option(
        str,
        nullable=True,
        command_line=CommandLine(
            "--browser-endpoint", action="store", help="Remote Playwright endpoint; overrides web.yml browser.endpoint"
        ),
    )

    # Library defaults of the directives whose empty option fallback would diverge — computed from
    # the model, the single default source; an unset directive resolves to the library default.
    _default_provider: t.Final = PrettyConfig.model_fields[WebConfigKeys.PROVIDER].get_default()
    _default_polling_delay: t.Final = PrettyConfig.model_fields[WebConfigKeys.POLLING_DELAY].get_default()
    _default_generation_attempts: t.Final = PrettyConfig.model_fields[WebConfigKeys.GENERATION_ATTEMPTS].get_default()
    _default_healing_attempts: t.Final = PrettyConfig.model_fields[WebConfigKeys.HEALING_ATTEMPTS].get_default()
    _default_llm_request_attempts: t.Final = PrettyConfig.model_fields[WebConfigKeys.LLM_REQUEST_ATTEMPTS].get_default()
    _default_request_max_tokens: t.Final = PrettyConfig.model_fields[WebConfigKeys.REQUEST_MAX_TOKENS].get_default()
    _default_generation_approve: t.Final = PrettyConfig.model_fields[WebConfigKeys.GENERATION_APPROVE].get_default()

    def __init__(self, *, context: dict, loaders: list[BaseLoader] | None = None) -> None:
        """Initialize the plugin and synchronously register the configured fixture plugins.

        The ``loader:`` section of the web document joins the explicit ``loaders`` in the shared
        discovery; it runs synchronously here — pytest reads ``pytest_plugins`` once the conftest
        import finishes — and an unparsable document defers to the configure-time gate (no
        discovery, the run fails at configphase with the clean error).

        Args:
            context: Namespace dict the plugin installs into; its ``pytest_plugins`` key is
                populated here.
            loaders: Explicit loaders in addition to the ``loader:`` section; none by default —
                the web kind carries no default package.
        """
        super().__init__()

        self.activation: PrettyConfig | None = None

        load_fixture_plugins(context, loaders or [], loader_section_of(self))

    def configure(self) -> None:
        """Assemble the activation from the resolved options and ready the runtime environment.

        Pluginator lifecycle callback at pytest configphase, before any collection. The
        ``pybuggy_generation_prompt`` marker is registered first — applying the per-test
        generation-instruction decorator in test modules stays warning-free. The directive
        values are already loaded — the standard option chain resolved them; what remains here is
        only what the standard loading cannot do. The document gates run next (the parse guard,
        the non-mapping and the empty rejection), so the option reads below never meet a broken
        reader. The typed ``--browser-endpoint`` is injected into a copy of the resolved browser
        group before validation — the injected value passes the same gate, and the typed empty
        string forces the local launch. The validation is the composed option values plus the
        unknown document keys riding along — the library forbid rule names a mistyped key — with
        a violation wrapped into the clean error naming ``web.yml`` (the pydantic detail chained).

        The resolved strict and interactive options re-store from the validated activation plus
        the typed flags — never from the raw parse the options route: a string-typed
        ``"false"``/``"no"`` the model coerces to false must not surface as true.

        Raises:
            ValueError: The document is unparsable, non-mapping, empty, or invalid; the message
                names the document location (the pydantic detail chained).
        """
        self.pytest_config.addinivalue_line("markers", _GENERATION_PROMPT_MARKER_HELP)

        strict_flag = bool(self.pytest_config.getoption("strict_mode", default=False))
        interactive_flag = bool(self.pytest_config.getoption("interactive", default=False))
        endpoint_flag = self.pytest_config.getoption("browser_endpoint", default=None)

        try:
            parsed = self.plugin_config
        except YAMLError as exc:
            raise ValueError(f"{defaults.WEB_CONFIG_FILE}: unparsable document: {exc}") from exc

        if not isinstance(parsed, dict):
            raise ValueError(f"{defaults.WEB_CONFIG_FILE}: the document must parse to a mapping")

        document = dict(parsed)

        # The foreign sections — the web autonomy axis consumed by the tool's resolver and the
        # fixture-discovery section consumed at install time — never ride into the validation;
        # dropped from the copy so the gates below judge the web keys only.
        document.pop("pipelines", None)
        document.pop(LOADER_SECTION, None)

        if not document:
            raise ValueError(
                f"{defaults.WEB_CONFIG_FILE}: the document is empty — "
                "it must carry at least the provider and the browser name"
            )

        # Unknown document keys ride into the validation — the library forbid rule names them.
        directives = {member.value for member in WebConfigKeys if member is not WebConfigKeys.FILENAME}
        unknown = {key: value for key, value in document.items() if key not in directives}

        # A null browser group means an empty one; a typed endpoint lands on a copy of the group —
        # a nested document path no flat option key addresses, and the read document stays intact.
        browser = {} if self.browser is None else self.browser

        if endpoint_flag is not None:
            browser = dict(browser) if isinstance(browser, dict) else {}
            browser["endpoint"] = endpoint_flag

        try:
            self.activation = PrettyConfig.model_validate(
                {
                    WebConfigKeys.PROVIDER: self.provider,
                    WebConfigKeys.BASE_URL: self.base_url,
                    WebConfigKeys.MODEL: self.model,
                    WebConfigKeys.GENERATION_MODEL: self.generation_model,
                    WebConfigKeys.CLASSIFICATION_MODEL: self.classification_model,
                    WebConfigKeys.GENERATION_PROMPT: self.generation_prompt,
                    WebConfigKeys.CLASSIFICATION_PROMPT: self.classification_prompt,
                    WebConfigKeys.STRICT: self.strict,
                    WebConfigKeys.INTERACTIVE: self.interactive,
                    WebConfigKeys.POLLING_TIMEOUT: self.polling_timeout,
                    WebConfigKeys.POLLING_DELAY: self.polling_delay,
                    WebConfigKeys.GENERATION_ATTEMPTS: self.generation_attempts,
                    WebConfigKeys.HEALING_ATTEMPTS: self.healing_attempts,
                    WebConfigKeys.LLM_REQUEST_ATTEMPTS: self.llm_request_attempts,
                    WebConfigKeys.REQUEST_MAX_TOKENS: self.request_max_tokens,
                    WebConfigKeys.SEND_SCREENSHOTS: self.send_screenshots,
                    WebConfigKeys.GENERATION_APPROVE: self.generation_approve,
                    WebConfigKeys.PROBE_TIMEOUT: self.probe_timeout,
                    WebConfigKeys.CACHE_ROOT: self.cache_root,
                    WebConfigKeys.BROWSER: browser,
                }
                | unknown
            )
        except ValidationError as err:
            raise ValueError(f"{defaults.WEB_CONFIG_FILE}: invalid web config document") from err

        self.strict = self.activation.strict or strict_flag
        self.interactive = self.activation.interactive or interactive_flag

        _scrub_prettyplay_env()

        install_event_log_formatter()

    @pytest.fixture
    def web(self, request: pytest.FixtureRequest) -> t.Iterator[PrettyPlay]:
        """Build the per-test prettyplay runtime and close it after the test.

        The cache address derives from the requesting item itself — the root is the activation's
        ``cache_root`` when set, otherwise the absolute directory of the test's own module file
        (never the cwd); the path and the key are both the item's own name — parametrize-aware,
        one cache directory per parameter case. The item's
        ``pybuggy_generation_prompt`` marker texts join (written order, top decorator first) into
        the generation prompt of exactly this test. Cleanup is disabled: the persistence mode of
        the committed-cache workflow keeps every cached file of the test's key.

        Args:
            request: The fixture request of the test being set up.

        Yields:
            The opened prettyplay runtime — ``step`` / ``expect`` / ``group`` / ``run_on_page``.
        """
        activation = self._require_activation()

        item = request.node
        root = activation.cache_root or str(item.path.parent.resolve())

        texts = [marker.kwargs.get("text", "") for marker in item.iter_markers("pybuggy_generation_prompt")]
        extras = "\n".join(text for text in reversed(texts) if text)

        config = build_pretty_config(activation, self.strict, self.interactive, prompt_extra=extras)

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
