"""SandboxPlugin entity: the fixture-driven pytest activation of the sandbox."""

import logging
import typing as t

import pytest
from pluginator import define
from yaml import YAMLError

from ..sandbox import Sandbox
from ..sandbox.config import SandboxConfig, validate_sandbox_config
from . import defaults

logger = logging.getLogger(__name__)

_MARKER_HELP = "pybuggy_services: per-test sandbox data presets (applied by the pybuggy sandbox)"


@define.plugin("pybuggy-sandbox", config=defaults.SANDBOX_CONFIG_FILE)
class SandboxPlugin:
    """Pluginator plugin exposing the product-owned ``sandbox`` fixtures.

    The sandbox document is the plugin's config: pluginator reads
    ``.goga/tools/pybuggy/sandbox.yml`` into ``plugin_config``, and ``configure()`` validates
    it into the activation — an invalid document fails the run at configphase, before any
    collection or container. Zero options; the installation entry constructs the plugin only
    when the document is present.

    Attributes:
        plugin_config: Anchor declaration; ``BasePlugin`` supplies the parsed document dict.
        activation: The validated sandbox configuration; set by ``configure``.
    """

    plugin_config: dict

    def __init__(self) -> None:
        """Initialize the plugin; the activation arrives with ``configure``."""
        super().__init__()

        self.activation: SandboxConfig | None = None

    def configure(self) -> None:
        """Register the ``pybuggy_services`` marker and validate the document into the activation.

        Pluginator lifecycle callback at pytest configphase, before collection — registering
        the marker here keeps applying it in test modules warning-free, and an invalid
        document fails the run before any container starts.

        Raises:
            ValueError: The document is unparsable, empty, or invalid; the message names the
                document location and the offending entry.
        """
        self.pytest_config.addinivalue_line("markers", _MARKER_HELP)

        try:
            document = self.plugin_config
        except YAMLError as exc:
            raise ValueError(f"{self.meta.config_file}: unparsable document: {exc}") from exc

        if not document:
            raise ValueError(
                f"{self.meta.config_file}: the document is empty — a sandbox document must carry the instance entry"
            )

        self.activation = validate_sandbox_config(document, self.meta.config_file)

        logger.info(
            "sandbox plugin armed",
            extra={"image": self.activation.instance.image, "services": list(self.activation.services)},
        )

    @pytest.fixture(scope="session")
    def sandbox(self) -> t.Iterator[Sandbox]:
        """The session sandbox — started lazily on first use, stopped on finalization.

        Yields:
            The running sandbox — the same object for the whole session.
        """
        activation = self._require_activation()

        sandbox = Sandbox(activation)
        sandbox.start()

        logger.info("sandbox session started", extra={"base_url": sandbox.base_url})

        yield sandbox

        sandbox.stop()

    @pytest.fixture(autouse=True)
    def _sandbox_test_batch(self, request: pytest.FixtureRequest) -> None:
        """Give the next sandbox test a fresh baseline and its marked presets.

        Inert for tests that do not use the sandbox — the fixturenames guard keeps the
        globally-autouse registration harmless for the rest of the suite.

        Args:
            request: The fixture request of the test being set up.
        """
        if "sandbox" not in request.fixturenames:
            return

        sandbox = request.getfixturevalue("sandbox")

        sandbox.clear()
        sandbox.new_test_batch()

        enqueued = 0

        for marker in request.node.iter_markers("pybuggy_services"):
            enqueued += sandbox.enqueue_presets(marker.kwargs.get("presets", {}))

        logger.debug("presets enqueued", extra={"node": request.node.name, "operations": enqueued})

    def _require_activation(self) -> SandboxConfig:
        """The validated activation the session fixture starts the sandbox from.

        Returns:
            The configuration built by ``configure``.

        Raises:
            RuntimeError: ``configure`` has not run — the fixtures only work on a configured
                plugin.
        """
        if self.activation is None:
            raise RuntimeError("the sandbox plugin is not configured — configure() did not run")

        return self.activation
