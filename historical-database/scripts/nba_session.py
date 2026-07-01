"""
nba_api transport: curl_cffi Chrome impersonation (to beat Akamai) + retry/backoff.

stats.nba.com sits behind Akamai, which fingerprints TLS handshakes and rejects plain
`requests`/`urllib`. curl_cffi replays Chrome's handshake byte-for-byte. We monkeypatch
nba_api's HTTP layer to send through a curl_cffi session, then wrap every endpoint call
in retry-with-backoff.

Usage:
    from nba_session import patch_nba_session, safe_call
    patch_nba_session()
    df = safe_call(ep.LeagueDashTeamStats, season="2024-25", ...)   # -> DataFrame (frame 0)
    dfs = safe_call(ep.LeagueDashTeamStats, _all_frames=True, ...)  # -> list[DataFrame]
"""

import os
import json
import time
import random
from urllib.parse import urlencode, quote
from curl_cffi import requests as cffi_requests
from nba_api.library.http import NBAHTTP

IMPERSONATE = "chrome120"


def _headers_for(host="stats.nba.com", referer="https://www.nba.com/", origin="https://www.nba.com"):
    """Browser-realistic headers for the given stats host (NBA or WNBA)."""
    return {
        "Host": host,
        "User-Agent": ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
                       "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"),
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
        "Referer": referer,
        "Origin": origin,
        "x-nba-stats-origin": "stats",
        "x-nba-stats-token": "true",
    }


# Active headers (set by patch_nba_session per league). Default = NBA.
STATS_HEADERS = _headers_for()
_session = None


def stats_json_via_zenrows(path, params, host="stats.nba.com", premium=True,
                           country="us", timeout=60):
    """Fetch a stats.<league>.com/stats/<path> endpoint through ZenRows' rotating-proxy API.

    Bypasses the per-IP empty-body throttle that re-trips on sustained GameRotation runs:
    every request exits a fresh residential IP, so NBA's edge can't rate-limit by source IP.
    Returns parsed JSON (raises on HTTP error). Requires ZENROWS_API_KEY in the environment.
    """
    key = os.getenv("ZENROWS_API_KEY")
    if not key:
        raise RuntimeError("ZENROWS_API_KEY not set")
    target = f"https://{host}/stats/{path}?" + urlencode(params)
    extra = f"&premium_proxy=true&proxy_country={country}" if premium else ""
    zurl = f"https://api.zenrows.com/v1/?apikey={key}&url={quote(target, safe='')}{extra}"
    # Forward our real NBA headers, but drop Accept-Encoding: ZenRows relays the origin's
    # compressed bytes raw without a matching Content-Encoding, so force identity -> plain JSON.
    hdr = {k: v for k, v in _headers_for(host, referer=f"https://{host}/",
                                         origin=f"https://{host}").items()
           if k.lower() != "accept-encoding"}
    hdr["Accept-Encoding"] = "identity"
    r = cffi_requests.get(zurl, headers=hdr, timeout=timeout)
    r.raise_for_status()
    return r.json()


def _get_session():
    global _session
    if _session is None:
        _session = cffi_requests.Session(impersonate=IMPERSONATE)
    return _session


def reset_session():
    """Tear down and recreate the curl_cffi session, re-installing it in nba_api.

    stats.nba.com starts returning blank bodies (throttle) on a session that has run many
    sequential heavy calls; a fresh TLS session usually clears it. Called automatically by
    `safe_call` when it sees the empty-body signature."""
    global _session
    try:
        if _session is not None:
            _session.close()
    except Exception:  # noqa: BLE001 — close() is best-effort
        pass
    _session = cffi_requests.Session(impersonate=IMPERSONATE)
    NBAHTTP.set_session(_session)
    NBAHTTP.headers = STATS_HEADERS
    return _session


def _is_empty_body(exc) -> bool:
    """True when the failure is stats.nba.com returning a blank body under load (JSON decode
    fails with 'Expecting value: line 1 column 1'). That's throttling, not a real data gap."""
    return isinstance(exc, json.JSONDecodeError) or "Expecting value" in str(exc)


def patch_nba_session(cfg=None):
    """Route all nba_api stats requests through curl_cffi with Chrome impersonation,
    targeting the league's host (NBA stats.nba.com or WNBA stats.wnba.com).

    nba_api 1.11.x builds the request itself inside `NBAHTTP.send_api_request` and issues it
    via `self.get_session().get(...)`. curl_cffi's Session is a drop-in for requests.Session,
    so the clean injection point is `set_session()` + headers + `base_url`. `cfg` is a league
    config dict (see league.py); omit for NBA."""
    global STATS_HEADERS
    if cfg:
        STATS_HEADERS = _headers_for(cfg["host"], cfg["referer"], cfg["origin"])
        # nba_api defaults base_url to stats.nba.com; point it at the league's host.
        NBAHTTP.base_url = "https://" + cfg["host"] + "/stats/{endpoint}"
    NBAHTTP.set_session(_get_session())
    NBAHTTP.headers = STATS_HEADERS


def safe_call(endpoint_cls, *, _all_frames=False, _retries=5, _base_delay=1.0, timeout=90, **kwargs):
    """
    Call an nba_api endpoint with retry + exponential backoff + jitter.
    Returns the first DataFrame by default, or all frames when _all_frames=True.
    Raises the last exception if every attempt fails (fail loud).
    """
    last_exc = None
    for attempt in range(_retries):
        try:
            obj = endpoint_cls(timeout=timeout, **kwargs)
            frames = obj.get_data_frames()
            return frames if _all_frames else frames[0]
        except Exception as exc:  # noqa: BLE001 — surface after retries
            last_exc = exc
            delay = _base_delay * (2 ** attempt) + random.uniform(0, 0.75)
            # Empty body = throttle, not a data gap: swap in a fresh session and back off harder.
            note = ""
            if _is_empty_body(exc):
                reset_session()
                delay += 2.0
                note = " [empty body -> new session]"
            print(f"  retry {attempt + 1}/{_retries} ({endpoint_cls.__name__}): {exc} "
                  f"-> sleeping {delay:.1f}s{note}")
            time.sleep(delay)
    raise RuntimeError(f"{endpoint_cls.__name__} failed after {_retries} attempts") from last_exc
