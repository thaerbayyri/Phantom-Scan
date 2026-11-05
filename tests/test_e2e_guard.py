"""PS-FIX-23 follow-up: the live-server e2e tests must never target the operator dashboard (:5000) or a non-local host."""
from __future__ import annotations

import pytest

from e2e_guard import DEFAULT_URL, e2e_server_url

OPT_IN = {"PHANTOM_E2E_LIVE_SERVER": "1"}


def test_without_opt_in_nothing_runs_even_if_a_url_is_given() -> None:
    assert e2e_server_url({})[0] is None
    assert e2e_server_url({"PHANTOM_E2E_SERVER_URL": "http://127.0.0.1:5099"})[0] is None
    assert e2e_server_url({"PHANTOM_E2E_LIVE_SERVER": "true"})[0] is None  # only the exact value "1" opts in


def test_opt_in_defaults_to_a_separate_local_port_not_5000() -> None:
    url, reason = e2e_server_url(OPT_IN)
    assert url == DEFAULT_URL == "http://127.0.0.1:5099" and reason == "ok"


@pytest.mark.parametrize("url", ["http://localhost:5000", "http://127.0.0.1:5000", "http://localhost:5000/", "http://[::1]:5000"])
def test_the_operator_dashboard_port_is_always_refused(url: str) -> None:
    got, reason = e2e_server_url({**OPT_IN, "PHANTOM_E2E_SERVER_URL": url})
    assert got is None and "5000" in reason and "dashboard" in reason


@pytest.mark.parametrize("url", ["http://192.168.1.20:5099", "http://example.com:5099", "http://10.0.0.77:5099"])
def test_non_local_hosts_are_refused(url: str) -> None:
    got, reason = e2e_server_url({**OPT_IN, "PHANTOM_E2E_SERVER_URL": url})
    assert got is None and "non-local" in reason


@pytest.mark.parametrize("url", ["https://localhost:5099", "ftp://localhost:5099", "localhost:5099", "http://localhost", "http://localhost:notaport", "http://localhost:99999"])
def test_malformed_or_portless_urls_are_refused(url: str) -> None:
    assert e2e_server_url({**OPT_IN, "PHANTOM_E2E_SERVER_URL": url})[0] is None


def test_other_local_ports_are_accepted_and_normalised() -> None:
    assert e2e_server_url({**OPT_IN, "PHANTOM_E2E_SERVER_URL": "http://localhost:5123/"})[0] == "http://localhost:5123"
    assert e2e_server_url({**OPT_IN, "PHANTOM_E2E_SERVER_URL": "http://127.0.0.1:6000/api"})[0] == "http://127.0.0.1:6000"
