"""Tests for ``Api.request`` serialization in `pybuggy.api.api`.

Covers the single-request serialization algorithm: pydantic ``params``/``json``
dumping (with ``use_aliases``), ``:name`` path substitution, headers/cookies
merge with call-level precedence, ``auth`` defaulting (a placed ``CombineAuth``
is never overridden), and the stripping of ``timeout``/``delay``. The resq
``Session`` verb is mocked at its boundary.
"""

from __future__ import annotations

from unittest import mock

from pybuggy.api.api import Api
from pydantic import BaseModel, ConfigDict, Field

from tests.api.conftest import HeaderAuth


class Params(BaseModel):
    """Query params model with an aliased field."""

    model_config = ConfigDict(populate_by_name=True)

    q: str = Field(default="x", alias="query")
    page: int = 1


class Body(BaseModel):
    """JSON body model with an aliased field."""

    model_config = ConfigDict(populate_by_name=True)

    name: str = Field(default="n", alias="displayName")


def _api(**kwargs: object) -> Api:
    """Build an ``Api`` whose underlying resq verb is a Mock."""
    api = Api(base_url="https://api.example.com", **kwargs)  # type: ignore[arg-type]
    mock.patch.object(api, "_client", create=True).start()
    return api


class TestRequestParams:
    """``params`` serialization: pydantic dump, dict copy, ``use_aliases``."""

    def test_pydantic_params_dumped(self) -> None:
        """A pydantic params model is dumped to a dict (aliases off by default)."""
        api = _api()
        api._client.get = mock.Mock()  # type: ignore[method-assign]

        api.request("GET", "/p", params=Params(q="find"))

        sent = api._client.get.call_args  # type: ignore[attr-defined]
        assert sent.args[0] == "/p"
        assert sent.kwargs["params"] == {"q": "find", "page": 1}

    def test_pydantic_params_with_aliases(self) -> None:
        """``use_aliases=True`` dumps using field aliases."""
        api = _api()
        api._client.get = mock.Mock()  # type: ignore[method-assign]

        api.request("GET", "/p", params=Params(q="find"), use_aliases=True)

        sent = api._client.get.call_args  # type: ignore[attr-defined]
        assert sent.kwargs["params"] == {"query": "find", "page": 1}

    def test_dict_params_copied_not_mutated(self) -> None:
        """A dict params is copied; ``:id`` is removed only from the copy."""
        api = _api()
        api._client.get = mock.Mock()  # type: ignore[method-assign]
        caller_params = {"q": "x", ":id": 7}

        api.request("GET", "/p/:id", params=caller_params)

        assert caller_params == {"q": "x", ":id": 7}  # caller dict untouched

    def test_missing_params_defaults_to_empty(self) -> None:
        """No params leaves an empty query dict."""
        api = _api()
        api._client.get = mock.Mock()  # type: ignore[method-assign]

        api.request("GET", "/p")

        assert api._client.get.call_args.kwargs["params"] == {}  # type: ignore[attr-defined]


class TestRequestPathParams:
    """``:name`` path substitution with the rest kept as the query."""

    def test_path_param_substituted_and_removed_from_query(self) -> None:
        """``:id`` is substituted into the path and dropped from params."""
        api = _api()
        api._client.get = mock.Mock()  # type: ignore[method-assign]

        api.request("GET", "/items/:id", params={":id": 42, "q": "x"})

        sent = api._client.get.call_args  # type: ignore[attr-defined]
        assert sent.args[0] == "/items/42"
        assert sent.kwargs["params"] == {"q": "x"}


class TestRequestJson:
    """``json`` serialization: pydantic dump with ``use_aliases``."""

    def test_pydantic_json_dumped(self) -> None:
        """A pydantic json model is dumped to a dict (aliases off)."""
        api = _api()
        api._client.post = mock.Mock()  # type: ignore[method-assign]

        api.request("POST", "/p", json=Body(name="bob"))

        assert api._client.post.call_args.kwargs["json"] == {"name": "bob"}  # type: ignore[attr-defined]

    def test_pydantic_json_with_aliases(self) -> None:
        """``use_aliases=True`` dumps json using aliases."""
        api = _api()
        api._client.post = mock.Mock()  # type: ignore[method-assign]

        api.request("POST", "/p", json=Body(name="bob"), use_aliases=True)

        assert api._client.post.call_args.kwargs["json"] == {"displayName": "bob"}  # type: ignore[attr-defined]

    def test_dict_json_kept_as_is(self) -> None:
        """A plain dict json body is forwarded unchanged."""
        api = _api()
        api._client.post = mock.Mock()  # type: ignore[method-assign]

        api.request("POST", "/p", json={"k": 1})

        assert api._client.post.call_args.kwargs["json"] == {"k": 1}  # type: ignore[attr-defined]


class TestRequestDefaults:
    """Auth/headers/cookies default injection with call-level precedence."""

    def test_stored_auth_applied_when_none_supplied(self) -> None:
        """The stored ``Api.auth`` is applied when the caller supplied none."""
        stored = HeaderAuth("X-Api", "v")
        api = _api(auth=stored)
        api._client.get = mock.Mock()  # type: ignore[method-assign]

        api.request("GET", "/p")

        assert api._client.get.call_args.kwargs["auth"] is stored  # type: ignore[attr-defined]

    def test_call_auth_not_overridden(self) -> None:
        """A caller-supplied auth is never overridden by the stored one."""
        call_auth = HeaderAuth("X-Call", "c")
        api = _api(auth=HeaderAuth("X-Api", "v"))
        api._client.get = mock.Mock()  # type: ignore[method-assign]

        api.request("GET", "/p", auth=call_auth)

        assert api._client.get.call_args.kwargs["auth"] is call_auth  # type: ignore[attr-defined]

    def test_call_headers_override_stored(self) -> None:
        """Call-level headers win over stored headers on conflict; both merged."""
        api = _api(headers={"X-A": "1", "X-B": "stored"})
        api._client.get = mock.Mock()  # type: ignore[method-assign]

        api.request("GET", "/p", headers={"X-B": "call", "X-C": "2"})

        assert api._client.get.call_args.kwargs["headers"] == {"X-A": "1", "X-B": "call", "X-C": "2"}  # type: ignore[attr-defined]

    def test_stored_headers_applied_when_none_supplied(self) -> None:
        """Stored headers are applied when the caller supplied none."""
        api = _api(headers={"X-A": "1"})
        api._client.get = mock.Mock()  # type: ignore[method-assign]

        api.request("GET", "/p")

        assert api._client.get.call_args.kwargs["headers"] == {"X-A": "1"}  # type: ignore[attr-defined]

    def test_stored_cookies_applied_when_none_supplied(self) -> None:
        """Stored cookies are applied when the caller supplied none."""
        api = _api(cookies={"session": "abc"})
        api._client.get = mock.Mock()  # type: ignore[method-assign]

        api.request("GET", "/p")

        assert api._client.get.call_args.kwargs["cookies"] == {"session": "abc"}  # type: ignore[attr-defined]

    def test_call_cookies_not_overridden(self) -> None:
        """Call-level cookies are not overridden by stored cookies."""
        api = _api(cookies={"session": "stored"})
        api._client.get = mock.Mock()  # type: ignore[method-assign]

        api.request("GET", "/p", cookies={"session": "call"})

        assert api._client.get.call_args.kwargs["cookies"] == {"session": "call"}  # type: ignore[attr-defined]


class TestRequestVerbDispatch:
    """Verb resolution, single request, and polling-option stripping."""

    def test_method_lowercased_to_verb(self) -> None:
        """The method is lowercased and resolved as a Session attribute."""
        api = _api()
        api._client.post = mock.Mock()  # type: ignore[method-assign]

        api.request("POST", "/p", json={})

        api._client.post.assert_called_once()

    def test_timeout_and_delay_never_forwarded(self) -> None:
        """``timeout``/``delay`` are stripped even if the caller passed them."""
        api = _api()
        api._client.get = mock.Mock()  # type: ignore[method-assign]

        api.request("GET", "/p", timeout=30, delay=2)  # type: ignore[call-arg]

        kwargs = api._client.get.call_args.kwargs  # type: ignore[attr-defined]
        assert "timeout" not in kwargs
        assert "delay" not in kwargs

    def test_single_request(self) -> None:
        """Exactly one verb call is issued per request."""
        api = _api()
        api._client.get = mock.Mock()  # type: ignore[method-assign]

        api.request("GET", "/p")

        assert api._client.get.call_count == 1  # type: ignore[attr-defined]
