"""SandboxConfig entity: the root model of the ``.sandbox.yml`` document."""

from pydantic import BaseModel, ConfigDict

from .instance import InstanceConfig
from .service import ServiceConfig
from .startup_data import StartupData


class SandboxConfig(BaseModel):
    """Root model of the sandbox configuration.

    Attributes:
        service: The service-under-test entry.
        instances: Dependency instance entries keyed by instance name; several instances of one
            kind are allowed.
        data: The startup data layer declarations.
    """

    model_config = ConfigDict(kw_only=True)

    service: ServiceConfig
    instances: dict[str, InstanceConfig] = {}
    data: StartupData = StartupData()
