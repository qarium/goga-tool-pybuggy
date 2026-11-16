"""Tests for the `goga_tool_pybuggy.web.pages` module (the page-object base of the web kind)."""

import inspect

import pytest
from goga_tool_pybuggy.web import BasePage
from goga_tool_pybuggy.web.pages import BasePage as LocatedBasePage
from prettyplay.failures import PrettyplayError


class FakeWeb:
    """The web runtime double — the ``site_base_url`` source and the step recorder."""

    def __init__(self, site_base_url: str = "") -> None:
        self.site_base_url = site_base_url
        self.steps: list[str] = []

    def step(self, text: str, **kwargs: object) -> None:
        self.steps.append(text)


class TestBasePageContract:
    """Contract tests: location, facade, constructor shape, surface."""

    def test_base_page_lives_on_the_pages_module(self):
        """`BasePage` is defined on `web.pages` and re-exported by the facade."""
        import goga_tool_pybuggy.web as web_module

        assert LocatedBasePage is BasePage
        assert web_module.BasePage is BasePage
        assert "BasePage" in web_module.__all__

    def test_constructor_signature_matches_contract(self):
        """`web` stays positional; `path` is optional with the empty default."""
        parameters = list(inspect.signature(BasePage.__init__).parameters.values())[1:]

        assert [parameter.name for parameter in parameters] == ["web", "path"]
        assert parameters[0].kind is inspect.Parameter.POSITIONAL_OR_KEYWORD
        assert parameters[1].default == ""

    def test_surface_matches_contract(self):
        """`url` is a property; `goto` and the runtime attribute are callable/plain."""
        assert isinstance(BasePage.url, property)
        assert callable(BasePage.goto)

    def test_class_path_attribute_defaults_empty(self):
        """The declared default path is the empty string — the site root page."""
        assert BasePage.path == ""


class TestBasePageUrl:
    """Logic tests: the URL join of the site base URL and the page path."""

    @pytest.mark.parametrize(
        ("base", "path", "expected"),
        [
            ("https://example.com", "/login", "https://example.com/login"),
            ("https://example.com/", "/login", "https://example.com/login"),
            ("https://example.com", "login", "https://example.com/login"),
            ("https://staging.example.com/app", "/dashboard", "https://staging.example.com/app/dashboard"),
            ("https://staging.example.com/app/", "dashboard", "https://staging.example.com/app/dashboard"),
            ("http://localhost:3000", "/users/42/orders", "http://localhost:3000/users/42/orders"),
        ],
    )
    def test_url_joins_base_and_path(self, base, path, expected):
        """Slash normalization: no doubled separators whatever the written forms."""
        assert BasePage(FakeWeb(base), path).url == expected

    @pytest.mark.parametrize(
        ("base", "expected"),
        [
            ("https://example.com", "https://example.com"),
            ("https://example.com/", "https://example.com"),
        ],
    )
    def test_empty_path_yields_the_bare_base_url(self, base, expected):
        """No path — the site root without a dangling trailing slash."""
        assert BasePage(FakeWeb(base)).url == expected

    def test_unset_base_url_fails_loudly_naming_the_directive(self):
        """A missing `site.base_url` is the loud actionable failure naming web.yml."""
        with pytest.raises(PrettyplayError) as excinfo:
            _ = BasePage(FakeWeb()).url

        assert "site.base_url" in str(excinfo.value)
        assert "web.yml" in str(excinfo.value)


class TestBasePageSubclassing:
    """Logic tests: the subclass pattern — the class attribute path."""

    def test_subclass_path_attribute_is_used_without_a_constructor_path(self):
        class LoginPage(BasePage):
            path = "/login"

        assert LoginPage(FakeWeb("https://example.com")).url == "https://example.com/login"

    def test_constructor_path_overrides_the_subclass_attribute(self):
        class LoginPage(BasePage):
            path = "/login"

        page = LoginPage(FakeWeb("https://example.com"), "/logout")

        assert page.url == "https://example.com/logout"
        assert page.path == "/logout"

    def test_subclass_inherits_the_runtime_attribute(self):
        web = FakeWeb("https://example.com")

        page = BasePage(web)

        assert page.web is web


class TestBasePageGoto:
    """Logic tests: the navigation step."""

    def test_goto_issues_one_step_sentence_with_the_full_url(self):
        web = FakeWeb("https://example.com")

        BasePage(web, "/login").goto()

        assert web.steps == ["Open https://example.com/login"]

    def test_goto_of_a_subclass_uses_the_class_path(self):
        web = FakeWeb("https://example.com")

        class LoginPage(BasePage):
            path = "/login"

        LoginPage(web).goto()

        assert web.steps == ["Open https://example.com/login"]

    def test_goto_without_a_base_url_fails_before_any_step(self):
        web = FakeWeb()

        with pytest.raises(PrettyplayError):
            BasePage(web, "/login").goto()

        assert web.steps == []
