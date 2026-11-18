"""Shared HTTP session with retries and a polite User-Agent."""
from __future__ import annotations

import logging

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

log = logging.getLogger(__name__)

USER_AGENT = "gxp-tender-monitor/0.1 (+https://github.com/tr4allzz/przetargi)"
TIMEOUT = 45


def session() -> requests.Session:
    s = requests.Session()
    retry = Retry(
        total=4,
        backoff_factor=2,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=frozenset({"GET", "POST"}),
        respect_retry_after_header=True,
    )
    s.mount("https://", HTTPAdapter(max_retries=retry))
    s.headers.update({"User-Agent": USER_AGENT, "Accept": "application/json"})
    return s


def get_json(s: requests.Session, url: str, **kw):
    kw.setdefault("timeout", TIMEOUT)
    r = s.get(url, **kw)
    r.raise_for_status()
    return r.json()


def post_json(s: requests.Session, url: str, payload: dict, **kw):
    r = s.post(url, json=payload, timeout=TIMEOUT, **kw)
    if r.status_code >= 400:
        log.error("POST %s -> %s: %s", url, r.status_code, r.text[:500])
    r.raise_for_status()
    return r.json()
