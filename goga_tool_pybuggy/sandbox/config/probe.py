"""ProbeConfig entity: the readiness declaration of the sandbox configuration."""

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class ProbeConfig(BaseModel):
    """Readiness declaration — wait bounds and the optional health-check path.

    The defaults reproduce the established wait exactly: timeout 30.0, interval 0.5. The path is
    accepted only on the instance-under-test entry; service entries declare bounds only.

    Attributes:
        timeout: Readiness deadline in seconds; an expired deadline fails with an actionable
            error.
        interval: Seconds between readiness attempts.
        path: Health-check path; ``None`` keeps port readiness.
    """

    model_config = ConfigDict(kw_only=True, extra="forbid")

    timeout: float = Field(default=30.0, gt=0)
    interval: float = Field(default=0.5, gt=0)
    path: str | None = None

    @model_validator(mode="after")
    def _interval_within_timeout(self) -> "ProbeConfig":
        """Enforce that the interval never exceeds the timeout.

        The message names the default interval so a sub-second-timeout error stays actionable.

        Returns:
            The validated model instance.
        """
        if self.interval > self.timeout:
            raise ValueError(
                "the probe interval (default 0.5) must not exceed the timeout — "
                "declare a smaller interval alongside a sub-second timeout"
            )

        return self

    @field_validator("path")
    @classmethod
    def _path_starts_with_a_slash(cls, value: str | None) -> str | None:
        """Require the leading slash of the health path.

        The readiness wait concatenates the path onto ``http://<host>:<port>`` — a path
        without the slash misforms every health URL and fails only at the readiness
        deadline, so the malformed form is rejected here, at load time.

        Args:
            value: The declared health path; ``None`` keeps port readiness.

        Returns:
            The validated health path.

        Raises:
            ValueError: The path does not start with ``/``.
        """
        if value is not None and not value.startswith("/"):
            raise ValueError("the probe path must start with '/' — it is appended to http://<host>:<port>")

        return value
