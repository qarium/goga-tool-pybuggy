"""HttpEngine: the http kind engine — a wiremock http mock service."""

import logging

import requests
from testcontainers.core.container import DockerContainer

from .base import BaseEngine
from .operation import DataOperation

logger = logging.getLogger(__name__)

DEFAULT_IMAGE = "wiremock/wiremock:3.13.0"
CONTAINER_PORT = 8080
SANDBOX_LABELS = {"pybuggy-sandbox": "true"}

PLANE_TIMEOUT = 5
HEALTHY_STATUS = 200
NOT_FOUND_STATUS = 404
WRITE_OK_MIN_STATUS = 200
WRITE_OK_MAX_STATUS = 299


class HttpEngine(BaseEngine):
    """http kind engine: wiremock container, admin-API stub plane, mappings-reset wipe.

    The container runs the product-pinned wiremock image unless the service entry overrides
    it — stub traffic and the admin API share the one published port. The data plane is plain
    ``requests`` posting stub mappings over the admin API; the declarations pass through as
    given, so matching, priority, delays and faults stay available to authors. Reset drops the
    API-created mappings over the admin reset endpoint — back to the effective empty state —
    and the base replays the journal through the same execution path.

    Attributes:
        config: The service declaration — name, kind, image override, probe.
    """

    _container_port = CONTAINER_PORT

    def _build_container(self) -> DockerContainer:
        """Build the wiremock container — pinned image, labels, published admin port.

        Returns:
            The built, not yet started, wiremock container.
        """
        image = self.config.image or DEFAULT_IMAGE
        container = DockerContainer(image, labels=SANDBOX_LABELS)
        container.with_exposed_ports(CONTAINER_PORT)

        self._attach_network(container)

        return container

    def _wait_ready(self) -> None:
        """Wait for the wiremock admin endpoint, bounded by the declared deadline.

        A probe loop at the declared bounds — the 3.x health endpoint is the primary signal;
        a 404 answer falls back to the mappings endpoint of older versions. Connection
        failures keep the loop probing.

        Raises:
            RuntimeError: The declared deadline expired; the lifecycle wrappers convert it
                into ``EngineError`` naming the service, the waited check and the deadline.
        """
        address = self.address
        base_url = f"http://{address.host}:{address.port}/__admin"
        timeout, interval = self._readiness_bounds

        def attempt() -> bool:
            try:
                ready = self._admin_ready(base_url)
            except requests.RequestException:
                logger.debug("wiremock admin probe retry", extra={"service": self.config.name, "admin": base_url})

                return False

            return ready

        self._probe_until(timeout, interval, attempt, f"admin endpoint {base_url} did not succeed")
        logger.debug("wiremock admin ready", extra={"service": self.config.name, "admin": base_url})

    def _open_plane(self) -> None:
        """Open the admin data plane.

        The plane is stateless ``requests`` — there is no client to hold; the step only marks
        the plane open.
        """
        logger.debug("wiremock plane open", extra={"service": self.config.name})

    def _execute(self, operation: DataOperation) -> None:
        """Execute one http operation over the admin API.

        A ``stub`` operation posts the mapping object to the admin mappings endpoint — the
        declaration passes through as given; a non-2xx answer maps onto a readable error
        naming the mapping.

        Args:
            operation: The ``stub`` operation to execute.

        Raises:
            RuntimeError: The mapping post failed — the message names the mapping.
        """
        mapping = operation.payload
        response = requests.post(self._admin_url("/mappings"), json=mapping, timeout=PLANE_TIMEOUT)

        if not WRITE_OK_MIN_STATUS <= response.status_code <= WRITE_OK_MAX_STATUS:
            raise RuntimeError(_stub_failure(mapping, response))

        logger.debug("wiremock stub created", extra={"service": self.config.name, "mapping": _mapping_label(mapping)})

    def _wipe(self) -> None:
        """Reset the mappings over the admin API — back to the effective empty state.

        The API-created mappings drop; the loaded mapping set stays. The base replays the
        journal after the wipe through the same execution path.

        Raises:
            RuntimeError: The reset post failed.
        """
        response = requests.post(self._admin_url("/mappings/reset"), timeout=PLANE_TIMEOUT)

        if not WRITE_OK_MIN_STATUS <= response.status_code <= WRITE_OK_MAX_STATUS:
            raise RuntimeError(f"mappings reset failed with status {response.status_code}")

        logger.debug("wiremock mappings reset", extra={"service": self.config.name})

    def _close_plane(self) -> None:
        """Close the admin data plane; stateless ``requests`` needs no close."""

    def _admin_ready(self, base_url: str) -> bool:
        """Probe the admin endpoint for readiness — health first, mappings fallback.

        Args:
            base_url: The mapped admin base URL of the service.

        Returns:
            True when the admin endpoint answered ready.
        """
        health = requests.get(f"{base_url}/health", timeout=PLANE_TIMEOUT)

        if health.status_code == HEALTHY_STATUS:
            return True

        if health.status_code != NOT_FOUND_STATUS:
            return False

        mappings = requests.get(f"{base_url}/mappings", timeout=PLANE_TIMEOUT)

        return mappings.status_code == HEALTHY_STATUS

    def _admin_url(self, path: str) -> str:
        """Build one admin API URL against the mapped address.

        Args:
            path: The admin API path of the request.

        Returns:
            The full admin URL of the path.
        """
        address = self.address

        return f"http://{address.host}:{address.port}/__admin{path}"


def _mapping_label(mapping: dict[str, object]) -> str:
    """Build the identifying label of one mapping declaration.

    Args:
        mapping: The mapping declaration as given.

    Returns:
        The mapping name when declared, else the matched request path, else a placeholder.
    """
    name = mapping.get("name")

    if isinstance(name, str) and name:
        return name

    request = mapping.get("request")

    if isinstance(request, dict):
        for key in ("urlPath", "urlPathPattern", "url", "urlPattern"):
            value = request.get(key)

            if isinstance(value, str) and value:
                return value

    return "unnamed mapping"


def _stub_failure(mapping: dict[str, object], response: requests.Response) -> str:
    """Build the readable failure text of one rejected mapping post.

    Args:
        mapping: The mapping declaration the post carried.
        response: The non-2xx answer of the server.

    Returns:
        The failure text naming the mapping, the status and the server's detail.
    """
    try:
        detail = str(response.json())
    except ValueError:
        detail = response.text

    return f"stub '{_mapping_label(mapping)}' failed with status {response.status_code}: {detail}"
