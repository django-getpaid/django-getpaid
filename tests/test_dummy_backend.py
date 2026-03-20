import json
from decimal import Decimal

import pytest
import swapper
from django.template.response import TemplateResponse

from getpaid.types import PaymentStatus as ps

pytestmark = pytest.mark.django_db

Order = swapper.load_model('getpaid', 'Order')
Payment = swapper.load_model('getpaid', 'Payment')


def _make_payment(**kwargs):
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


class TestDummyPrepareTransaction:
    def test_rest_method_returns_redirect(self, rf, settings):
        settings.GETPAID_BACKEND_SETTINGS = {
            'getpaid.backends.dummy': {'paywall_method': 'REST'}
        }
        payment = _make_payment()
        result = payment.prepare_transaction(request=rf.get('/'))

        assert result.status_code == 302
        assert payment.status == ps.PREPARED

    def test_get_method_returns_redirect(self, rf, settings):
        settings.GETPAID_BACKEND_SETTINGS = {
            'getpaid.backends.dummy': {'paywall_method': 'GET'}
        }
        payment = _make_payment()
        result = payment.prepare_transaction(request=rf.get('/'))

        assert result.status_code == 302
        assert payment.status == ps.PREPARED

    def test_post_method_returns_template_response(self, rf, settings):
        settings.GETPAID_BACKEND_SETTINGS = {
            'getpaid.backends.dummy': {'paywall_method': 'POST'}
        }
        payment = _make_payment()
        result = payment.prepare_transaction(request=rf.get('/'))

        assert isinstance(result, TemplateResponse)
        assert result.status_code == 200
        assert payment.status == ps.PREPARED


class TestDummyCallbacks:
    def test_paid_callback_marks_payment_paid(self, rf):
        payment = _make_payment(status=ps.PREPARED)
        request = rf.post(
            '',
            data=json.dumps({'new_status': ps.PAID}),
            content_type='application/json',
        )

        response = payment.handle_paywall_callback(request)

        payment.refresh_from_db()
        assert response.status_code == 200
        assert payment.status == ps.PAID
        assert payment.amount_paid == payment.amount_required

    def test_preauth_callback_marks_payment_locked(self, rf):
        payment = _make_payment(status=ps.PREPARED)
        request = rf.post(
            '',
            data=json.dumps({'new_status': ps.PRE_AUTH}),
            content_type='application/json',
        )

        response = payment.handle_paywall_callback(request)

        payment.refresh_from_db()
        assert response.status_code == 200
        assert payment.status == ps.PRE_AUTH
        assert payment.amount_locked == payment.amount_required

    def test_failed_callback_marks_payment_failed(self, rf):
        payment = _make_payment(status=ps.PREPARED)
        request = rf.post(
            '',
            data=json.dumps({'new_status': ps.FAILED}),
            content_type='application/json',
        )

        response = payment.handle_paywall_callback(request)

        payment.refresh_from_db()
        assert response.status_code == 200
        assert payment.status == ps.FAILED

    def test_missing_status_returns_400(self, rf):
        payment = _make_payment(status=ps.PREPARED)
        request = rf.post(
            '', data=json.dumps({}), content_type='application/json'
        )

        response = payment.handle_paywall_callback(request)

        assert response.status_code == 400


class TestDummyPullAndActions:
    def test_fetch_and_update_status_marks_paid(self, settings):
        settings.GETPAID_BACKEND_SETTINGS = {
            'getpaid.backends.dummy': {'confirmation_status': 'paid'}
        }
        payment = _make_payment(status=ps.PREPARED)

        result = payment.fetch_and_update_status()

        assert result.status == ps.PAID
        assert result.amount_paid == result.amount_required

    def test_fetch_and_update_status_marks_preauth(self, settings):
        settings.GETPAID_BACKEND_SETTINGS = {
            'getpaid.backends.dummy': {'confirmation_status': 'pre_auth'}
        }
        payment = _make_payment(status=ps.PREPARED)

        result = payment.fetch_and_update_status()

        assert result.status == ps.PRE_AUTH
        assert result.amount_locked == result.amount_required

    def test_charge_updates_paid_amount(self):
        payment = _make_payment(
            status=ps.PRE_AUTH,
            amount_locked=Decimal('100.00'),
        )

        result = payment.charge(amount=Decimal('50.00'))

        payment.refresh_from_db()
        assert result.success is True
        assert payment.amount_paid == Decimal('50.00')
        assert payment.amount_locked == Decimal('50.00')
        assert payment.status == ps.PARTIAL

    def test_release_lock_updates_status(self):
        payment = _make_payment(
            status=ps.PRE_AUTH,
            amount_locked=Decimal('100.00'),
        )

        result = payment.release_lock()

        payment.refresh_from_db()
        assert result == Decimal('100.00')
        assert payment.amount_locked == Decimal('0.00')
        assert payment.status == ps.REFUNDED

    def test_start_refund_stores_provider_data(self):
        payment = _make_payment(
            status=ps.PAID,
            amount_paid=Decimal('100.00'),
        )

        result = payment.start_refund(amount=Decimal('50.00'))

        payment.refresh_from_db()
        assert result.amount == Decimal('50.00')
        assert payment.status == ps.REFUND_STARTED
        assert payment.provider_data['refund_id'].startswith('dummy-refund-')

    def test_cancel_refund_restores_paid_state(self):
        payment = _make_payment(
            status=ps.REFUND_STARTED,
            amount_paid=Decimal('100.00'),
            amount_required=Decimal('100.00'),
            provider_data={'refund_id': 'dummy-refund-1'},
        )

        result = payment.cancel_refund()

        payment.refresh_from_db()
        assert result is True
        assert payment.status == ps.PAID
