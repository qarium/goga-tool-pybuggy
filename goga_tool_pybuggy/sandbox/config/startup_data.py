"""StartupData entity: the startup data layer declarations of the sandbox document."""

from pydantic import BaseModel, ConfigDict


class StartupData(BaseModel):
    """Startup data layer declarations, in the fixed section order.

    The field order — vault secrets, http mappings, then postgres init — is the section
    application order at sandbox start. Within a section the declaration order is the
    application order. There is no kafka section — the kafka topology is declared inline on the
    service entry.

    Attributes:
        vault: Service name → secret declarations (path, data).
        http: Service name → stub mapping declarations (request, response).
        postgres: Service name → init SQL statements.
    """

    model_config = ConfigDict(kw_only=True)

    vault: dict[str, list[dict[str, object]]] = {}
    http: dict[str, list[dict[str, object]]] = {}
    postgres: dict[str, list[str]] = {}
