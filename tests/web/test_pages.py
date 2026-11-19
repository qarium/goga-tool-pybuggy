"""Tests for the `goga_tool_pybuggy.web.pages` module (the page-object base of the web kind)."""

import inspect

import pytest
from goga_tool_pybuggy.web import BasePage
from goga_tool_pybuggy.web.pages import BasePage as LocatedBasePage
from goga_tool_pybuggy.web.pages import _page_scope
from prettyplay.failures import PrettyplayError


class _FakeGroup:
    """The group double the FakeWeb.group hands out."""


class FakeWeb:
    """The web runtime double — the ``site_base_url`` source and the step recorder.

    Every recorded call carries the passed ``_scope`` as its fifth element — the page's
    cache scope for the page's own calls, ``None`` for a test's inline calls.
    """

    def __init__(self, site_base_url: str = "") -> None:
        self.site_base_url = site_base_url
        self.steps: list[tuple] = []
        self.expects: list[tuple] = []
        self.groups: list[tuple] = []

    def step(self, text: str, *, tries=None, delay=None, vars=None, _scope=None) -> None:
        self.steps.append((text, tries, delay, vars, _scope))

    def expect(self, text: str, *, tries=None, delay=None, vars=None, _scope=None) -> None:
        self.expects.append((text, tries, delay, vars, _scope))

    def group(self, prompt: str, *, speed=None, delay=None, _scope=None) -> _FakeGroup:
        self.groups.append((prompt, speed, delay, _scope))

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
        """`web` and `path` are positional; the path is required — no class fallback."""
        parameters = list(inspect.signature(BasePage.__init__).parameters.values())[1:]

        assert [parameter.name for parameter in parameters] == ["web", "path"]
        assert parameters[0].kind is inspect.Parameter.POSITIONAL_OR_KEYWORD
        assert parameters[1].kind is inspect.Parameter.POSITIONAL_OR_KEYWORD
        assert parameters[1].default is inspect.Parameter.empty

    def test_surface_matches_contract(self):
        """`url` is a property; the step proxies, the call and the context manager are callable."""
        assert isinstance(BasePage.url, property)

        for name in ("step", "expect", "group", "__call__", "__enter__", "__exit__"):
            assert callable(getattr(BasePage, name)), name

    def test_goto_is_absent_from_the_public_surface(self):
        """The named navigation method is gone — the activation call owns the navigation."""
        assert not hasattr(BasePage, "goto")

    def test_path_class_attribute_is_gone(self):
        """No class-level path — the address arrives at construction only."""
        assert "path" not in BasePage.__dict__
        assert not hasattr(BasePage, "path")


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
            ("https://example.com/", "https://example.com/"),
            ("https://cabinet.example.com/app/", "https://cabinet.example.com/app/"),
        ],
    )
    def test_empty_path_yields_the_site_base_url_verbatim(self, base, expected):
        """No path — the declared base verbatim: its trailing slash is significant
        (servers may answer 404 to the slashed-off form, so the page never rewrites it)."""
        assert BasePage(FakeWeb(base), "").url == expected

    @pytest.mark.parametrize("path", ["/", "//"])
    def test_root_slash_path_is_the_verbatim_base_too(self, path):
        """``/`` carries no non-empty segment — the same verbatim-base address as ``""``."""
        assert BasePage(FakeWeb("https://cabinet.example.com/app/"), path).url == "https://cabinet.example.com/app/"

    def test_unset_base_url_fails_loudly_naming_the_directive(self):
        """A missing `site.base_url` is the loud actionable failure naming web.yml."""
        with pytest.raises(PrettyplayError) as excinfo:
            _ = BasePage(FakeWeb(), "").url

        assert "site.base_url" in str(excinfo.value)
        assert "web.yml" in str(excinfo.value)


class TestBasePageSubclassing:
    """Logic tests: the subclass pattern — behavior classes, the address at construction."""

    def test_subclass_constructs_with_its_path(self):
        class LoginPage(BasePage):
            pass

        assert LoginPage(FakeWeb("https://example.com"), "/login").url == "https://example.com/login"

    def test_path_is_required_at_construction(self):
        """No class-attribute fallback: constructing without a path fails loudly."""
        with pytest.raises(TypeError):
            BasePage(FakeWeb("https://example.com"))

    def test_subclass_inherits_the_runtime_attribute(self):
        web = FakeWeb("https://example.com")

        page = BasePage(web, "/login")

        assert page.web is web


class TestBasePageCall:
    """Logic tests: the activation call — the characteristic action on call."""

    def test_call_issues_one_step_sentence_with_the_full_url_and_returns_self(self):
        web = FakeWeb("https://example.com")
        page = BasePage(web, "/login")

        assert page() is page
        assert web.steps == [("Open https://example.com/login", None, None, None, _page_scope(BasePage))]

    def test_call_of_a_subclass_uses_its_constructed_path(self):
        web = FakeWeb("https://example.com")

        class LoginPage(BasePage):
            pass

        LoginPage(web, "/login")()

        assert web.steps == [("Open https://example.com/login", None, None, None, _page_scope(LoginPage))]

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

        assert web.steps == [("Open https://example.com/login", None, None, None, _page_scope(BasePage))]

    def test_exit_never_suppresses_exceptions(self):
        page = BasePage(FakeWeb("https://example.com"), "/login")

        with pytest.raises(AssertionError, match="boom"), page():
            raise AssertionError("boom")

    def test_exit_returns_none(self):
        """A falsy exit return keeps the block exception propagating."""
        page = BasePage(FakeWeb("https://example.com"), "")

        with page():
            pass

        assert page.__exit__(AssertionError, AssertionError("x"), None) is None


class TestBasePageStepProxies:
    """Logic tests: the step surface proxied onto the page."""

    def test_step_delegates_with_the_keyword_arguments(self):
        web = FakeWeb("https://example.com")
        page = BasePage(web, "")

        page.step("Заполнить поле «INN»", tries=3, delay=0.5, vars={"id": "42"})

        assert web.steps == [("Заполнить поле «INN»", 3, 0.5, {"id": "42"}, None)]

    def test_expect_delegates_with_the_keyword_arguments(self):
        web = FakeWeb("https://example.com")
        page = BasePage(web, "")

        page.expect("Поле содержит значение", tries=2)

        assert web.expects == [("Поле содержит значение", 2, None, None, None)]

    def test_group_delegates_and_returns_the_group(self):
        web = FakeWeb("https://example.com")
        page = BasePage(web, "")

        group = page.group("Dismiss the cookie banner", speed=50)

        assert isinstance(group, _FakeGroup)
        assert web.groups == [("Dismiss the cookie banner", 50, None, None)]

    def test_proxies_are_used_by_subclass_methods(self):
        """The page's own scenarios drive the runtime through the same proxied surface."""

        class LoginPage(BasePage):
            def dismiss_cookie_banner(self) -> None:
                self.step("Close the cookie banner")
                self.expect("The cookie banner is gone")

        web = FakeWeb("https://example.com")
        LoginPage(web, "/login").dismiss_cookie_banner()

        assert web.steps == [("Close the cookie banner", None, None, None, _page_scope(LoginPage))]
        assert web.expects == [("The cookie banner is gone", None, None, None, _page_scope(LoginPage))]


class TestBasePageScopeDetection:
    """Logic tests: the automatic page-scope discrimination of the proxy calls."""

    def test_a_method_call_carries_the_page_scope(self):
        """A named method of the page class is the page's shared vocabulary."""

        class LoginPage(BasePage):
            def fill_credentials(self) -> None:
                self.step("Заполнить логин и пароль")

        web = FakeWeb("https://example.com")
        LoginPage(web, "/login").fill_credentials()

        assert web.steps == [("Заполнить логин и пароль", None, None, None, _page_scope(LoginPage))]

    def test_an_inline_call_from_a_test_function_stays_the_tests_own(self):
        web = FakeWeb("https://example.com")
        page = BasePage(web, "/login")

        page.step("Шаг прямо из теста")

        assert web.steps == [("Шаг прямо из теста", None, None, None, None)]

    def test_an_inline_call_from_a_test_class_method_stays_the_tests_own(self):
        """A test-class method's ``self`` is the test object, never the page — no scope."""

        class LoginPage(BasePage):
            pass

        web = FakeWeb("https://example.com")
        page = LoginPage(web, "/login")

        class TestLogin:
            def run(self) -> None:
                page.step("Шаг из метода тест-класса")

        TestLogin().run()

        assert web.steps == [("Шаг из метода тест-класса", None, None, None, None)]

    def test_the_activation_call_carries_the_page_scope(self):
        """``page()`` executes through the page's own proxy — the opening sentence is shared."""
        web = FakeWeb("https://example.com")

        class LoginPage(BasePage):
            pass

        LoginPage(web, "/login")()

        assert web.steps[-1] == ("Open https://example.com/login", None, None, None, _page_scope(LoginPage))

    def test_a_closure_inside_a_page_method_carries_the_page_scope(self):
        """The frame walk climbs nested helpers of the page module to the owning method."""

        class LoginPage(BasePage):
            def dismiss_banner(self) -> None:
                def inner() -> None:
                    self.step("Закрыть баннер")

                inner()

        web = FakeWeb("https://example.com")
        LoginPage(web, "/login").dismiss_banner()

        assert web.steps == [("Закрыть баннер", None, None, None, _page_scope(LoginPage))]

    def test_a_module_level_helper_of_a_foreign_module_stays_the_tests_own(self):
        """A helper outside the page's own files stops the walk — no page scope."""

        def foreign_helper(page: BasePage) -> None:
            page.step("Шаг из чужого хелпера")

        web = FakeWeb("https://example.com")
        foreign_helper(BasePage(web, "/login"))

        assert web.steps == [("Шаг из чужого хелпера", None, None, None, None)]

    def test_a_group_opened_by_a_page_method_carries_the_page_scope(self):
        """A group opened from the page's own code scopes every step of the block."""

        class LoginPage(BasePage):
            def login_flow(self) -> None:
                return self.group("Войти в аккаунт")

        web = FakeWeb("https://example.com")
        LoginPage(web, "/login").login_flow()

        assert web.groups == [("Войти в аккаунт", None, None, _page_scope(LoginPage))]

    def test_a_group_opened_inline_stays_the_tests_own(self):
        web = FakeWeb("https://example.com")
        page = BasePage(web, "/login")

        page.group("Блок прямо из теста")

        assert web.groups == [("Блок прямо из теста", None, None, None)]

    def test_the_scope_is_the_page_module_path_under_cache(self):
        """The scope value mirrors the page module's dotted path as directories under ``.cache``."""

        class LoginPage(BasePage):
            pass

        parts = LoginPage.__module__.split(".")

        assert _page_scope(LoginPage) == "/".join([*parts[:-1], ".cache", parts[-1]])

    def test_a_subclass_in_another_module_gets_its_own_scope(self):
        """The scope follows the concrete class — a subclass is its own vocabulary."""
        AuthPage = type(  # noqa: N806 — the class name is the assertion's subject
            "AuthPage", (BasePage,), {"__module__": "pages_extra.admin.auth_page"}
        )

        assert _page_scope(AuthPage) == "pages_extra/admin/.cache/auth_page"
