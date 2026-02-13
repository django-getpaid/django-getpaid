"""Tests for the dummy payment backend (rewritten from scratch)."""

import pathlib
from decimal import Decimal

import pytest
import swapper
from getpaid_core.fsm import create_payment_machine

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
        import importlib

        mod = importlib.import_module('getpaid.backends.dummy.processor')
        source = pathlib.Path(mod.__file__).open().read()
        assert 'import requests' not in source


class TestDummyPrepareTransaction:
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
        settings.GETPAID_BACKEND_SETTINGS = {
            'getpaid.backends.dummy': {'paywall_method': 'REST'}
        }
        payment = _make_payment()
        result = payment.prepare_transaction(request=None)
        assert result.status_code == 302
        assert payment.status == ps.PREPARED


class TestDummyHandleCallback:
    def test_callback_paid(self, rf):
        payment = _make_payment()
        create_payment_machine(payment)
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
        create_payment_machine(payment)
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
        create_payment_machine(payment)
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
        payment = _make_payment()
        create_payment_machine(payment)
        payment.confirm_prepared()
        payment.save()

        request = rf.post('', content_type='application/json', data={})
        response = payment.handle_paywall_callback(request)
        assert response.status_code == 400

    def test_callback_unknown_status_returns_400(self, rf):
        payment = _make_payment()
        create_payment_machine(payment)
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
    def test_new_payment_no_callback(self):
        payment = _make_payment()
        proc = payment._get_processor()
        result = proc.fetch_payment_status()
        assert result.get('callback') is None

    def test_prepared_payment_returns_confirm_payment(self):
        payment = _make_payment()
        create_payment_machine(payment)
        payment.confirm_prepared()
        payment.save()
        proc = payment._get_processor()
        result = proc.fetch_payment_status()
        assert result.get('callback') == 'confirm_payment'
        assert result.get('amount') == payment.amount_required

    def test_terminal_paid_returns_no_callback(self):
        payment = _make_payment()
        create_payment_machine(payment)
        payment.confirm_prepared()
        full = payment.amount_required
        payment.confirm_payment(amount=full)
        payment.amount_paid = full
        payment.mark_as_paid()
        payment.save()
        proc = payment._get_processor()
        result = proc.fetch_payment_status()
        assert result == {}

    def test_terminal_failed_returns_no_callback(self):
        payment = _make_payment()
        create_payment_machine(payment)
        payment.confirm_prepared()
        payment.fail()
        payment.save()
        proc = payment._get_processor()
        result = proc.fetch_payment_status()
        assert result == {}

    def test_confirmation_status_failed(self, settings):
        settings.GETPAID_BACKEND_SETTINGS = {
            'getpaid.backends.dummy': {'confirmation_status': 'failed'}
        }
        payment = _make_payment()
        create_payment_machine(payment)
        payment.confirm_prepared()
        payment.save()
        proc = payment._get_processor()
        result = proc.fetch_payment_status()
        assert result.get('callback') == 'fail'

    def test_confirmation_status_pre_auth(self, settings):
        settings.GETPAID_BACKEND_SETTINGS = {
            'getpaid.backends.dummy': {'confirmation_status': 'pre_auth'}
        }
        payment = _make_payment()
        create_payment_machine(payment)
        payment.confirm_prepared()
        payment.save()
        proc = payment._get_processor()
        result = proc.fetch_payment_status()
        assert result.get('callback') == 'confirm_lock'


class TestDummyCharge:
    def test_charge_returns_dict_with_amount(self):
        payment = _make_payment()
        create_payment_machine(payment)
        payment.confirm_lock(amount=Decimal('100.00'))
        payment.save()

        proc = payment._get_processor()
        result = proc.charge(amount=Decimal('50.00'))
        assert isinstance(result, dict)
        assert result['amount_charged'] == Decimal('50.00')
        assert result['success'] is True

    def test_charge_uses_locked_amount_when_none(self):
        payment = _make_payment()
        create_payment_machine(payment)
        payment.confirm_lock(amount=Decimal('100.00'))
        payment.save()

        proc = payment._get_processor()
        result = proc.charge(amount=None)
        assert result['amount_charged'] == Decimal('100.00')

    def test_charge_returns_dict_not_none(self):
        payment = _make_payment()
        create_payment_machine(payment)
        payment.confirm_lock(amount=Decimal('100.00'))
        payment.save()

        proc = payment._get_processor()
        result = proc.charge(amount=Decimal('100.00'))
        assert result is not None


class TestDummyReleaseLock:
    def test_release_lock_returns_decimal(self):
        payment = _make_payment()
        create_payment_machine(payment)
        payment.confirm_lock(amount=Decimal('100.00'))
        payment.save()

        proc = payment._get_processor()
        result = proc.release_lock()
        assert isinstance(result, Decimal)
        assert result == Decimal('100.00')


class TestDummyStartRefund:
    def test_start_refund_returns_amount(self):
        payment = _make_payment()
        create_payment_machine(payment)
        full = payment.amount_required
        payment.confirm_lock(amount=full)
        payment.confirm_payment(amount=full)
        payment.amount_paid = full
        payment.mark_as_paid()
        payment.save()

        proc = payment._get_processor()
        result = proc.start_refund(amount=Decimal('50.00'))
        assert isinstance(result, Decimal)
        assert result == Decimal('50.00')

    def test_start_refund_defaults_to_paid_amount(self):
        payment = _make_payment()
        create_payment_machine(payment)
        full = payment.amount_required
        payment.confirm_lock(amount=full)
        payment.confirm_payment(amount=full)
        payment.amount_paid = full
        payment.mark_as_paid()
        payment.save()

        proc = payment._get_processor()
        result = proc.start_refund()
        assert result == full


class TestDummyCancelRefund:
    def test_cancel_refund_returns_true(self):
        payment = _make_payment()
        proc = payment._get_processor()
        result = proc.cancel_refund()
        assert result is True
