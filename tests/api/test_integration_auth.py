"""Integration tests for end-to-end call-level auth combining through ``_call``.

Only ``api.request`` and ``ResponseWrapper`` are mocked; the auth primitives run for real.
"""

from __future__ import annotations

from unittest import mock

from goga_tool_pybuggy.api.api import Api
from goga_tool_pybuggy.api.auth import CombineAuth
from goga_tool_pybuggy.api.endpoint import Endpoint

from tests.api.conftest import HeaderAuth, StubRequest


class User:
    """``Auth``-protocol object: exposes ``auth(request)`` and sets X-Token."""

    def auth(self, request: object) -> object:
        """Sign the request by setting the X-Token header (protocol branch)."""
        request.headers["X-Token"] = "from-user"  # type: ignore[attr-defined]
        return request


class ConflictUser:
    """``Auth``-protocol object writing a header also written by ``api.auth``.

    The call-level auth is applied after ``api.auth``, so its value wins on the shared header.
    """

    def auth(self, request: object) -> object:
        """Sign the request by overwriting the X-Conflict header."""
        request.headers["X-Conflict"] = "user"  # type: ignore[attr-defined]
        return request


class TestCallLevelAuthIntegration:
    """Cross-entity tests for call-level auth combining through ``_call``."""

    def test_call_level_auth_combines_api_auth_and_protocol_end_to_end(self) -> None:
        """``_call`` merges ``api.auth`` (AuthBase) with an ``Auth``-protocol call.

        Applying the captured ``CombineAuth`` signs with both; on a shared header the call-level auth wins.
        """
        api = Api(base_url="https://x", auth=HeaderAuth("X-Api", "1"))
        ep = Endpoint(api, "/p", method="GET")

        with mock.patch.object(api, "request") as m:
            ep(auth=User())

        sent = m.call_args.kwargs["auth"]
        assert isinstance(sent, CombineAuth)
        stub = StubRequest()
        sent(stub)
        assert stub.headers["X-Api"] == "1"
        assert stub.headers["X-Token"] == "from-user"

        # On a conflicting header, the call-level auth (applied last) wins.
        conflict_api = Api(base_url="https://x", auth=HeaderAuth("X-Conflict", "api"))
        conflict_ep = Endpoint(conflict_api, "/p", method="GET")

        with mock.patch.object(conflict_api, "request") as m2:
            conflict_ep(auth=ConflictUser())

        sent2 = m2.call_args.kwargs["auth"]
        assert isinstance(sent2, CombineAuth)
        conflict_stub = StubRequest()
        sent2(conflict_stub)
        assert conflict_stub.headers["X-Conflict"] == "user"

    def test_call_and_error_wire_is_negative_through_call(self) -> None:
        """``__call__`` wires ``is_negative=False``; ``error`` wires ``True``.

        Asserted via the mocked ``ResponseWrapper`` constructor's positional ``is_negative`` (index 3).
        """
        api = Api(base_url="https://x")
        ep = Endpoint(api, "/p", method="GET")

        with (
            mock.patch.object(api, "request"),
            mock.patch("goga_tool_pybuggy.api.endpoint.ResponseWrapper") as rw,
        ):
            ep()
        assert rw.call_args.args[3] is False

        with (
            mock.patch.object(api, "request"),
            mock.patch("goga_tool_pybuggy.api.endpoint.ResponseWrapper") as rw_error,
        ):
            ep.error()
        assert rw_error.call_args.args[3] is True
