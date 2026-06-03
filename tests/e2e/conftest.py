"""E2E test fixtures for django-getpaid.

Provides fixtures for:
- Browser/page fixtures from pytest-playwright
- Order/user factories for test data

The Django server is expected to be running on http://e2e-server:8000/
(when running in Docker Compose) or http://localhost:8000/ (local).
"""

import os

import pytest
from playwright.sync_api import Page

# Detect environment: Docker Compose uses container name, local uses localhost
if os.environ.get('E2E_SERVER_URL'):
    E2E_SERVER_URL = os.environ['E2E_SERVER_URL']
elif os.path.exists('/.dockerenv'):
    E2E_SERVER_URL = 'http://e2e-server:8000'
else:
    E2E_SERVER_URL = 'http://localhost:8000'


@pytest.fixture
def page(browser) -> Page:
    """Playwright page fixture."""
    return browser.new_page()
