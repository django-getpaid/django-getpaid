"""Tests for the dummy payment backend (rewritten from scratch).

The dummy backend should be a self-contained payment processor for
development and testing — no external HTTP calls, no paywall app dependency.
"""

import json
from decimal import Decimal
from unittest.mock import MagicMock

import pytest
import swapper

from getpaid.types import PaymentStatus as ps

pytestmark = pytest.mark.django_db

Order = swapper.load_model('getpaid', 'Order')
Payment = swapper.load_model('getpaid', 'Payment')


def _make_payment(**kwargs):
    """Helper to create an Order + Payment pair."""
    order = Order.objects.create()
    defaults = {
        'order': order,
        'currency': order.currency,
        'amount_required': Decimal(str(order.get_total_amount())),
        'backend': 'getpaid.backends.dummy',
        'description': order.get_description(),
    }
    defaults.update(kwargs)
    return Payment.objects.create(**defaults)


class TestDummyProcessorAttributes:
    """Test that the dummy processor has required class attributes."""

    def test_slug(self):
        from getpaid.backends.dummy.processor import PaymentProcessor

        assert PaymentProcessor.slug == 'dummy'

    def test_display_name(self):
        from getpaid.backends.dummy.processor import PaymentProcessor

        assert PaymentProcessor.display_name == 'Dummy'

    def test_accepted_currencies(self):
        from getpaid.backends.dummy.processor import PaymentProcessor

        assert 'PLN' in PaymentProcessor.accepted_currencies
        assert 'EUR' in PaymentProcessor.accepted_currencies

    def test_no_requests_import(self):
        """The dummy backend should NOT use the requests library."""
        import importlib
        import sys

        # Reload to ensure fresh import
        mod = importlib.import_module('getpaid.backends.dummy.processor')
        source = open(mod.__file__).read()
        assert 'import requests' not in source


class TestDummyPrepareTransaction:
    """Test prepare_transaction for all three methods."""

    def test_rest_method_returns_redirect(self, rf, settings):
        settings.GETPAID_BACKEND_SETTINGS = {
            'getpaid.backends.dummy': {'paywall_method': 'REST'}
        }
        payment = _make_payment()
        request = rf.get('/')
        result = payment.prepare_transaction(request=request)
        assert result.status_code == 302
        assert payment.status == ps.PREPARED

    def test_get_method_returns_redirect(self, rf, settings):
        settings.GETPAID_BACKEND_SETTINGS = {
            'getpaid.backends.dummy': {'paywall_method': 'GET'}
        }
        payment = _make_payment()
        request = rf.get('/')
        result = payment.prepare_transaction(request=request)
        assert result.status_code == 302
        assert payment.status == ps.PREPARED

    def test_post_method_returns_template_response(self, rf, settings):
        settings.GETPAID_BACKEND_SETTINGS = {
            'getpaid.backends.dummy': {'paywall_method': 'POST'}
        }
        payment = _make_payment()
        request = rf.get('/')
        result = payment.prepare_transaction(request=request)
        assert result.status_code == 200
        assert payment.status == ps.PREPARED

    def test_prepare_works_without_request(self, settings):
        """prepare_transaction should work even without a request object."""
        settings.GETPAID_BACKEND_SETTINGS = {
            'getpaid.backends.dummy': {'paywall_method': 'REST'}
        }
        payment = _make_payment()
        result = payment.prepare_transaction(request=None)
        assert result.status_code == 302
        assert payment.status == ps.PREPARED


class TestDummyHandleCallback:
    """Test handle_paywall_callback with various statuses."""

    def test_callback_paid(self, rf):
        payment = _make_payment()
        payment.confirm_prepared()
        payment.save()

        request = rf.post(
            '', content_type='application/json', data={'new_status': ps.PAID}
        )
        response = payment.handle_paywall_callback(request)
        assert response.status_code == 200
        assert payment.status == ps.PAID

    def test_callback_pre_auth(self, rf):
        payment = _make_payment()
        payment.confirm_prepared()
        payment.save()

        request = rf.post(
            '',
            content_type='application/json',
            data={'new_status': ps.PRE_AUTH},
        )
        response = payment.handle_paywall_callback(request)
        assert response.status_code == 200
        assert payment.status == ps.PRE_AUTH

    def test_callback_failed(self, rf):
        payment = _make_payment()
        payment.confirm_prepared()
        payment.save()

        request = rf.post(
            '',
            content_type='application/json',
            data={'new_status': ps.FAILED},
        )
        response = payment.handle_paywall_callback(request)
        assert response.status_code == 200
        assert payment.status == ps.FAILED

    def test_callback_no_status_returns_400(self, rf):
        """Missing new_status should return 400, not raise an exception."""
        payment = _make_payment()
        payment.confirm_prepared()
        payment.save()

        request = rf.post('', content_type='application/json', data={})
        response = payment.handle_paywall_callback(request)
        assert response.status_code == 400

    def test_callback_unknown_status_returns_400(self, rf):
        """Unknown status values should return 400."""
        payment = _make_payment()
        payment.confirm_prepared()
        payment.save()

        request = rf.post(
            '',
            content_type='application/json',
            data={'new_status': 'nonsense'},
        )
        response = payment.handle_paywall_callback(request)
        assert response.status_code == 400


class TestDummyFetchPaymentStatus:
    """Test fetch_payment_status returns correct callback names."""

    def test_new_payment_no_callback(self):
        """A NEW payment should not suggest any callback."""
        payment = _make_payment()
        result = payment.processor.fetch_payment_status()
        assert result.get('callback') is None

    def test_prepared_payment_returns_confirm_payment(self):
        """A PREPARED payment in PULL mode returns 'confirm_payment'
        (simulating the provider saying 'payment received')."""
        payment = _make_payment()
        payment.confirm_prepared()
        payment.save()
        result = payment.processor.fetch_payment_status()
        assert result.get('callback') == 'confirm_payment'
        assert result.get('amount') == payment.amount_required

    def test_terminal_paid_returns_no_callback(self):
        """A PAID payment should not return any callback."""
        payment = _make_payment()
        payment.confirm_prepared()
        full = payment.amount_required
        payment.confirm_payment(amount=full)
        payment.mark_as_paid()
        payment.save()
        result = payment.processor.fetch_payment_status()
        assert result == {}

    def test_terminal_failed_returns_no_callback(self):
        """A FAILED payment should not return any callback."""
        payment = _make_payment()
        payment.confirm_prepared()
        payment.fail()
        payment.save()
        result = payment.processor.fetch_payment_status()
        assert result == {}

    def test_confirmation_status_failed(self, settings):
        """confirmation_status='failed' should return 'fail' callback."""
        settings.GETPAID_BACKEND_SETTINGS = {
            'getpaid.backends.dummy': {'confirmation_status': 'failed'}
        }
        payment = _make_payment()
        payment.confirm_prepared()
        payment.save()
        result = payment.processor.fetch_payment_status()
        assert result.get('callback') == 'fail'

    def test_confirmation_status_pre_auth(self, settings):
        """confirmation_status='pre_auth' should return 'confirm_lock' callback."""
        settings.GETPAID_BACKEND_SETTINGS = {
            'getpaid.backends.dummy': {'confirmation_status': 'pre_auth'}
        }
        payment = _make_payment()
        payment.confirm_prepared()
        payment.save()
        result = payment.processor.fetch_payment_status()
        assert result.get('callback') == 'confirm_lock'


class TestDummyCharge:
    """Test that charge() returns a proper ChargeResponse dict."""

    def test_charge_returns_dict_with_amount(self):
        payment = _make_payment()
        payment.confirm_lock(amount=Decimal('100.00'))
        payment.save()

        result = payment.processor.charge(amount=Decimal('50.00'))
        assert isinstance(result, dict)
        assert result['amount_charged'] == Decimal('50.00')
        assert result['success'] is True

    def test_charge_uses_locked_amount_when_none(self):
        payment = _make_payment()
        payment.confirm_lock(amount=Decimal('100.00'))
        payment.save()

        result = payment.processor.charge(amount=None)
        assert result['amount_charged'] == Decimal('100.00')

    def test_charge_returns_dict_not_none(self):
        """charge() must return a dict, never None (old bug)."""
        payment = _make_payment()
        payment.confirm_lock(amount=Decimal('100.00'))
        payment.save()

        result = payment.processor.charge(amount=Decimal('100.00'))
        assert result is not None


class TestDummyReleaseLock:
    """Test that release_lock() returns the released amount."""

    def test_release_lock_returns_decimal(self):
        payment = _make_payment()
        payment.confirm_lock(amount=Decimal('100.00'))
        payment.save()

        result = payment.processor.release_lock()
        assert isinstance(result, Decimal)
        assert result == Decimal('100.00')


class TestDummyStartRefund:
    """Test that start_refund() returns the refund amount."""

    def test_start_refund_returns_amount(self):
        payment = _make_payment()
        full = payment.amount_required
        payment.confirm_lock(amount=full)
        payment.confirm_payment(amount=full)
        payment.mark_as_paid()
        payment.save()

        result = payment.processor.start_refund(amount=Decimal('50.00'))
        assert isinstance(result, Decimal)
        assert result == Decimal('50.00')

    def test_start_refund_defaults_to_paid_amount(self):
        payment = _make_payment()
        full = payment.amount_required
        payment.confirm_lock(amount=full)
        payment.confirm_payment(amount=full)
        payment.mark_as_paid()
        payment.save()

        result = payment.processor.start_refund()
        assert result == full


class TestDummyCancelRefund:
    """Test that cancel_refund() returns a bool."""

    def test_cancel_refund_returns_true(self):
        payment = _make_payment()
        result = payment.processor.cancel_refund()
        assert result is True
