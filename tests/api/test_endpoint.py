"""Contract and logic tests for `goga_tool_pybuggy.api.endpoint`.

Contract tests (``TestEndpoint``) lock the facade/API shape: importability,
construction, the ``url_path``/``method`` properties, the presence of
``__call__``/``error``/``_call``, and that ``__call__``/``error`` delegate to
``_call`` with ``is_negative=False``/``True``.

Logic tests (``TestCallAuth``, ``TestCallKeysAndAutocheck``, ``TestCallKwargs``)
exercise ``_call``'s call-level auth resolution, data/error-key fallback, the
``use_autocheck`` override, and kwargs handling. The network and the deferred
``ResponseWrapper`` behavior are mocked at their boundaries (``api.request`` and
``goga_tool_pybuggy.api.endpoint.ResponseWrapper``); the auth primitives
(``CombineAuth``/``AuthWrapper``) are exercised for real.
"""

from __future__ import annotations

from enum import Enum
from pathlib import Path
from unittest import mock

import pytest
from goga_tool_pybuggy.api.api import Api
from goga_tool_pybuggy.api.auth import AuthWrapper, CombineAuth
from goga_tool_pybuggy.api.endpoint import Endpoint
from requests.auth import AuthBase

from tests.api.conftest import HeaderAuth, StubRequest


class User:
    """``Auth``-protocol object: exposes ``auth(request)``, sets X-Token."""

    def auth(self, request: object) -> object:
        """Sign the request by setting the X-Token header."""
        request.headers["X-Token"] = "from-user"  # type: ignore[attr-defined]
        return request


class Dual:
    """Object that is both callable and exposes ``auth(request)``.

    The protocol branch (``auth`` method) must take precedence over the plain
    callable branch (``__call__``).
    """

    def __call__(self, request: object) -> object:
        """Callable branch — sets X-Dual to from-call (must NOT be used)."""
        request.headers["X-Dual"] = "from-call"  # type: ignore[attr-defined]
        return request

    def auth(self, request: object) -> object:
        """Protocol branch — sets X-Dual to from-auth (must be used)."""
        request.headers["X-Dual"] = "from-auth"  # type: ignore[attr-defined]
        return request


class TestEndpoint:
    """Contract tests for the ``Endpoint`` facade/API shape."""

    def test_imports_succeed(self) -> None:
        """Endpoint is importable from goga_tool_pybuggy.api.endpoint."""
        assert isinstance(Endpoint, type)

    def test_constructs_and_stores_url_path_method(self) -> None:
        """Endpoint stores url_path/method and exposes them as properties."""
        api = Api(base_url="https://x")
        ep = Endpoint(api, "/p", method="GET")

        assert ep.url_path == "/p"
        assert ep.method == "GET"

    def test_methods_exist(self) -> None:
        """__call__, error, and _call are present on the facade."""
        api = Api(base_url="https://x")
        ep = Endpoint(api, "/p", method="GET")

        assert callable(ep)
        assert callable(ep.error)
        assert callable(ep._call)

    def test_call_delegates_with_is_negative_false(self) -> None:
        """__call__ delegates to _call with is_negative=False and the kwargs."""
        api = Api(base_url="https://x")
        ep = Endpoint(api, "/p", method="GET")

        with mock.patch.object(ep, "_call") as call:
            ep(json={"a": 1})

        call.assert_called_once_with(False, json={"a": 1})

    def test_error_delegates_with_is_negative_true(self) -> None:
        """error delegates to _call with is_negative=True and the kwargs."""
        api = Api(base_url="https://x")
        ep = Endpoint(api, "/p", method="GET")

        with mock.patch.object(ep, "_call") as call:
            ep.error(json={"a": 1})

        call.assert_called_once_with(True, json={"a": 1})


class TestCallAuth:
    """Logic tests for ``_call``'s call-level auth resolution."""

    def test_call_level_authbase_added_directly_after_api_auth(self) -> None:
        """A call-level AuthBase is added after api.auth; both sign, api first."""
        api = Api(base_url="https://x", auth=HeaderAuth("X-Api", "api"))
        ep = Endpoint(api, "/p", method="GET")
        token = HeaderAuth("X-Token", "token")

        with mock.patch.object(api, "request") as m:
            ep(auth=token)

        sent = m.call_args.kwargs["auth"]
        assert isinstance(sent, CombineAuth)
        stub = StubRequest()
        sent(stub)
        assert stub.headers["X-Api"] == "api"
        assert stub.headers["X-Token"] == "token"

    def test_call_level_auth_protocol_wraps_bound_method(self) -> None:
        """An Auth-protocol object's bound auth method is wrapped in AuthWrapper."""
        api = Api(base_url="https://x")
        ep = Endpoint(api, "/p", method="GET")

        with mock.patch.object(api, "request") as m:
            ep(auth=User())

        sent = m.call_args.kwargs["auth"]
        assert isinstance(sent, CombineAuth)
        assert isinstance(sent._chain[0], AuthWrapper)
        stub = StubRequest()
        sent(stub)
        assert stub.headers["X-Token"] == "from-user"

    def test_call_level_plain_callable_wrapped(self) -> None:
        """A plain callable call-level auth is wrapped; func is the callable itself."""

        def fn(request: object) -> object:
            return request

        api = Api(base_url="https://x")
        ep = Endpoint(api, "/p", method="GET")

        with mock.patch.object(api, "request") as m:
            ep(auth=fn)

        sent = m.call_args.kwargs["auth"]
        assert isinstance(sent, CombineAuth)
        assert isinstance(sent._chain[0], AuthWrapper)
        assert sent._chain[0].func is fn

    def test_no_call_level_auth_leaves_request_to_api_auth(self) -> None:
        """Without a call-level auth, no CombineAuth is built; api.auth setdefaults."""
        api = Api(base_url="https://x")
        ep = Endpoint(api, "/p", method="GET")

        with mock.patch.object(api, "request") as m:
            ep(json={"a": 1})

        assert "auth" not in m.call_args.kwargs

    def test_call_level_auth_without_api_auth(self) -> None:
        """api.auth is None + call-level AuthBase → chain contains only the call-level."""
        api = Api(base_url="https://x")
        ep = Endpoint(api, "/p", method="GET")
        token = HeaderAuth("X-Token", "t")

        with mock.patch.object(api, "request") as m:
            ep(auth=token)

        sent = m.call_args.kwargs["auth"]
        assert isinstance(sent, CombineAuth)
        assert len(sent._chain) == 1
        assert sent._chain[0] is token

    def test_call_level_combineauth_added_directly(self) -> None:
        """A CombineAuth passed as call-level auth is added directly (nesting allowed).

        Both ``CombineAuth`` and the stored ``api.auth`` are ``AuthBase``, so the
        call-level ``CombineAuth`` is appended to the outer chain verbatim (not
        re-wrapped in an ``AuthWrapper``), after ``api.auth``.
        """
        api = Api(base_url="https://x", auth=HeaderAuth("X-Api", "api"))
        ep = Endpoint(api, "/p", method="GET")
        nested = CombineAuth().add_auth(HeaderAuth("X-Nested", "n"))

        with mock.patch.object(api, "request") as m:
            ep(auth=nested)

        sent = m.call_args.kwargs["auth"]
        assert isinstance(sent, CombineAuth)
        assert sent._chain[1] is nested
        assert not isinstance(sent._chain[1], AuthWrapper)

    def test_call_level_auth_callable_with_auth_method_prefers_protocol(self) -> None:
        """An object both callable and exposing auth is treated as the protocol."""
        api = Api(base_url="https://x")
        ep = Endpoint(api, "/p", method="GET")

        with mock.patch.object(api, "request") as m:
            ep(auth=Dual())

        sent = m.call_args.kwargs["auth"]
        wrapper = sent._chain[0]
        assert isinstance(wrapper, AuthWrapper)
        assert wrapper.func.__name__ == "auth"
        stub = StubRequest()
        sent(stub)
        assert stub.headers["X-Dual"] == "from-auth"

    def test_invalid_call_level_auth_raises_typeerror(self) -> None:
        """An unsupported call-level auth type raises TypeError before any request."""
        api = Api(base_url="https://x")
        ep = Endpoint(api, "/p", method="GET")

        with (
            mock.patch.object(api, "request") as m,
            pytest.raises(TypeError),
        ):
            ep(auth=12345)

        assert not m.called


class TestCallKeysAndAutocheck:
    """Logic tests for key resolution and the use_autocheck override."""

    def test_data_key_endpoint_overrides_api(self) -> None:
        """Endpoint data_key/error_key win over the Api-level keys when set."""
        api = Api(base_url="https://x", data_key="api-d", error_key="api-e")
        ep = Endpoint(api, "/p", method="GET", data_key="ep-d", error_key="ep-e")

        with (
            mock.patch.object(api, "request"),
            mock.patch("goga_tool_pybuggy.api.endpoint.ResponseWrapper") as rw,
        ):
            ep()

        assert rw.call_args.args[1].data_key == "ep-d"
        assert rw.call_args.args[1].error_key == "ep-e"

    def test_data_key_falls_back_to_api(self) -> None:
        """Without per-endpoint keys, the Api-level keys are used."""
        api = Api(base_url="https://x", data_key="api-d", error_key="api-e")
        ep = Endpoint(api, "/p", method="GET")

        with (
            mock.patch.object(api, "request"),
            mock.patch("goga_tool_pybuggy.api.endpoint.ResponseWrapper") as rw,
        ):
            ep()

        assert rw.call_args.args[1].data_key == "api-d"
        assert rw.call_args.args[1].error_key == "api-e"

    def test_assert_polling_options_flow_from_api(self) -> None:
        """``_call`` forwards Api's assert_timeout/delay/class options into AssertConfig."""
        api = Api(
            base_url="https://x",
            assert_timeout=10,
            assert_delay=0.5,
            assert_field_class="mod:FieldCls",
            assert_response_class="mod:ResponseCls",
        )
        ep = Endpoint(api, "/p", method="GET")

        with (
            mock.patch.object(api, "request"),
            mock.patch("goga_tool_pybuggy.api.endpoint.ResponseWrapper") as rw,
        ):
            ep()

        config = rw.call_args.args[1]
        assert config.timeout == 10
        assert config.delay == 0.5
        assert config.assert_field_class == "mod:FieldCls"
        assert config.assert_response_class == "mod:ResponseCls"

    def test_assert_polling_options_default_to_none(self) -> None:
        """Without Api-level assert options, AssertConfig's polling fields are None."""
        api = Api(base_url="https://x")
        ep = Endpoint(api, "/p", method="GET")

        with (
            mock.patch.object(api, "request"),
            mock.patch("goga_tool_pybuggy.api.endpoint.ResponseWrapper") as rw,
        ):
            ep()

        config = rw.call_args.args[1]
        assert config.timeout is None
        assert config.delay is None
        assert config.assert_field_class is None
        assert config.assert_response_class is None

    def test_use_autocheck_call_level_override(self) -> None:
        """use_autocheck=False per call disables it; default keeps Endpoint's True."""
        api = Api(base_url="https://x")
        ep = Endpoint(api, "/p", method="GET")

        with (
            mock.patch.object(api, "request"),
            mock.patch("goga_tool_pybuggy.api.endpoint.ResponseWrapper") as rw,
        ):
            ep(use_autocheck=False)
        assert rw.call_args.args[2] is False

        with (
            mock.patch.object(api, "request"),
            mock.patch("goga_tool_pybuggy.api.endpoint.ResponseWrapper") as rw,
        ):
            ep()
        assert rw.call_args.args[2] is True

    def test_call_wires_is_negative_false(self) -> None:
        """__call__ wires ResponseWrapper with is_negative=False."""
        api = Api(base_url="https://x")
        ep = Endpoint(api, "/p", method="GET")

        with (
            mock.patch.object(api, "request"),
            mock.patch("goga_tool_pybuggy.api.endpoint.ResponseWrapper") as rw,
        ):
            ep()

        assert rw.call_args.args[3] is False

    def test_error_wires_is_negative_true(self) -> None:
        """error wires ResponseWrapper with is_negative=True."""
        api = Api(base_url="https://x")
        ep = Endpoint(api, "/p", method="GET")

        with (
            mock.patch.object(api, "request"),
            mock.patch("goga_tool_pybuggy.api.endpoint.ResponseWrapper") as rw,
        ):
            ep.error()

        assert rw.call_args.args[3] is True

    def test_status_normalizes_enum_value(self) -> None:
        """An Enum status is normalized to its value before wiring ResponseWrapper."""

        class _Status(Enum):
            """Stand-in status Enum."""

            CREATED = 201

        api = Api(base_url="https://x")
        ep = Endpoint(api, "/p", method="GET", status=_Status.CREATED)

        with (
            mock.patch.object(api, "request"),
            mock.patch("goga_tool_pybuggy.api.endpoint.ResponseWrapper") as rw,
        ):
            ep()

        assert rw.call_args.args[1].status == 201

    def test_schemas_dir_resolved_from_caller_frame(self) -> None:
        """schemas_dir resolves to the caller module's parent dir joined with 'schemas'.

        ``Endpoint.__init__`` inspects ``stack()[1]`` (the caller frame), reads its
        ``__file__``, and sets ``schemas_dir`` to that file's parent / 'schemas'.
        Constructed directly in this test function, that is this test module's dir.
        """
        api = Api(base_url="https://x")
        ep = Endpoint(api, "/p", method="GET")

        assert ep.schemas_dir == Path(__file__).parent / "schemas"

    def test_call_wires_schemas_dir_to_response_wrapper(self) -> None:
        """_call passes the resolved schemas_dir as ResponseWrapper's schemas_dir arg."""
        api = Api(base_url="https://x")
        ep = Endpoint(api, "/p", method="GET")

        with (
            mock.patch.object(api, "request"),
            mock.patch("goga_tool_pybuggy.api.endpoint.ResponseWrapper") as rw,
        ):
            ep()

        assert rw.call_args.args[1].schemas_dir == ep.schemas_dir


class TestCallKwargs:
    """Logic tests for kwargs handling in ``_call``."""

    def test_call_does_not_mutate_caller_kwargs(self) -> None:
        """The caller's kwargs dict is not mutated in place.

        Probes with ``use_autocheck``, which ``_call`` pops from its private copy
        and never re-adds: if the dict were not copied, the caller's copy would
        lose the key. This is the exact signal the copy (``dict(kwargs)``) exists
        to provide; checking only ``auth``/``json`` (popped-then-re-added /
        untouched) would not detect a dropped copy.
        """
        api = Api(base_url="https://x")
        ep = Endpoint(api, "/p", method="GET")
        token = HeaderAuth("X-T", "t")
        caller_kwargs: dict[str, object] = {"json": {"a": 1}, "auth": token, "use_autocheck": False}

        with mock.patch.object(api, "request"):
            ep(**caller_kwargs)

        assert set(caller_kwargs.keys()) == {"json", "auth", "use_autocheck"}
        assert caller_kwargs["json"] == {"a": 1}
        assert caller_kwargs["auth"] is token
        assert isinstance(caller_kwargs["auth"], AuthBase)
        assert caller_kwargs["use_autocheck"] is False

    def test_call_level_auth_and_use_autocheck_not_forwarded(self) -> None:
        """use_autocheck is popped and auth is the CombineAuth, not the raw AuthBase."""
        api = Api(base_url="https://x")
        ep = Endpoint(api, "/p", method="GET")
        token = HeaderAuth("X-Token", "t")

        with mock.patch.object(api, "request") as m:
            ep(auth=token, use_autocheck=False, json={"a": 1})

        kwargs = m.call_args.kwargs
        assert "json" in kwargs
        assert "use_autocheck" not in kwargs
        assert isinstance(kwargs["auth"], CombineAuth)
        assert kwargs["auth"] is not token

    def test_request_dispatched_with_method_and_url_path(self) -> None:
        """api.request is called positionally with method and url_path."""
        api = Api(base_url="https://x")
        ep = Endpoint(api, "/p", method="POST")

        with mock.patch.object(api, "request") as m:
            ep(json={"a": 1})

        assert m.call_args.args == ("POST", "/p")


class TestEndpointAdapter:
    """Logic tests for the per-endpoint ``adapter`` override plumbing."""

    def test_adapter_defaults_to_none(self) -> None:
        """Endpoint defaults adapter to None (fall back to the Api default)."""
        api = Api(base_url="https://x")
        ep = Endpoint(api, "/p", method="GET")

        assert ep.adapter is None

    def test_adapter_stored_from_construction(self) -> None:
        """Endpoint exposes the adapter passed at construction."""
        api = Api(base_url="https://x")
        ep = Endpoint(api, "/p", method="GET", adapter="requests")

        assert ep.adapter == "requests"

    def test_adapter_is_read_only(self) -> None:
        """adapter has no setter: assignment raises AttributeError."""
        api = Api(base_url="https://x")
        ep = Endpoint(api, "/p", method="GET")

        with pytest.raises(AttributeError):
            ep.adapter = "requests"

    def test_call_passes_adapter_to_api_request(self) -> None:
        """_call injects the endpoint's adapter into the api.request kwargs."""
        api = Api(base_url="https://x")
        ep = Endpoint(api, "/p", method="GET", adapter="requests")

        with mock.patch.object(api, "request") as m:
            ep(json={"a": 1})

        assert m.call_args.kwargs["adapter"] == "requests"

    def test_call_passes_none_adapter_when_unset(self) -> None:
        """_call passes adapter=None (Api default fallback) when the endpoint has none."""
        api = Api(base_url="https://x")
        ep = Endpoint(api, "/p", method="GET")

        with mock.patch.object(api, "request") as m:
            ep(json={"a": 1})

        assert m.call_args.kwargs["adapter"] is None

    def test_call_does_not_forward_adapter_to_caller_kwargs(self) -> None:
        """The injected adapter lands in api.request, not the caller's kwargs."""
        api = Api(base_url="https://x")
        ep = Endpoint(api, "/p", method="GET", adapter="requests")
        caller_kwargs: dict[str, object] = {"json": {"a": 1}}

        with mock.patch.object(api, "request"):
            ep(**caller_kwargs)

        assert "adapter" not in caller_kwargs
