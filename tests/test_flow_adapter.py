"""Tests for DjangoPaymentFlowAdapter and prepare_transaction."""

from collections import OrderedDict
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest
import swapper
from django import forms
from django.http import HttpResponseRedirect
from getpaid_core.exceptions import GetPaidException

from getpaid.flow_adapter import DjangoPaymentFlowAdapter, prepare_transaction
from getpaid.status import PaymentStatus as ps

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


class TestAdapterCharge:
    def test_charge_full_amount(self):
        payment = _make_payment(
            status=ps.PRE_AUTH,
            amount_locked=Decimal('100.00'),
        )
        adapter = DjangoPaymentFlowAdapter(payment, Payment)
        adapter.charge(amount=Decimal('100.00'))
        payment.refresh_from_db()
        assert payment.amount_paid == Decimal('100.00')
        assert payment.amount_locked == Decimal('0.00')

    def test_charge_partial_amount(self):
        payment = _make_payment(
            status=ps.PRE_AUTH,
            amount_locked=Decimal('100.00'),
        )
        adapter = DjangoPaymentFlowAdapter(payment, Payment)
        adapter.charge(amount=Decimal('50.00'))
        payment.refresh_from_db()
        assert payment.amount_paid == Decimal('50.00')
        assert payment.amount_locked == Decimal('50.00')
        assert payment.status == ps.PARTIAL

    def test_charge_rejects_invalid_status(self):
        payment = _make_payment(status=ps.NEW)
        adapter = DjangoPaymentFlowAdapter(payment, Payment)
        with pytest.raises(GetPaidException):
            adapter.charge(amount=Decimal('100.00'))


class TestAdapterFetchStatus:
    def test_fetch_status_paid(self, settings):
        settings.GETPAID_BACKEND_SETTINGS = {
            'getpaid.backends.dummy': {'confirmation_status': 'paid'}
        }
        payment = _make_payment(status=ps.PREPARED)
        adapter = DjangoPaymentFlowAdapter(payment, Payment)
        adapter.fetch_status()
        payment.refresh_from_db()
        assert payment.status == ps.PAID

    def test_fetch_status_pre_auth(self, settings):
        settings.GETPAID_BACKEND_SETTINGS = {
            'getpaid.backends.dummy': {'confirmation_status': 'pre_auth'}
        }
        payment = _make_payment(status=ps.PREPARED)
        adapter = DjangoPaymentFlowAdapter(payment, Payment)
        adapter.fetch_status()
        payment.refresh_from_db()
        assert payment.status == ps.PRE_AUTH


class TestAdapterPrepare:
    def test_prepare_sets_status(self):
        payment = _make_payment()
        adapter = DjangoPaymentFlowAdapter(payment, Payment)
        result = adapter.prepare()
        payment.refresh_from_db()
        assert payment.status == ps.PREPARED
        assert result.redirect_url is not None


class TestAdapterRefunds:
    def test_start_refund(self):
        payment = _make_payment(
            status=ps.PAID,
            amount_paid=Decimal('100.00'),
        )
        adapter = DjangoPaymentFlowAdapter(payment, Payment)
        adapter.start_refund(amount=Decimal('30.00'))
        payment.refresh_from_db()
        assert payment.status == ps.REFUND_STARTED

    def test_cancel_refund(self):
        payment = _make_payment(
            status=ps.REFUND_STARTED,
            amount_paid=Decimal('100.00'),
            amount_required=Decimal('100.00'),
        )
        adapter = DjangoPaymentFlowAdapter(payment, Payment)
        adapter.cancel_refund()
        payment.refresh_from_db()
        assert payment.status == ps.PAID

    def test_start_refund_rejects_invalid_status(self):
        payment = _make_payment(status=ps.NEW)
        adapter = DjangoPaymentFlowAdapter(payment, Payment)
        with pytest.raises(GetPaidException):
            adapter.start_refund(amount=Decimal('10.00'))


class TestAdapterReleaseLock:
    def test_release_lock(self):
        payment = _make_payment(
            status=ps.PRE_AUTH,
            amount_locked=Decimal('100.00'),
        )
        adapter = DjangoPaymentFlowAdapter(payment, Payment)
        adapter.release_lock()
        payment.refresh_from_db()
        assert payment.amount_locked == Decimal('0.00')
        assert payment.status == ps.REFUNDED

    def test_release_lock_rejects_invalid_status(self):
        payment = _make_payment(status=ps.NEW)
        adapter = DjangoPaymentFlowAdapter(payment, Payment)
        with pytest.raises(GetPaidException):
            adapter.release_lock()


class TestPrepareTransaction:
    def test_prepare_transaction_passes_view_to_processor(self):
        payment = _make_payment()
        mock_view = MagicMock()
        mock_request = MagicMock()

        with patch(
            'getpaid.flow_adapter.DjangoPaymentFlowAdapter.prepare',
            return_value=MagicMock(
                method='GET',
                redirect_url='https://example.com/pay',
                form_data=None,
            ),
        ) as mock_prep:
            result = prepare_transaction(
                payment, request=mock_request, view=mock_view
            )
            mock_prep.assert_called_once()
            assert isinstance(result, HttpResponseRedirect)

    def test_prepare_transaction_for_rest_iterates_form_fields(self):
        payment = _make_payment()

        mock_form = MagicMock()
        mock_form.fields = OrderedDict(
            [
                ('amount', forms.DecimalField(initial='100.00', label='Amount')),
                ('currency', forms.CharField(initial='EUR', label='Currency')),
            ]
        )

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.context_data = {
            'paywall_url': 'https://example.com/pay',
            'form': mock_form,
        }

        with patch.object(
            type(payment),
            'prepare_transaction',
            return_value=mock_response,
        ):
            result = payment.prepare_transaction_for_rest()

        assert result['status_code'] == 200
        assert result['target_url'] == 'https://example.com/pay'
        assert len(result['form']['fields']) == 2
        assert result['form']['fields'][0]['name'] == 'amount'
        assert result['form']['fields'][1]['name'] == 'currency'
