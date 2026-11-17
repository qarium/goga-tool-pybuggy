"""The page-object base of the web test kind — a tested-site page bound to the web runtime.

``BasePage`` binds a ``PrettyPlay`` runtime and a page path the way the api kind's ``Endpoint``
binds an ``Api`` and a route path: the base URL lives on the runtime (the ``site.base_url``
directive of ``web.yml``), the page adds its own path, and the page performs its characteristic
action — opening the full URL through one ordinary step sentence — **on call**. The step
surface (``step`` / ``expect`` / ``group``) is proxied onto the page, so tests and page methods
alike drive the runtime without the ``.web`` hop; the runtime itself stays public for everything
else (``run_on_page``, ``site_base_url``).
"""

from __future__ import annotations

from prettyplay import PrettyPlay, StepGroup
from prettyplay.failures import PrettyplayError


class BasePage:
    """One tested-site page: the runtime plus a path; the call opens it.

    Args:
        web: the web runtime of the current test — the ``site.base_url`` source and the step
            executor of the navigation; held as the public ``web`` attribute the way Endpoint
            holds its api.
        path: the page path resolved against the site base URL; empty falls back to the
            ``path`` class attribute of the subclass (``""`` — the site root).

    Raises:
        PrettyplayError: ``url`` or the activation call runs while the site base URL is unset —
            the ``site.base_url`` directive of ``web.yml`` is missing or empty.
    """

    path: str = ""

    def __init__(self, web: PrettyPlay, path: str = "") -> None:
        self.web = web
        self.path = path or type(self).path

    @property
    def url(self) -> str:
        """The full page URL — the site base URL with this page's path.

        Returns:
            ``<site.base_url>/<path>`` with the joining slashes normalized — a trailing
            slash of the base and a leading slash of the path never duplicate; an empty
            path yields the bare base URL.

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
            return base.rstrip("/")

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

        Args:
            text: The step sentence — the template source, exactly as ``web.step`` takes it.
            tries: Keyword-only retry count; ``None`` — the settle mode (see ``web.step``).
            delay: Keyword-only quiet pre-step pause in seconds.
            vars: Keyword-only call-local string inputs of the step.
        """
        self.web.step(text, tries=tries, delay=delay, vars=vars)

    def expect(
        self,
        text: str,
        *,
        tries: int | None = None,
        delay: float | None = None,
        vars: dict[str, str] | None = None,
    ) -> None:
        """Execute one assertion step sentence through the bound runtime.

        Args:
            text: The expectation sentence — the template source, exactly as ``web.expect``
                takes it.
            tries: Keyword-only retry count; ``None`` — the settle mode.
            delay: Keyword-only quiet pre-step pause in seconds.
            vars: Keyword-only call-local string inputs of the expectation.
        """
        self.web.expect(text, tries=tries, delay=delay, vars=vars)

    def group(self, prompt: str, *, speed: int | None = None, delay: float | None = None) -> StepGroup:
        """Open the group authoring block through the bound runtime.

        Args:
            prompt: The group prompt — the shared goal of the mini-scenario.
            speed: Keyword-only group pace, an integer 0-100.
            delay: Keyword-only quiet pause before the group's first step, seconds.

        Returns:
            The authoring group object — the same ``web.group`` yields.
        """
        return self.web.group(prompt, speed=speed, delay=delay)

    def __call__(self) -> BasePage:
        """Open this page — one action step sentence carrying the full URL — and return self.

        The page performs its characteristic action on call, the pattern of the api kind's
        ``Endpoint``: ``page_login()`` opens the page, ``with page_login() as page:`` scopes
        the work on it under a short local name. The navigation is an ordinary step of the
        cycle: the first run generates and caches it, the replay executes the cached code, a
        failure heals. Never override — scenario logic lives in named methods.

        Returns:
            This page — opened, ready for the block.
        """
        self.web.step(f"Open {self.url}")

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
