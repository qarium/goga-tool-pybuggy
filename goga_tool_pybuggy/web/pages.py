"""The page-object base of the web test kind — a tested-site page bound to the web runtime.

``BasePage`` binds a ``PrettyPlay`` runtime and a page path the way the api kind's ``Endpoint``
binds an ``Api`` and a route path: the base URL lives on the runtime (the ``site.base_url``
directive of ``web.yml``), the page adds its own path, and the page performs its characteristic
action — opening the full URL through one ordinary step sentence — **on call**. The step
surface (``step`` / ``expect`` / ``group``) is proxied onto the page, so tests and page methods
alike drive the runtime without the ``.web`` hop; the runtime itself stays public for everything
else (``run_on_page``, ``site_base_url``).

The proxy is also the boundary of the page's shared step vocabulary: a step sentence executed
from a named method of the page class (the activation call included) carries the page method's
cache scope — the page module's path with the method's own name as its last segment — so one
sentence of one page **method** is one shared cache entry for every test using that method;
the same sentence of another method of the same page is another entry — two methods pressing
a same-named button press it in their own contexts, the generated code of one never stands in
for the other. A step called inline from a test stays the test's own per-test entry. The
discrimination is automatic — the caller frame of the proxy is a bound method of this very page
or it is not — no path is ever passed by hand (see ``_scope_if_page_call``).
"""

from __future__ import annotations

import sys
from functools import cache
from inspect import getsourcefile

from prettyplay import PrettyPlay, StepGroup
from prettyplay.failures import PrettyplayError

#: The upper bound of the caller-frame walk of ``_scope_if_page_call`` — deep helper nesting
#: inside a page module is page vocabulary, a runaway walk is a bug; eight frames cover both.
_CALLER_WALK_LIMIT = 8


@cache
def _page_scope(page_class: type[BasePage]) -> str:
    """Derive the base cache scope of a page class — its module's path under a ``cache`` segment.

    Args:
        page_class: the concrete page class of the instance in hand.

    Returns:
        The module path with the dots of the dotted name as separators and a
        ``.cache`` segment above the module's own name — ``pages.admin.auth_page``
        becomes ``pages/admin/.cache/auth_page``, the subdirectory of the cache
        root holding the page's method directories of shared steps; the ``.cache``
        parent keeps the generated directories of one module directory under one
        roof. The method's own name lands as one more segment on top of this base
        (see ``_scope_if_page_call``).
    """
    segments = page_class.__module__.split(".")
    segments.insert(-1, ".cache")

    return "/".join(segments)


@cache
def _page_files(page_class: type[BasePage]) -> frozenset[str]:
    """Collect the source files whose frames count as this page's own.

    Args:
        page_class: the concrete page class of the instance in hand.

    Returns:
        The page class's source file together with this module's file — the
        two places a frame may sit in while still acting for the page (its
        methods and the base's own ``__call__``); an unresolvable source file
        (a synthetic class without one) drops out, leaving the base module's
        file alone.
    """
    try:
        own = getsourcefile(page_class)
    except TypeError:  # a synthetic class whose module carries no file — the base module's file alone
        own = None

    return frozenset({own, __file__} - {None})


def _scope_if_page_call(page: BasePage) -> str | None:
    """Decide whether this proxy call comes from the page's own code, and from which method.

    Called directly from ``step`` / ``expect`` / ``group`` — two frames up is
    the proxy's caller. The walk stays inside the page's own source files and
    declares the call page-scoped exactly when a frame of this very instance
    (a bound method's ``self``, ``__call__`` included) initiated it; a test
    function, a test-class method (its ``self`` is the test object, never the
    page) and foreign helpers stop the walk at their first frame. The scope of
    a page call is the page's base scope plus the owning method's own name as
    the last segment — the step binds to the method, not to the page whole, so
    the same sentence of two methods is two cache entries, never one shared
    across their different contexts (a method's name is a plain identifier, a
    valid scope segment by construction).

    Args:
        page: the page instance whose proxy is executing.

    Returns:
        The calling page method's cache scope when the call is the page's own;
        ``None`` — the test's per-test address — otherwise.
    """
    frame = sys._getframe(2)  # this helper sits directly under the proxy; frame two is its caller
    files = _page_files(type(page))

    for _ in range(_CALLER_WALK_LIMIT):
        if frame is None or frame.f_code.co_filename not in files:
            return None

        # a method's ``self`` is its first parameter; a closure inside a method sees ``self``
        # only as a free variable — such a frame is the method's implementation detail, the
        # walk continues to the owning method itself
        if frame.f_code.co_varnames[:1] == ("self",) and frame.f_locals.get("self") is page:
            return f"{_page_scope(type(page))}/{frame.f_code.co_name}"

        frame = frame.f_back  # a closure inside a page method — keep walking to the method itself

    return None


class BasePage:
    """One tested-site page: the runtime plus a path; the call opens it.

    Args:
        web: the web runtime of the current test — the ``site.base_url`` source and the step
            executor of the navigation; held as the public ``web`` attribute the way Endpoint
            holds its api.
        path: the page path resolved against the site base URL; ``""`` — the site root. The
            address arrives at construction (the fixture binds it) — a subclass declares
            behavior, never a path.

    Raises:
        PrettyplayError: ``url`` or the activation call runs while the site base URL is unset —
            the ``site.base_url`` directive of ``web.yml`` is missing or empty.
    """

    def __init__(self, web: PrettyPlay, path: str) -> None:
        self.web = web
        self.path = path

    @property
    def url(self) -> str:
        """The full page URL — the site base URL with this page's path.

        Returns:
            ``<site.base_url>/<path>`` with the joining slashes normalized — a trailing
            slash of the base and a leading slash of the path never duplicate. A path
            without a non-empty segment (``""`` or ``"/"``) yields the site base URL
            **verbatim**: a trailing slash declared in ``site.base_url`` is significant —
            servers may answer 404 to its slashed-off form, so the page never rewrites
            the declared base.

        Raises:
            PrettyplayError: The site base URL is unset — ``web.yml`` carries no
                ``site.base_url``.
        """
        base = self.web.site_base_url

        if not base:
            raise PrettyplayError(
                "the site base URL is unset — set the site.base_url directive of web.yml to build page URLs"
            )

        stripped = self.path.lstrip("/")

        if not stripped:
            return base  # the declared base verbatim — its trailing slash is the site's own answer

        return f"{base.rstrip('/')}/{stripped}"

    def step(
        self,
        text: str,
        *,
        tries: int | None = None,
        delay: float | None = None,
        vars: dict[str, str] | None = None,
    ) -> None:
        """Execute one action step sentence through the bound runtime.

        The sentence carries the calling page method's cache scope when the call comes from
        the page's own code — a method of this class or the activation call; an inline call
        from a test addresses the step under the test's own cache key (see the module
        docstring).

        Args:
            text: The step sentence — the template source, exactly as ``web.step`` takes it.
            tries: Keyword-only retry count; ``None`` — the settle mode (see ``web.step``).
            delay: Keyword-only quiet pre-step pause in seconds.
            vars: Keyword-only call-local string inputs of the step.
        """
        self.web.step(text, tries=tries, delay=delay, vars=vars, _scope=_scope_if_page_call(self))

    def expect(
        self,
        text: str,
        *,
        tries: int | None = None,
        delay: float | None = None,
        vars: dict[str, str] | None = None,
    ) -> None:
        """Execute one assertion step sentence through the bound runtime.

        The scope rule is exactly that of :meth:`step` — the calling method's scope from the
        page's own code, the test's address from a test's inline call.

        Args:
            text: The expectation sentence — the template source, exactly as ``web.expect``
                takes it.
            tries: Keyword-only retry count; ``None`` — the settle mode.
            delay: Keyword-only quiet pre-step pause in seconds.
            vars: Keyword-only call-local string inputs of the expectation.
        """
        self.web.expect(text, tries=tries, delay=delay, vars=vars, _scope=_scope_if_page_call(self))

    def group(self, prompt: str, *, speed: int | None = None, delay: float | None = None) -> StepGroup:
        """Open the group authoring block through the bound runtime.

        The scope rule is exactly that of :meth:`step` — a group opened from the page's own
        code carries the calling method's scope for every step of the block; opened inline
        from a test it addresses under the test's cache key.

        Args:
            prompt: The group prompt — the shared goal of the mini-scenario.
            speed: Keyword-only group pace, an integer 0-100.
            delay: Keyword-only quiet pause before the group's first step, seconds.

        Returns:
            The authoring group object — the same ``web.group`` yields.
        """
        return self.web.group(prompt, speed=speed, delay=delay, _scope=_scope_if_page_call(self))

    def __call__(self) -> BasePage:
        """Open this page — one action step sentence carrying the full URL — and return self.

        The page performs its characteristic action on call, the pattern of the api kind's
        ``Endpoint``: ``page_login()`` opens the page, ``with page_login() as page:`` scopes
        the work on it under a short local name. The navigation is an ordinary step of the
        cycle executed through the page's own proxy — it carries the ``__call__`` method's
        cache scope (the page's base scope with ``__call__`` as the last segment), so the
        opening sentence is one shared entry for every test of this page: the first run
        generates and caches it, the replay executes the cached code, a failure heals. Never
        override — scenario logic lives in named methods.

        Returns:
            This page — opened, ready for the block.
        """
        self.step(f"Open {self.url}")

        return self

    def __enter__(self) -> BasePage:
        """Enter the page block; the activation call has opened the page.

        Returns:
            This page — the short local name of the ``with`` block.
        """
        return self

    def __exit__(self, exc_type: object, exc_value: object, traceback: object) -> None:
        """Leave the page block — scoping only.

        The runtime lifecycle belongs to the ``web`` fixture of the plugins cell: the exit
        closes nothing and never suppresses — a falsy return keeps the exception propagating.
        """
        return None
