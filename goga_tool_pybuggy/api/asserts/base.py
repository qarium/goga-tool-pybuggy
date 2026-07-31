"""Shared base for `pybuggy.api` asserts (matchcrest-backed).

``BaseAssert`` is the minimal helper shared by the assert entities: it builds a
matchcrest matcher from its class and the expected value, injecting the polling
options (``timeout``/``delay``) into the matcher. The baseline values come from
``AssertConfig`` (stored as ``self._timeout``/``self._delay`` by subclasses); a
per-check ``timeout``/``delay`` kwarg overrides them for one assertion. pybuggy
ships plain classes (no reporting layer).
"""

from __future__ import annotations

from importlib import import_module
from typing import Any

from ...matchcrest import BaseMatcher


def load_assert_class(import_path: str, base_class: type) -> type:
    """Import an assert class by dotted ``module:Class`` path.

    Args:
        import_path: ``"module.path:ClassName"`` — the module is imported with
            ``importlib`` and the class read off it.
        base_class: the required base — the loaded class must be a subclass.

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

    Subclasses set ``self._timeout``/``self._delay`` (the config baseline) and
    call ``_create_matcher`` to instantiate a matcher. A per-check
    ``timeout``/``delay`` kwarg overrides the baseline for that one matcher;
    ``None`` values are dropped so the matcher defaults apply. The remaining
    kwargs (``any``/``in_array``/``strict``/``or_equal``/``count``/…) are
    forwarded verbatim.
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

        ``timeout``/``delay`` in ``kwargs`` (per-check overrides) win; when
        absent, ``self._timeout``/``self._delay`` (the config baseline) apply.
        All ``None`` kwargs are filtered out so matchcrest's own defaults take
        over.

        Args:
            matcher: a matchcrest matcher class.
            expected_value: the value the matcher asserts against.
            **kwargs: matcher options; ``timeout``/``delay`` override the
                baseline, the rest are forwarded; ``None`` values are dropped.

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
