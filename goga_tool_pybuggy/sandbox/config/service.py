"""ServiceConfig entity: the service-under-test entry of ``.sandbox.yml``."""

from pydantic import BaseModel, ConfigDict


class ServiceConfig(BaseModel):
    """Service-under-test entry of the sandbox configuration.

    Attributes:
        image: Container image of the service under test.
        env: Environment values; values may carry instance address placeholders resolved at
            sandbox start.
        port: Container port the service serves on.
        health: Health path for readiness; ``None`` means port readiness only.
    """

    model_config = ConfigDict(kw_only=True)

    image: str
    env: dict[str, str] = {}
    port: int
    health: str | None = None
