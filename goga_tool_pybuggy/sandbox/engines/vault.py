"""VaultEngine: the vault kind engine — a dev-mode vault secrets mock instance."""

import logging
import time

import requests
from testcontainers.core.container import DockerContainer

from .base import BaseEngine, reserve_port
from .operation import DataOperation

logger = logging.getLogger(__name__)

DEFAULT_IMAGE = "hashicorp/vault:1.17"
CONTAINER_PORT = 8200
DEV_ROOT_TOKEN = "sandbox-root"
DEV_LISTEN_ADDRESS = f"0.0.0.0:{CONTAINER_PORT}"
DEV_COMMAND = "server -dev"
SANDBOX_LABELS = {"pybuggy-sandbox": "true"}

READINESS_TIMEOUT = 30.0
READINESS_INTERVAL = 0.5
PLANE_TIMEOUT = 5
HEALTHY_STATUS = 200
WRITE_OK_MIN_STATUS = 200
WRITE_OK_MAX_STATUS = 299
RESTART_TIMEOUT = 10


class VaultEngine(BaseEngine):
    """vault kind engine: dev-mode container, KV v2 HTTP plane, restart-based wipe.

    The container runs the product-pinned vault image in dev mode unless the instance config
    overrides it — in-memory storage, plain HTTP, auto-initialized and auto-unsealed, with the
    fixed dev root token. The data plane is plain ``requests`` with the token header writing
    secrets over the KV v2 API. Reset restarts the same container — the published address
    survives, the in-memory storage empties, and the journal replay re-establishes the declared
    secrets.

    Attributes:
        config: The instance declaration — name, kind, image override.
    """

    _container_port = CONTAINER_PORT

    def _build_container(self) -> DockerContainer:
        """Build the vault dev container — pinned image, labels, fixed port, dev env, dev command.

        The container's vault port is published on a reserved fixed host port, not a
        dynamically assigned one: a restart-based reset re-rolls dynamic port assignments,
        and the mapped address — already rendered into the service env — must survive the
        reset.

        Returns:
            The built, not yet started, vault container.
        """
        image = self.config.image or DEFAULT_IMAGE
        container = DockerContainer(image, labels=SANDBOX_LABELS)
        container.with_bind_ports(CONTAINER_PORT, reserve_port())
        container.with_env("VAULT_DEV_ROOT_TOKEN_ID", DEV_ROOT_TOKEN)
        container.with_env("VAULT_DEV_LISTEN_ADDRESS", DEV_LISTEN_ADDRESS)
        container.with_command(DEV_COMMAND)

        self._attach_network(container)

        return container

    def _wait_ready(self) -> None:
        """Wait for the vault health endpoint.

        A probe loop with a deadline — the endpoint answers 200 once the server is initialized,
        unsealed and active; the pre-ready codes (429, 501, 503) keep the loop probing.

        Raises:
            RuntimeError: The health endpoint did not succeed within the deadline.
        """
        host = self._container.get_container_host_ip()
        port = int(self._container.get_exposed_port(self._container_port))
        url = f"http://{host}:{port}/v1/sys/health"
        deadline = time.monotonic() + READINESS_TIMEOUT

        while time.monotonic() < deadline:
            try:
                response = requests.get(url, timeout=PLANE_TIMEOUT)

                if response.status_code == HEALTHY_STATUS:
                    logger.debug("vault health ready", extra={"instance": self.config.name, "health": url})

                    return
            except requests.RequestException:
                logger.debug("vault health probe retry", extra={"instance": self.config.name, "health": url})

            time.sleep(READINESS_INTERVAL)

        raise RuntimeError(f"health endpoint {url} did not succeed within {READINESS_TIMEOUT:.0f}s")

    def _open_plane(self) -> None:
        """Open the HTTP data plane.

        The plane is stateless ``requests`` with the token header — there is no client to hold;
        the step only marks the plane open.
        """
        logger.debug("vault plane open", extra={"instance": self.config.name})

    def _execute(self, operation: DataOperation) -> None:
        """Execute one vault operation through the KV v2 HTTP API.

        A ``put`` operation writes the secret at the payload path — a non-2xx answer maps onto a
        readable error naming the path, the status and the server's error detail.

        Args:
            operation: The ``put`` operation to execute.

        Raises:
            RuntimeError: The write failed — the message names the path and the status.
        """
        path = operation.payload["path"]
        response = requests.post(
            self._data_url(path),
            headers=_token_headers(),
            json={"data": operation.payload["data"]},
            timeout=PLANE_TIMEOUT,
        )

        if not WRITE_OK_MIN_STATUS <= response.status_code <= WRITE_OK_MAX_STATUS:
            raise RuntimeError(_write_failure(path, response))

        logger.debug("vault secret written", extra={"instance": self.config.name, "path": path})

    def _wipe(self) -> None:
        """Restart the same container — empty in-memory storage, unchanged address.

        The SDK restart preserves the port bindings; readiness is re-waited afterwards. No plane
        client exists to rebuild — ``requests`` is stateless.

        Raises:
            RuntimeError: The restart or the post-restart health wait failed.
        """
        wrapped = self._container.get_wrapped_container()
        wrapped.restart(timeout=RESTART_TIMEOUT)
        logger.debug("vault container restarted", extra={"instance": self.config.name})

        self._wait_ready()

    def _close_plane(self) -> None:
        """Close the HTTP data plane; stateless ``requests`` needs no close."""

    def _data_url(self, path: object) -> str:
        """Build the KV v2 data URL of one secret path against the mapped address.

        Args:
            path: The secret path of the payload.

        Returns:
            The KV v2 write/read URL of the path.
        """
        address = self.address

        return f"http://{address.host}:{address.port}/v1/secret/data/{path}"


def _token_headers() -> dict[str, str]:
    """Build the token header of every data-plane request.

    Returns:
        The fixed dev root token header — a test-fixture credential, never logged.
    """
    return {"X-Vault-Token": DEV_ROOT_TOKEN}


def _write_failure(path: object, response: requests.Response) -> str:
    """Build the readable failure text of one rejected write.

    Args:
        path: The secret path the write targeted.
        response: The non-2xx answer of the server.

    Returns:
        The failure text naming the path, the status and the server's error detail.
    """
    try:
        errors = response.json().get("errors", [])
    except ValueError:
        errors = []

    detail = ", ".join(str(error) for error in errors)
    failure = f"write at '{path}' failed with status {response.status_code}"

    if detail:
        return f"{failure}: {detail}"

    return failure
