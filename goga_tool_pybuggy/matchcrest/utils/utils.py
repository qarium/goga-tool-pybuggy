import logging
import time
import typing as t
from datetime import date, datetime
from functools import wraps
from urllib.parse import urlparse

import requests
from dateutil.parser import parse as parse_date_iso_string

DEFAULT_TIMEOUT: t.Final = 5
DEFAULT_DELAY: t.Final = 0.5

WrappedType = t.Callable[[...], t.Any]  # type: ignore[misc]
logger = logging.getLogger(__name__)


def waiting_for(f: WrappedType, *,
                args: t.Optional[list | tuple] = None,
                kwargs: t.Optional[dict] = None,
                timeout: int | float = DEFAULT_TIMEOUT,
                delay: int | float = DEFAULT_DELAY,
                hook: t.Optional[t.Callable[[t.Any], t.Any]] = None) -> t.Any:
    args = args or tuple()
    kwargs = kwargs or {}

    start_time = time.time()

    while time.time() <= start_time + timeout:
        rv = f(*args, **kwargs)

        if callable(hook):
            rv = hook(rv)

        if rv:
            return rv

        time.sleep(delay)

    raise TimeoutError(f'waiting for success call "{f.__name__}" timeout={timeout}')


def join(*parts: str) -> str:
    """Join URL parts, collapsing duplicate slashes between them."""
    url = ''
    for part in parts:
        url += part.rstrip('/')
    if parts[len(parts) - 1].endswith('/'):
        url += '/'
    return url


def url_is_valid(url: str, is_live: bool = False, allowed_protocols: t.Optional[list | tuple] = None) -> bool:
    allowed_protocols = allowed_protocols or ['https', 'http']
    url_link = urlparse(url)
    is_relative_link = not bool(url_link.scheme)

    if all([(not is_relative_link and url_link.scheme in allowed_protocols) or True, url_link.netloc]):
        protocol = f'{next(iter(allowed_protocols))}://' if is_relative_link else ''

        if is_live and not url_is_live(join(protocol, url)):
            return False

        return True
    return False


def url_is_live(url: str) -> bool:
    response = requests.get(url)
    return 200 <= response.status_code <= 299


def date_to_timestamp(value: date | datetime) -> float:
    if isinstance(value, datetime):
        return value.timestamp()

    if isinstance(value, date):
        return parse_date_iso_string(value.isoformat()).timestamp()

    raise ValueError(f'"{value}" is not date or datetime object')


def allow_failure(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        try:
            return f(*args, **kwargs)
        # pylint: disable=broad-exception-caught
        except Exception as exc:
            logger.exception(exc)

        return None

    return wrapper
