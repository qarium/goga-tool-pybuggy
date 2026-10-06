"""StartupData entity: the startup data layer declarations of ``.sandbox.yml``."""

from pydantic import BaseModel, ConfigDict


class StartupData(BaseModel):
    """Startup data layer declarations, in the fixed section order.

    The field order — vault secrets, http mappings, the kafka spec, then postgres init — is the
    section application order at sandbox start. Within a section the declaration order is the
    application order.

    Attributes:
        vault: Instance name → secret declarations (path, data).
        http: Instance name → stub mapping declarations (request, response).
        kafka: Instance name → AsyncAPI spec file path.
        postgres: Instance name → init SQL statements.
    """

    model_config = ConfigDict(kw_only=True)

    vault: dict[str, list[dict[str, object]]] = {}
    http: dict[str, list[dict[str, object]]] = {}
    kafka: dict[str, str] = {}
    postgres: dict[str, list[str]] = {}
