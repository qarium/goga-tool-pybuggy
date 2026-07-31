"""`pybuggy.api` cell facade.

Exposes the contract entities of the runtime HTTP cell:

- ``Api`` — HTTP client composing a ``resq.Session``; holds auth/headers/cookies/
  data_key/error_key and injects them into each request.
- ``Endpoint`` — callable route over an ``Api``; ``__call__`` (positive) and
  ``error`` (negative) issue a single request per call and return a
  ``ResponseWrapper``.
- ``ResponseWrapper`` — context manager over the raw response.
- ``Expected`` — two-level assert dispatcher: response-level checks
  (``has_status_code``/``has_header``/``json_*``/``jsonschema_*``) and a callable
  field-level entry (``expected('data.items') -> AssertField``).
- ``AssertField`` — field-level assert over a resolved body value (matchcrest
  matchers); produced by ``Expected.__call__``, re-exported for type-hinting.
- ``Auth`` — structural ``Protocol`` for type-hinting per-call authenticators.

``CombineAuth`` and ``AuthWrapper`` are internal to the cell (used by
``Endpoint._call`` to combine a call-level authenticator with the stored
``Api`` auth) and are deliberately not re-exported here.
"""

from .api import Api
from .asserts import AssertField, Expected
from .auth import Auth
from .endpoint import Endpoint
from .response import ResponseWrapper

__all__ = ["Api", "AssertField", "Auth", "Endpoint", "Expected", "ResponseWrapper"]
