"""InstanceConfig entity: one named dependency instance declaration of ``.sandbox.yml``."""

from pydantic import BaseModel, ConfigDict


class InstanceConfig(BaseModel):
    """One named dependency instance declaration.

    The accepted kinds (postgresql, kafka, vault, http) are validated by the loader — the model
    carries the field types only.

    Attributes:
        name: Instance name — the addressable key and the placeholder name.
        kind: Dependency kind: postgresql, kafka, vault, or http.
        image: Image override; ``None`` keeps the product-pinned default of the kind.
    """

    model_config = ConfigDict(kw_only=True)

    name: str
    kind: str
    image: str | None = None
