from __future__ import annotations

import json
import ssl
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

import certifi

_SSL_CONTEXT = ssl.create_default_context(cafile=certifi.where())

DEFAULT_TIMEOUT = 6.0


class Response:
    __slots__ = ("status_code", "text")

    def __init__(self, status_code: int, text: str) -> None:
        self.status_code = status_code
        self.text = text

    def json(self) -> Any:
        return json.loads(self.text)


def get(
    url: str,
    params: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
    timeout: float = DEFAULT_TIMEOUT,
) -> Response:
    if params:
        separator = "&" if "?" in url else "?"
        url = f"{url}{separator}{urllib.parse.urlencode(params)}"

    request = urllib.request.Request(url, headers=dict(headers or {}), method="GET")
    try:
        with urllib.request.urlopen(request, timeout=timeout, context=_SSL_CONTEXT) as response:
            return Response(response.status, response.read().decode("utf-8", errors="replace"))
    except urllib.error.HTTPError as error:
        return Response(error.code, error.read().decode("utf-8", errors="replace"))
