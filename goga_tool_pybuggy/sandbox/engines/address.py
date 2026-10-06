"""InstanceAddress entity: the mapped address of a started instance."""

from pydantic import BaseModel, ConfigDict


class InstanceAddress(BaseModel):
    """The mapped address of a started instance.

    Addresses are always read back from the container engine — never a fixed host port — so
    ``port`` carries the published host-side port of the running container.

    Attributes:
        host: Mapped host the instance is reachable on.
        port: Published host-side port the instance is reachable on.
    """

    model_config = ConfigDict(kw_only=True)

    host: str
    port: int
