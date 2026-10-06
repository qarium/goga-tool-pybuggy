"""services entity: the per-test data-preset decorator."""

from collections.abc import Callable
from typing import Any

import pytest

_SUPPORTED_KINDS = ("postgresql", "kafka", "vault", "http")


def services(**presets: dict[str, list[dict[str, object]]]) -> Callable[..., Any]:
    """Mark one test with per-test sandbox data presets.

    Each keyword names a supported instance kind and carries that kind's instance-targeted
    declarations: ``kind -> instance name -> declaration list``. The declarations pass through
    as given — declaration order within one instance is the application order. Presets apply
    only to the test declaring them: the marked presets are enqueued into the per-test batch at
    setup time, ahead of any in-test view declaration, and applied right before the first call
    to the service under test.

    Nothing executes at decoration time — the routine only validates the kind keys and
    attaches the marker. Instance names are validated later, at enqueue time, against the
    sandbox configuration.

    Args:
        **presets: The per-kind declarations. Every key must be one of the supported kinds
            (postgresql, kafka, vault, http); each value maps instance names to the
            declaration lists the kind's view methods would declare.

    Returns:
        The decorator applying the ``pybuggy_services`` marker with the presets to a test.

    Raises:
        ValueError: When a preset key is not a supported kind.
    """
    for kind in presets:
        if kind not in _SUPPORTED_KINDS:
            raise ValueError(
                f"services preset kind '{kind}' is not one of the supported kinds ({', '.join(_SUPPORTED_KINDS)})"
            )

    def _decorate(item: Any) -> Any:
        return pytest.mark.pybuggy_services(presets=presets)(item)

    return _decorate
