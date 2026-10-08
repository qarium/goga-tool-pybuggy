"""InstanceConfig entity: the instance-under-test entry of the sandbox document."""

from pydantic import BaseModel, ConfigDict

from .probe import ProbeConfig


class InstanceConfig(BaseModel):
    """Instance-under-test entry of the sandbox configuration.

    Attributes:
        image: Container image of the instance under test.
        env: Environment values; values may carry service address placeholders resolved at
            sandbox start.
        port: Container port the service serves on.
        probe: Readiness declaration — the health path and the wait bounds; ``None`` keeps the
            default wait: port readiness with the default deadline and interval.
    """

    model_config = ConfigDict(kw_only=True, extra="forbid")

    image: str
    env: dict[str, str] = {}
    port: int
    probe: ProbeConfig | None = None
