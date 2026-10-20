"""DataOperation entity: the uniform operation unit of the sandbox data plane."""

from pydantic import BaseModel, ConfigDict


class DataOperation(BaseModel):
    """The uniform operation unit.

    One operation covers every data-plane interaction: startup data, presets, in-test
    declarations and journal entries. The fixed action set is ``insert`` / ``produce`` / ``put``
    / ``stub`` / ``set`` / ``hset`` / ``rpush`` / ``sadd``; the payload carries plain
    serializable data — for postgresql startup inserts a raw ``sql`` key instead of ``table``
    + ``rows``, executed as given, opaque. A redis operation's payload carries the key plus
    ``value``, ``values``, or ``members`` — the fields of the matching view operation.

    Attributes:
        instance: Name of the target service (a configured service key).
        kind: Dependency kind of the target service: postgresql, kafka, vault, http, or redis.
        action: Data-plane action: insert, produce, put, stub, set, hset, rpush, or sadd.
        payload: Plain serializable operation data; the shape follows the kind and action.
    """

    model_config = ConfigDict(kw_only=True)

    instance: str
    kind: str
    action: str
    payload: dict[str, object] = {}
