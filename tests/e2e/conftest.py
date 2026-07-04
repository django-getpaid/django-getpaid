"""E2E test fixtures for django-getpaid.

Provides fixtures for:
- Browser/page fixtures from pytest-playwright
- Order/user factories for test data

The Django server is expected to be running on http://e2e-server:8000/
(when running in Docker Compose) or http://localhost:8000/ (local).
"""

import os
import pathlib
import socket
from urllib.parse import urlparse

import pytest
from playwright.sync_api import Page

# Detect environment: Docker Compose uses container name, local uses localhost
if os.environ.get('E2E_SERVER_URL'):
    E2E_SERVER_URL = os.environ['E2E_SERVER_URL']
elif pathlib.Path('/.dockerenv').exists():
    E2E_SERVER_URL = 'http://e2e-server:8000'
else:
    E2E_SERVER_URL = 'http://localhost:8000'


def _e2e_server_reachable(url: str, timeout: float = 1.0) -> bool:
    """Return True when the getpaid example e2e server is running at url.

    First does a cheap TCP connect with a short timeout, then verifies
    the server actually is the example app (another application might
    be listening on the same port) by requesting the fake gateway page
    that only the example project serves.
    """
    parsed = urlparse(url)
    host = parsed.hostname or 'localhost'
    port = parsed.port or (443 if parsed.scheme == 'https' else 80)
    try:
        with socket.create_connection((host, port), timeout=timeout):
            pass
    except OSError:
        return False

    from urllib.error import URLError
    from urllib.request import urlopen

    probe_url = f'{url.rstrip("/")}/paywall/fake_gateway/'
    try:
        with urlopen(probe_url, timeout=2.0) as response:  # noqa: S310
            return response.status == 200
    except (URLError, OSError, ValueError):
        return False


@pytest.fixture(scope='session', autouse=True)
def _require_e2e_server():
    """Skip all E2E tests when the e2e server is not running."""
    if not _e2e_server_reachable(E2E_SERVER_URL):
        pytest.skip(
            f'E2E server not reachable at {E2E_SERVER_URL}; '
            'start it with `make test-e2e` (docker compose e2e-server).',
        )


@pytest.fixture
def page(browser) -> Page:
    """Playwright page fixture."""
    return browser.new_page()
