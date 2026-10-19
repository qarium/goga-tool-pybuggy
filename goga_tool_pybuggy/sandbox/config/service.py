"""ServiceConfig entity: one named dependency service declaration of the sandbox document."""

from pydantic import BaseModel, ConfigDict, model_validator

from .migrations import MigrationsConfig
from .probe import ProbeConfig
from .topic import TopicConfig


class ServiceConfig(BaseModel):
    """One named dependency service declaration.

    The accepted kinds (postgresql, kafka, vault, http, redis) are validated by the loader —
    the model carries the field types only.

    Attributes:
        name: Service name — the addressable key and the placeholder name.
        kind: Dependency kind: postgresql, kafka, vault, http, or redis.
        image: Image override; ``None`` keeps the product-pinned default of the kind.
        topics: Kafka topic declarations; required and non-empty for the kafka kind, empty for
            every other kind.
        probe: Readiness declaration — the wait bounds for this service's readiness check; the
            path is accepted only on the instance-under-test entry.
        migrations: Migrations declaration — accepted on the postgresql kind only; a declaration
            on any other kind fails at document load with the entry named; ``None`` — no
            migrations.
        password: The redis auth password — optional, accepted on the redis kind only; absent
            starts the service without authentication; present starts it with ``--requirepass``.
        db: The redis logical database index — optional, accepted on the redis kind only; 0 by
            default; the valid range is 0-15.
    """

    model_config = ConfigDict(kw_only=True, extra="forbid")

    name: str
    kind: str
    image: str | None = None
    topics: list[TopicConfig] = []
    probe: ProbeConfig | None = None
    migrations: MigrationsConfig | None = None
    password: str | None = None
    db: int = 0

    @model_validator(mode="after")
    def _probe_carries_no_path(self) -> "ServiceConfig":
        """Reject a probe path — the path belongs to the instance-under-test entry only.

        Returns:
            The validated model instance.

        Raises:
            ValueError: The probe declares a health-check path.
        """
        if self.probe is not None and self.probe.path is not None:
            raise ValueError("the probe path is accepted only on the instance entry")

        return self
