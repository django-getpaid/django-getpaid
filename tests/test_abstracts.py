from collections import OrderedDict
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest
import swapper
from django import forms
from django.http import HttpResponseRedirect

from getpaid.status import FraudStatus as fs
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


class TestPrepareTransaction:
    def test_prepare_transaction_passes_view_to_processor(self):
        payment = _make_payment()
        mock_view = MagicMock()
        mock_request = MagicMock()

        proc = payment._get_processor()
        with (
            patch.object(
                type(proc),
                'prepare_transaction',
                return_value=HttpResponseRedirect('/redirect'),
            ) as mock_prep,
            patch.object(type(payment), '_get_processor', return_value=proc),
        ):
            payment.prepare_transaction(request=mock_request, view=mock_view)
            mock_prep.assert_called_once_with(
                request=mock_request,
                view=mock_view,
            )

    def test_prepare_transaction_for_rest_iterates_form_fields(self):
        payment = _make_payment()

        mock_form = MagicMock()
        mock_form.fields = OrderedDict([
            ('amount', forms.DecimalField(initial='100.00', label='Amount')),
            ('currency', forms.CharField(initial='EUR', label='Currency')),
        ])

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


class TestChargeAndRefunds:
    def test_charge_does_not_double_count_amount_paid(self):
        payment = _make_payment(
            status=ps.PRE_AUTH,
            amount_locked=Decimal('100.00'),
        )

        payment.charge(amount=Decimal('100.00'))
        payment.refresh_from_db()

        assert payment.amount_paid == Decimal('100.00')
        assert payment.amount_locked == Decimal('0.00')

    def test_charge_partial_amount(self):
        payment = _make_payment(
            status=ps.PRE_AUTH,
            amount_locked=Decimal('100.00'),
        )

        payment.charge(amount=Decimal('50.00'))
        payment.refresh_from_db()

        assert payment.amount_paid == Decimal('50.00')
        assert payment.amount_locked == Decimal('50.00')
        assert payment.status == ps.PARTIAL

    def test_fetch_and_update_status_returns_payment_instance(self, settings):
        settings.GETPAID_BACKEND_SETTINGS = {
            'getpaid.backends.dummy': {'confirmation_status': 'paid'}
        }
        payment = _make_payment(status=ps.PREPARED)

        result = payment.fetch_and_update_status()

        assert result is payment
        assert payment.status == ps.PAID


class TestFraudMethodNames:
    def test_payment_has_flag_as_fraud(self):
        payment = _make_payment()
        assert hasattr(payment, 'flag_as_fraud')
        assert callable(payment.flag_as_fraud)

    def test_payment_has_flag_as_legit(self):
        payment = _make_payment()
        assert hasattr(payment, 'flag_as_legit')
        assert callable(payment.flag_as_legit)

    def test_payment_has_flag_for_check(self):
        payment = _make_payment()
        assert hasattr(payment, 'flag_for_check')
        assert callable(payment.flag_for_check)

    def test_flag_as_fraud_transitions_from_unknown(self):
        payment = _make_payment()
        assert payment.fraud_status == fs.UNKNOWN
        payment.flag_as_fraud(message='Suspicious IP')
        payment.save()
        assert payment.fraud_status == fs.REJECTED
        assert payment.fraud_message == 'Suspicious IP'

    def test_flag_as_legit_transitions_from_unknown(self):
        payment = _make_payment()
        assert payment.fraud_status == fs.UNKNOWN
        payment.flag_as_legit(message='Verified buyer')
        payment.save()
        assert payment.fraud_status == fs.ACCEPTED
        assert payment.fraud_message == 'Verified buyer'

    def test_flag_for_check_transitions_from_unknown(self):
        payment = _make_payment()
        assert payment.fraud_status == fs.UNKNOWN
        payment.flag_for_check(message='Needs review')
        payment.save()
        assert payment.fraud_status == fs.CHECK
        assert payment.fraud_message == 'Needs review'

    def test_no_triple_underscore_methods(self):
        payment = _make_payment()
        assert not hasattr(payment, '___mark_as_fraud')
        assert not hasattr(payment, '___mark_as_legit')
        assert not hasattr(payment, '___mark_for_check')


class TestAmountRefundedPrecision:
    def test_amount_refunded_has_2_decimal_places(self):
        field = Payment._meta.get_field('amount_refunded')
        assert field.decimal_places == 2

    def test_all_money_fields_same_precision(self):
        money_fields = [
            'amount_required',
            'amount_locked',
            'amount_paid',
            'amount_refunded',
        ]
        precisions = {}
        for name in money_fields:
            field = Payment._meta.get_field(name)
            precisions[name] = field.decimal_places
        unique_precisions = set(precisions.values())
        assert len(unique_precisions) == 1


class TestFieldVerboseNames:
    def test_amount_locked_verbose_name(self):
        field = Payment._meta.get_field('amount_locked')
        verbose = str(field.verbose_name).lower()
        assert 'locked' in verbose

    def test_amount_paid_verbose_name(self):
        field = Payment._meta.get_field('amount_paid')
        verbose = str(field.verbose_name).lower()
        assert 'paid' in verbose

    def test_provider_data_field_exists(self):
        field = Payment._meta.get_field('provider_data')
        assert field.default == dict

    def test_no_duplicate_verbose_names_on_money_fields(self):
        money_fields = [
            'amount_required',
            'amount_locked',
            'amount_paid',
            'amount_refunded',
        ]
        names = {}
        for name in money_fields:
            field = Payment._meta.get_field(name)
            names[name] = str(field.verbose_name)
        assert len(set(names.values())) == len(money_fields)


class TestValidatorOrdering:
    def test_validators_run_in_deterministic_order(self, settings):
        from getpaid.validators import run_getpaid_validators

        call_order = []

        def make_validator(name):
            def validator(data):
                call_order.append(name)
                return data

            return validator

        import sys
        import types

        fake_module = types.ModuleType('fake_validators')
        fake_module.v1 = make_validator('v1')
        fake_module.v2 = make_validator('v2')
        fake_module.v3 = make_validator('v3')
        sys.modules['fake_validators'] = fake_module

        try:
            settings.GETPAID = {
                'VALIDATORS': ['fake_validators.v1', 'fake_validators.v2'],
                'BACKENDS': {
                    'test_backend': {'VALIDATORS': ['fake_validators.v3']}
                },
            }

            data = {'backend': 'test_backend'}
            for index in range(5):
                call_order.clear()
                run_getpaid_validators(data)
                if index == 0:
                    first_order = call_order.copy()
                else:
                    assert call_order == first_order
        finally:
            del sys.modules['fake_validators']

    def test_validators_no_duplicates(self, settings):
        from getpaid.validators import run_getpaid_validators

        call_count = {'v1': 0}

        def counting_validator(data):
            call_count['v1'] += 1
            return data

        import sys
        import types

        fake_module = types.ModuleType('fake_validators2')
        fake_module.v1 = counting_validator
        sys.modules['fake_validators2'] = fake_module

        try:
            settings.GETPAID = {
                'VALIDATORS': ['fake_validators2.v1'],
                'BACKENDS': {
                    'test_backend': {'VALIDATORS': ['fake_validators2.v1']}
                },
            }
            run_getpaid_validators({'backend': 'test_backend'})
            assert call_count['v1'] == 1
        finally:
            del sys.modules['fake_validators2']
