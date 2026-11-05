"""Decide whether the live-server e2e tests may run, and against which URL.

Those tests log in, ingest samples and create sessions on whatever server answers. Running them against an operator's
dashboard pollutes its data/sessions (PS-FIX-23), so they require:
  * explicit opt-in:  PHANTOM_E2E_LIVE_SERVER=1
  * a throw-away LOCAL server on its own port (default http://127.0.0.1:5099; override PHANTOM_E2E_SERVER_URL)
  * never the operator dashboard port 5000, and never a non-local host.

Start such a server with its OWN data directory so it can never write into an operator's data/sessions (PS-FIX-27):

    PHANTOM_DATA_DIR=<scratch dir> PORT=5099 npm run dev

PHANTOM_DATA_DIR relocates sessions, audit log, operator seed, runtime settings, datasets and phase-test logs (default: ``data``).
"""
from __future__ import annotations

from typing import Mapping
from urllib.parse import urlparse

OPERATOR_PORT = 5000
DEFAULT_URL = "http://127.0.0.1:5099"
LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1"}


def e2e_server_url(env: Mapping[str, str]) -> tuple[str | None, str]:
    """(url, reason): url is None when the tests must not run; reason says why (or 'ok')."""
    if env.get("PHANTOM_E2E_LIVE_SERVER") != "1":
        return None, "opt-in required: set PHANTOM_E2E_LIVE_SERVER=1"
    raw = env.get("PHANTOM_E2E_SERVER_URL") or DEFAULT_URL
    try:
        parsed = urlparse(raw)
        port = parsed.port
    except ValueError:
        return None, f"invalid PHANTOM_E2E_SERVER_URL {raw!r}"
    if parsed.scheme != "http" or not parsed.hostname:
        return None, f"PHANTOM_E2E_SERVER_URL must be an http URL, got {raw!r}"
    if parsed.hostname not in LOCAL_HOSTS:
        return None, f"refusing non-local host {parsed.hostname!r}: use a throw-away local server"
    if port is None:
        return None, "PHANTOM_E2E_SERVER_URL must include an explicit port (not :5000)"
    if port == OPERATOR_PORT:
        return None, f"refusing port {OPERATOR_PORT}: that is the operator dashboard; start a throw-away server on another port"
    return f"{parsed.scheme}://{parsed.hostname}:{port}", "ok"
