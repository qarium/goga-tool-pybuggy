"""Shared base for `goga_tool_pybuggy.api` asserts (matchcrest-backed).

``BaseAssert`` builds matchcrest matchers, injecting the polling options (``timeout``/``delay``).
"""

from __future__ import annotations

from importlib import import_module
from typing import Any

from ...matchcrest import BaseMatcher


def load_assert_class(import_path: str, base_class: type) -> type:
    """Import an assert class by dotted ``module:Class`` path.

    Args:
        import_path: ``"module.path:ClassName"`` dotted specifier.
        base_class: required base class; the loaded class must subclass it.

    Returns:
        The loaded class.

    Raises:
        ValueError: when ``import_path`` has no ``:`` separator.
        ImportError: when the module or the named class cannot be resolved.
        TypeError: when the loaded class is not a subclass of ``base_class``.
    """
    if ":" not in import_path:
        raise ValueError(f'Invalid import path "{import_path}"')

    module_path, class_name = import_path.split(":", 1)

    try:
        module = import_module(module_path)
    except ModuleNotFoundError as exc:
        raise ImportError(f'Module "{module_path}" not found') from exc

    cls = getattr(module, class_name, None)

    if cls is None:
        raise ImportError(f'Class "{class_name}" not found in module "{module_path}"')

    if base_class not in cls.__mro__:
        raise TypeError(f'"{class_name}" is not a subclass of "{base_class.__name__}"')

    return cls


class BaseAssert:
    """Helper building matchcrest matchers with polling options.

    Subclasses set ``self._timeout``/``self._delay`` as the baseline; per-check kwargs override it.
    """

    _timeout: int | float | None = None
    _delay: int | float | None = None

    def _create_matcher(
        self,
        matcher: type[BaseMatcher],
        expected_value: Any,
        **kwargs: Any,
    ) -> BaseMatcher:
        """Build a matcher, applying the polling baseline.

        Args:
            matcher: a matchcrest matcher class.
            expected_value: the value the matcher asserts against.
            **kwargs: matcher options; ``timeout``/``delay`` override the baseline, ``None`` values are dropped.

        Returns:
            The constructed matcher instance.
        """
        timeout = kwargs.get("timeout")
        if timeout is None:
            timeout = self._timeout
        delay = kwargs.get("delay")
        if delay is None:
            delay = self._delay

        kwargs = {key: value for key, value in kwargs.items() if value is not None}
        if timeout is not None:
            kwargs["timeout"] = timeout
        if delay is not None:
            kwargs["delay"] = delay

        return matcher(expected_value, **kwargs)
