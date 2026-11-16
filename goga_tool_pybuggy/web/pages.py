"""The page-object base of the web test kind — a tested-site page bound to the web runtime.

``BasePage`` binds a ``PrettyPlay`` runtime and a page path the way the api kind's ``Endpoint``
binds an ``Api`` and a route path: the base URL lives on the runtime (the ``site.base_url``
directive of ``web.yml``), the page adds its own path, and ``goto`` navigates through one
ordinary step sentence — the navigation participates in the step cycle (cache, generation,
healing) like every authored step.
"""

from __future__ import annotations

from prettyplay import PrettyPlay
from prettyplay.failures import PrettyplayError


class BasePage:
    """One tested-site page: the runtime plus a path, ``goto`` opens the full URL.

    Args:
        web: the web runtime of the current test — the ``site.base_url`` source and the
            step executor of the navigation.
        path: the page path resolved against the site base URL; empty falls back to the
            ``path`` class attribute of the subclass (``""`` — the site root).

    Raises:
        PrettyplayError: ``goto`` or ``url`` runs while the site base URL is unset — the
            ``site.base_url`` directive of ``web.yml`` is missing or empty.
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

    def goto(self) -> None:
        """Open this page — one action step sentence carrying the full URL.

        The navigation is an ordinary step: the first run generates and caches it, the
        replay executes the cached code, a failure heals — exactly like every authored
        step sentence of the test.
        """
        self.web.step(f"Open {self.url}")
