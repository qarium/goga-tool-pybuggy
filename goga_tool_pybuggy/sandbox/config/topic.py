"""TopicConfig entity: one inline kafka topic declaration of the sandbox configuration."""

from pydantic import BaseModel, ConfigDict, Field


class TopicConfig(BaseModel):
    """One kafka topic declared inline on a kafka service entry.

    Attributes:
        name: Topic name the mock opens and tests produce into.
        partitions: Topic partition count; 1 when omitted.
    """

    model_config = ConfigDict(kw_only=True)

    name: str = Field(min_length=1)
    partitions: int = Field(default=1, gt=0)
