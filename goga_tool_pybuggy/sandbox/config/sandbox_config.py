"""SandboxConfig entity: the root model of the sandbox document."""

from pydantic import BaseModel, ConfigDict

from .instance import InstanceConfig
from .service import ServiceConfig
from .startup_data import StartupData


class SandboxConfig(BaseModel):
    """Root model of the sandbox configuration.

    Attributes:
        instance: The instance-under-test entry.
        services: Dependency service entries keyed by service name; several services of one
            kind are allowed.
        data: The startup data layer declarations.
    """

    model_config = ConfigDict(kw_only=True)

    instance: InstanceConfig
    services: dict[str, ServiceConfig] = {}
    data: StartupData = StartupData()
