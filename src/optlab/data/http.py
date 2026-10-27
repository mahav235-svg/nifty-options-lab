"""A small HTTP client with retries and a polite delay between requests.

NSE's archive host rejects requests without a browser-like User-Agent and throttles bursts,
so every downloader in this package goes through here.
"""

from __future__ import annotations

import logging
import time

import requests

log = logging.getLogger(__name__)

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/126.0 Safari/537.36"
    ),
    "Accept": "*/*",
    "Accept-Language": "en-US,en;q=0.9",
}


class NotFoundError(Exception):
    """The server answered 404. For dated archives this usually means a market holiday."""


class HttpClient:
    def __init__(self, min_interval: float = 0.35, retries: int = 4, timeout: float = 30.0) -> None:
        self._session = requests.Session()
        self._session.headers.update(_HEADERS)
        self._min_interval = min_interval
        self._retries = retries
        self._timeout = timeout
        self._last = 0.0

    def get(self, url: str, **kwargs: object) -> requests.Response:
        delay = 1.0
        for attempt in range(1, self._retries + 1):
            wait = self._min_interval - (time.monotonic() - self._last)
            if wait > 0:
                time.sleep(wait)
            self._last = time.monotonic()
            try:
                resp = self._session.get(url, timeout=self._timeout, **kwargs)  # type: ignore[arg-type]
            except requests.RequestException as exc:
                log.warning("GET %s failed (%s), attempt %d", url, exc, attempt)
            else:
                if resp.status_code == 404:
                    raise NotFoundError(url)
                if resp.status_code == 200:
                    return resp
                log.warning("GET %s returned %d, attempt %d", url, resp.status_code, attempt)
            time.sleep(delay)
            delay *= 2
        raise RuntimeError(f"giving up on {url} after {self._retries} attempts")
