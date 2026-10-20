"""InstanceConfig entity: the instance-under-test entry of the sandbox document."""

from pydantic import BaseModel, ConfigDict, field_validator

from .probe import ProbeConfig


class InstanceConfig(BaseModel):
    """Instance-under-test entry of the sandbox configuration.

    Attributes:
        image: Container image of the instance under test.
        env: Environment values; values may carry service address placeholders resolved at
            sandbox start.
        port: Container port the service serves on.
        base_path: URL path prefix of the service API; an empty value keeps the bare
            ``http://<host>:<port>`` address.
        probe: Readiness declaration — the health path and the wait bounds; ``None`` keeps the
            default wait: port readiness with the default deadline and interval.
    """

    model_config = ConfigDict(kw_only=True, extra="forbid")

    image: str
    env: dict[str, str] = {}
    port: int
    base_path: str = ""
    probe: ProbeConfig | None = None

    @field_validator("base_path")
    @classmethod
    def _base_path_starts_with_a_slash(cls, value: str) -> str:
        """Require the leading slash of the API path prefix.

        The sandbox base URL concatenates the prefix onto ``http://<host>:<port>`` — a path
        without the slash misforms every bound request URL and fails only at request time,
        so the malformed form is rejected here, at load time.

        Args:
            value: The declared API path prefix; an empty value keeps the bare address.

        Returns:
            The validated API path prefix.

        Raises:
            ValueError: The prefix does not start with ``/``.
        """
        if value and not value.startswith("/"):
            raise ValueError("the instance base_path must start with '/' — it is appended to http://<host>:<port>")

        return value
