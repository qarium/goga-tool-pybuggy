"""StartupData entity: the startup data layer declarations of the sandbox document."""

from pydantic import BaseModel, ConfigDict


class StartupData(BaseModel):
    """Startup data layer declarations, in the fixed section order.

    The field order — vault secrets, http mappings, postgres init, then redis data — is the
    section application order at sandbox start. Within a section the declaration order is the
    application order. There is no kafka section — the kafka topology is declared inline on the
    service entry.

    Attributes:
        vault: Service name → secret declarations (path, data).
        http: Service name → stub mapping declarations (request, response).
        postgres: Service name → init SQL statements.
        redis: Service name → data declarations; each carries the action key (set, hset, rpush,
            or sadd) plus the fields of the matching view operation (key with
            value/values/members).
    """

    model_config = ConfigDict(kw_only=True)

    vault: dict[str, list[dict[str, object]]] = {}
    http: dict[str, list[dict[str, object]]] = {}
    postgres: dict[str, list[str]] = {}
    redis: dict[str, list[dict[str, object]]] = {}
