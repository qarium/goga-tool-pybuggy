"""Tests for the `goga_tool_pybuggy.web.pages` module (the page-object base of the web kind)."""

import inspect

import pytest
from goga_tool_pybuggy.web import BasePage
from goga_tool_pybuggy.web.pages import BasePage as LocatedBasePage
from prettyplay.failures import PrettyplayError


class _FakeGroup:
    """The group double the FakeWeb.group hands out."""


class FakeWeb:
    """The web runtime double — the ``site_base_url`` source and the step recorder."""

    def __init__(self, site_base_url: str = "") -> None:
        self.site_base_url = site_base_url
        self.steps: list[tuple] = []
        self.expects: list[tuple] = []
        self.groups: list[tuple] = []

    def step(self, text: str, *, tries=None, delay=None, vars=None) -> None:
        self.steps.append((text, tries, delay, vars))

    def expect(self, text: str, *, tries=None, delay=None, vars=None) -> None:
        self.expects.append((text, tries, delay, vars))

    def group(self, prompt: str, *, speed=None, delay=None) -> _FakeGroup:
        self.groups.append((prompt, speed, delay))

        return _FakeGroup()


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
        """`url` is a property; the step proxies, the call and the context manager are callable."""
        assert isinstance(BasePage.url, property)

        for name in ("step", "expect", "group", "__call__", "__enter__", "__exit__"):
            assert callable(getattr(BasePage, name)), name

    def test_goto_is_absent_from_the_public_surface(self):
        """The named navigation method is gone — the activation call owns the navigation."""
        assert not hasattr(BasePage, "goto")

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


class TestBasePageCall:
    """Logic tests: the activation call — the characteristic action on call."""

    def test_call_issues_one_step_sentence_with_the_full_url_and_returns_self(self):
        web = FakeWeb("https://example.com")
        page = BasePage(web, "/login")

        assert page() is page
        assert web.steps == [("Open https://example.com/login", None, None, None)]

    def test_call_of_a_subclass_uses_the_class_path(self):
        web = FakeWeb("https://example.com")

        class LoginPage(BasePage):
            path = "/login"

        LoginPage(web)()

        assert web.steps == [("Open https://example.com/login", None, None, None)]

    def test_call_without_a_base_url_fails_before_any_step(self):
        web = FakeWeb()

        with pytest.raises(PrettyplayError):
            BasePage(web, "/login")()

        assert web.steps == []

    def test_repeated_call_navigates_again(self):
        """Leaving and returning: the second call is an ordinary re-navigation step."""
        web = FakeWeb("https://example.com")
        page = BasePage(web, "/login")

        page()
        page()

        assert len(web.steps) == 2


class TestBasePageContextManager:
    """Logic tests: the with-block — a short local name over the opened page."""

    def test_with_call_binds_the_same_opened_page(self):
        web = FakeWeb("https://example.com")
        page = BasePage(web, "/login")

        with page() as bound:
            assert bound is page

        assert web.steps == [("Open https://example.com/login", None, None, None)]

    def test_exit_never_suppresses_exceptions(self):
        page = BasePage(FakeWeb("https://example.com"), "/login")

        with pytest.raises(AssertionError, match="boom"), page():
            raise AssertionError("boom")

    def test_exit_returns_none(self):
        """A falsy exit return keeps the block exception propagating."""
        page = BasePage(FakeWeb("https://example.com"))

        with page():
            pass

        assert page.__exit__(AssertionError, AssertionError("x"), None) is None


class TestBasePageStepProxies:
    """Logic tests: the step surface proxied onto the page."""

    def test_step_delegates_with_the_keyword_arguments(self):
        web = FakeWeb("https://example.com")
        page = BasePage(web)

        page.step("Заполнить поле «INN»", tries=3, delay=0.5, vars={"id": "42"})

        assert web.steps == [("Заполнить поле «INN»", 3, 0.5, {"id": "42"})]

    def test_expect_delegates_with_the_keyword_arguments(self):
        web = FakeWeb("https://example.com")
        page = BasePage(web)

        page.expect("Поле содержит значение", tries=2)

        assert web.expects == [("Поле содержит значение", 2, None, None)]

    def test_group_delegates_and_returns_the_group(self):
        web = FakeWeb("https://example.com")
        page = BasePage(web)

        group = page.group("Dismiss the cookie banner", speed=50)

        assert isinstance(group, _FakeGroup)
        assert web.groups == [("Dismiss the cookie banner", 50, None)]

    def test_proxies_are_used_by_subclass_methods(self):
        """The page's own scenarios drive the runtime through the same proxied surface."""

        class LoginPage(BasePage):
            path = "/login"

            def dismiss_cookie_banner(self) -> None:
                self.step("Close the cookie banner")
                self.expect("The cookie banner is gone")

        web = FakeWeb("https://example.com")
        LoginPage(web).dismiss_cookie_banner()

        assert web.steps == [("Close the cookie banner", None, None, None)]
        assert web.expects == [("The cookie banner is gone", None, None, None)]
