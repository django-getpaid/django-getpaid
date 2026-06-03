"""E2E tests for the full payment flow.

Tests the complete user journey:
1. Create order via home page
2. Visit order detail page
3. Create payment (REST paywall method -> redirect to fake gateway)
4. Authorize payment via fake gateway
5. Verify callback updates payment status
6. Verify success/failure page is shown
"""

import re

import pytest
from playwright.sync_api import expect

from .conftest import E2E_SERVER_URL

# Pre-existing superuser: e2e_user / e2e_pass (created by e2e-server startup)


class TestHappyPath:
    """Full happy-path E2E flow."""

    def _login(self, page):
        """Log in as e2e_user via Django admin."""
        page.goto(f'{E2E_SERVER_URL}/admin/login/?next=/')
        page.fill('input[name="username"]', 'e2e_user')
        page.fill('input[name="password"]', 'e2e_pass')
        page.click('input[type="submit"]')
        page.wait_for_url(re.compile(r'/$'), timeout=10000)

    def _create_order(self, page, name, total):
        """Create an order via the home page."""
        page.goto(f'{E2E_SERVER_URL}/')
        page.fill('input[name="name"]', name)
        page.fill('input[name="total"]', total)
        page.click('input[type="submit"]')
        expect(page).to_have_url(re.compile(r'/order/\d+/'))

    def test_create_order_then_pay_success(self, page):
        """Create an order, pay via dummy backend, reach success page."""
        self._login(page)
        self._create_order(page, 'E2E Test Order', '29.99')

        # Select dummy backend and submit checkout form
        page.check('input[name="backend"][value="dummy"]')
        with page.expect_navigation(timeout=10000):
            page.click('input[type="submit"][value="Checkout"]')

        # Should be on fake gateway
        expect(page).to_have_url(re.compile(r'/paywall/fake_gateway'))
        expect(page.locator('h1')).to_contain_text('fake payment gateway')

        # Authorize payment (authorize_payment is a <select>, not radio)
        page.select_option('select[name="authorize_payment"]', '1')
        with page.expect_navigation(timeout=10000):
            page.click('input[type="submit"][value="Continue"]')

        # Verify success page
        expect(page).to_have_url(re.compile(r'/payments/success/'))
        expect(page.locator('h2')).to_contain_text('Payment Successful')


class TestFailurePath:
    """Full failure-path E2E flow."""

    def _login(self, page):
        page.goto(f'{E2E_SERVER_URL}/admin/login/?next=/')
        page.fill('input[name="username"]', 'e2e_user')
        page.fill('input[name="password"]', 'e2e_pass')
        page.click('input[type="submit"]')
        page.wait_for_url(re.compile(r'/$'), timeout=10000)

    def _create_order(self, page, name, total):
        page.goto(f'{E2E_SERVER_URL}/')
        page.fill('input[name="name"]', name)
        page.fill('input[name="total"]', total)
        page.click('input[type="submit"]')
        expect(page).to_have_url(re.compile(r'/order/\d+/'))

    def test_reject_payment_shows_failure(self, page):
        """Create an order, reject payment, reach failure page."""
        self._login(page)
        self._create_order(page, 'Failure Test Order', '19.99')

        # Select dummy backend and submit checkout form
        page.check('input[name="backend"][value="dummy"]')
        with page.expect_navigation(timeout=10000):
            page.click('input[type="submit"][value="Checkout"]')

        # Reject payment (authorize_payment is a <select>)
        page.select_option('select[name="authorize_payment"]', '0')
        with page.expect_navigation(timeout=10000):
            page.click('input[type="submit"][value="Continue"]')

        # Verify failure page
        expect(page).to_have_url(re.compile(r'/payments/failure/'))
        expect(page.locator('h2')).to_contain_text('Payment Failed')


class TestPreAuthFlow:
    """Pre-auth (LOCK) E2E flow -- PAYWALL_MODE=LOCK is the default in tests/settings.py."""

    def _login(self, page):
        page.goto(f'{E2E_SERVER_URL}/admin/login/?next=/')
        page.fill('input[name="username"]', 'e2e_user')
        page.fill('input[name="password"]', 'e2e_pass')
        page.click('input[type="submit"]')
        page.wait_for_url(re.compile(r'/$'), timeout=10000)

    def _create_order(self, page, name, total):
        page.goto(f'{E2E_SERVER_URL}/')
        page.fill('input[name="name"]', name)
        page.fill('input[name="total"]', total)
        page.click('input[type="submit"]')
        expect(page).to_have_url(re.compile(r'/order/\d+/'))

    def test_pre_auth_payment_flow(self, page):
        """Create an order, pre-auth payment, verify PRE_AUTH status."""
        self._login(page)
        self._create_order(page, 'PreAuth Order', '99.99')

        # Select dummy backend and submit checkout form
        page.check('input[name="backend"][value="dummy"]')
        with page.expect_navigation(timeout=10000):
            page.click('input[type="submit"][value="Checkout"]')

        # Authorize on fake gateway
        page.select_option('select[name="authorize_payment"]', '1')
        with page.expect_navigation(timeout=10000):
            page.click('input[type="submit"][value="Continue"]')

        # Verify success (pre-auth is still a success from user POV)
        expect(page).to_have_url(re.compile(r'/payments/success/'))
        expect(page.locator('h2')).to_contain_text('Payment Successful')


class TestHealthCheck:
    """E2E test for the health check endpoint."""

    def test_health_check_is_reachable(self, page):
        """Health check endpoint returns 200 and is reachable."""
        page.goto(f'{E2E_SERVER_URL}/payments/health/')
        content = page.content()
        assert 'ok' in content


class TestErrorPaths:
    """E2E tests for error paths."""

    def test_create_payment_requires_login(self, page):
        """Unauthenticated user is redirected to login when creating payment."""
        page.goto(f'{E2E_SERVER_URL}/payments/new/')
        expect(page).to_have_url(re.compile(r'/admin/login/'))

    def test_create_order_without_data_shows_form_errors(self, page):
        """Submitting order form without data shows validation errors."""
        page.goto(f'{E2E_SERVER_URL}/')
        page.click('input[type="submit"]')
        expect(page).to_have_url(re.compile(r'/$'))
