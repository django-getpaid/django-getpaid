"""Tests for AbstractPayment methods (via concrete CustomPayment model)."""

import logging
from collections import OrderedDict
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest
import swapper
from django import forms

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


class TestPrepareTransaction:
    """Tests for prepare_transaction and prepare_transaction_for_rest."""

    def test_prepare_transaction_passes_view_to_processor(self):
        """Bug: view=None hardcoded at abstracts.py:364 instead of view=view.
        The view parameter should be forwarded to the processor."""
        payment = _make_payment()
        mock_view = MagicMock()
        mock_request = MagicMock()

        with patch.object(
            type(payment.processor),
            'prepare_transaction',
            return_value=MagicMock(status_code=302, url='/redirect'),
        ) as mock_prep:
            payment.prepare_transaction(request=mock_request, view=mock_view)
            mock_prep.assert_called_once_with(
                request=mock_request, view=mock_view
            )

    def test_prepare_transaction_for_rest_iterates_form_fields(self):
        """Bug: .fields should be .fields.items() at abstracts.py:391.
        Iterating a Django form's .fields dict yields only keys (strings),
        not (name, field) tuples, causing a ValueError."""
        payment = _make_payment()

        # Build a mock response that mimics a 200 TemplateResponse with form
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


class TestChargeDoubleCount:
    """Tests for the charge() method and its interaction with confirm_payment()."""

    def test_charge_does_not_double_count_amount_paid(self):
        """Bug: charge() sets self.amount_paid then calls confirm_payment()
        which does self.amount_paid += amount, resulting in double-counting."""
        payment = _make_payment()
        payment.confirm_lock(amount=Decimal('100.00'))
        payment.save()

        with patch.object(
            type(payment.processor),
            'charge',
            return_value={
                'amount_charged': Decimal('100.00'),
                'success': True,
            },
        ):
            payment.charge(amount=Decimal('100.00'))

        # charge() calls save() internally, check in-memory values
        # (refresh_from_db doesn't work with protected FSM fields)
        # Should be exactly 100.00, not 200.00 (double-counted)
        assert payment.amount_paid == Decimal('100.00')

    def test_charge_partial_amount(self):
        """Charging a partial amount should correctly update amount_paid."""
        payment = _make_payment()
        payment.confirm_lock(amount=Decimal('100.00'))
        payment.save()

        with patch.object(
            type(payment.processor),
            'charge',
            return_value={
                'amount_charged': Decimal('50.00'),
                'success': True,
            },
        ):
            payment.charge(amount=Decimal('50.00'))

        assert payment.amount_paid == Decimal('50.00')
        assert payment.amount_locked == Decimal('50.00')


class TestFetchAndUpdateStatusAllowlist:
    """Tests for the FSM callback allowlist in fetch_and_update_status()."""

    def test_payment_has_allowed_callbacks(self):
        """AbstractPayment should define ALLOWED_CALLBACKS set."""
        from getpaid.abstracts import AbstractPayment

        assert hasattr(AbstractPayment, 'ALLOWED_CALLBACKS')
        assert isinstance(AbstractPayment.ALLOWED_CALLBACKS, frozenset)

    def test_allowed_callbacks_contains_known_methods(self):
        """ALLOWED_CALLBACKS should contain all known FSM transition method names."""
        from getpaid.abstracts import AbstractPayment

        expected = {
            'confirm_prepared',
            'confirm_lock',
            'confirm_charge_sent',
            'confirm_payment',
            'mark_as_paid',
            'fail',
            'confirm_refund',
            'mark_as_refunded',
        }
        assert expected.issubset(AbstractPayment.ALLOWED_CALLBACKS)

    def test_fetch_and_update_rejects_disallowed_callback(self):
        """fetch_and_update_status() should reject callback names not in allowlist."""
        payment = _make_payment()

        # Prepare status so fetch_status returns a disallowed callback name
        with patch.object(
            type(payment),
            'fetch_status',
            return_value={'callback': 'delete', 'amount': Decimal('100.00')},
        ):
            result = payment.fetch_and_update_status()

        # Should NOT have a 'callback_result' because the callback was blocked
        assert 'callback_result' not in result
        # Should have recorded the rejection
        assert 'exception' in result

    def test_fetch_and_update_accepts_allowed_callback(self):
        """fetch_and_update_status() should accept callback names in the allowlist."""
        payment = _make_payment()
        # Put payment in PREPARED state for confirm_lock to work
        payment.confirm_prepared()
        payment.save()

        with patch.object(
            type(payment),
            'fetch_status',
            return_value={
                'callback': 'confirm_lock',
                'amount': Decimal('100.00'),
            },
        ):
            result = payment.fetch_and_update_status()

        assert 'callback_result' in result or 'saved' in result

    def test_fetch_and_update_logs_disallowed_callback(self, caplog):
        """fetch_and_update_status() should log a warning for disallowed callbacks."""
        payment = _make_payment()

        with caplog.at_level(logging.WARNING, logger='getpaid.abstracts'):
            with patch.object(
                type(payment),
                'fetch_status',
                return_value={
                    'callback': 'save',
                    'amount': Decimal('100.00'),
                },
            ):
                payment.fetch_and_update_status()

        assert any(
            'Disallowed callback' in record.message for record in caplog.records
        )


class TestFraudMethodNames:
    """Tests that fraud methods are accessible with public names (no name mangling)."""

    def test_payment_has_flag_as_fraud(self):
        """Payment should have a flag_as_fraud() method (UNKNOWN -> REJECTED)."""
        payment = _make_payment()
        assert hasattr(payment, 'flag_as_fraud')
        assert callable(payment.flag_as_fraud)

    def test_payment_has_flag_as_legit(self):
        """Payment should have a flag_as_legit() method (UNKNOWN -> ACCEPTED)."""
        payment = _make_payment()
        assert hasattr(payment, 'flag_as_legit')
        assert callable(payment.flag_as_legit)

    def test_payment_has_flag_for_check(self):
        """Payment should have a flag_for_check() method (UNKNOWN -> CHECK)."""
        payment = _make_payment()
        assert hasattr(payment, 'flag_for_check')
        assert callable(payment.flag_for_check)

    def test_flag_as_fraud_transitions_from_unknown(self):
        """flag_as_fraud should transition fraud_status from UNKNOWN to REJECTED."""
        from getpaid.types import FraudStatus as fs

        payment = _make_payment()
        assert payment.fraud_status == fs.UNKNOWN
        payment.flag_as_fraud(message='Suspicious IP')
        payment.save()
        assert payment.fraud_status == fs.REJECTED
        assert payment.fraud_message == 'Suspicious IP'

    def test_flag_as_legit_transitions_from_unknown(self):
        """flag_as_legit should transition fraud_status from UNKNOWN to ACCEPTED."""
        from getpaid.types import FraudStatus as fs

        payment = _make_payment()
        assert payment.fraud_status == fs.UNKNOWN
        payment.flag_as_legit(message='Verified buyer')
        payment.save()
        assert payment.fraud_status == fs.ACCEPTED
        assert payment.fraud_message == 'Verified buyer'

    def test_flag_for_check_transitions_from_unknown(self):
        """flag_for_check should transition fraud_status from UNKNOWN to CHECK."""
        from getpaid.types import FraudStatus as fs

        payment = _make_payment()
        assert payment.fraud_status == fs.UNKNOWN
        payment.flag_for_check(message='Needs review')
        payment.save()
        assert payment.fraud_status == fs.CHECK
        assert payment.fraud_message == 'Needs review'

    def test_no_triple_underscore_methods(self):
        """Triple-underscore methods should NOT exist (name mangling makes them useless)."""
        payment = _make_payment()
        # Python name mangling turns ___x into _ClassName__x (double underscore)
        # so ___mark_as_fraud is actually inaccessible with its declared name
        assert not hasattr(payment, '___mark_as_fraud')
        assert not hasattr(payment, '___mark_as_legit')
        assert not hasattr(payment, '___mark_for_check')


class TestAmountRefundedPrecision:
    """Tests that amount_refunded has consistent decimal precision with other money fields."""

    def test_amount_refunded_has_2_decimal_places(self):
        """amount_refunded should have decimal_places=2, same as other money fields."""
        field = Payment._meta.get_field('amount_refunded')
        assert field.decimal_places == 2

    def test_all_money_fields_same_precision(self):
        """All money fields should have the same decimal precision."""
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
        # All should be the same
        unique_precisions = set(precisions.values())
        assert len(unique_precisions) == 1, (
            f'Inconsistent decimal places across money fields: {precisions}'
        )


class TestFieldVerboseNames:
    """Tests that model field verbose_names are correct (not copy-pasted)."""

    def test_amount_locked_verbose_name(self):
        """amount_locked verbose_name should say 'amount locked', not 'amount paid'."""
        field = Payment._meta.get_field('amount_locked')
        verbose = str(field.verbose_name).lower()
        assert 'locked' in verbose, (
            f'amount_locked verbose_name is {field.verbose_name!r}, '
            f'expected to contain "locked"'
        )

    def test_amount_paid_verbose_name(self):
        """amount_paid verbose_name should contain 'paid'."""
        field = Payment._meta.get_field('amount_paid')
        verbose = str(field.verbose_name).lower()
        assert 'paid' in verbose

    def test_no_duplicate_verbose_names_on_money_fields(self):
        """Each money field should have a unique verbose_name."""
        money_fields = [
            'amount_required',
            'amount_locked',
            'amount_paid',
            'amount_refunded',
        ]
        names = {}
        for name in money_fields:
            field = Payment._meta.get_field(name)
            verbose = str(field.verbose_name)
            names[name] = verbose
        # All verbose names should be unique
        unique_names = set(names.values())
        assert len(unique_names) == len(money_fields), (
            f'Duplicate verbose_names on money fields: {names}'
        )


class TestValidatorOrdering:
    """Tests for validators.py — deterministic ordering and error handling."""

    def test_validators_run_in_deterministic_order(self, settings):
        """Validators should run in a deterministic order (not randomized by set())."""
        from getpaid.validators import run_getpaid_validators

        call_order = []

        def make_validator(name):
            def validator(data):
                call_order.append(name)
                return data

            return validator

        # Monkey-patch importable validators
        import types

        fake_module = types.ModuleType('fake_validators')
        fake_module.v1 = make_validator('v1')
        fake_module.v2 = make_validator('v2')
        fake_module.v3 = make_validator('v3')

        import sys

        sys.modules['fake_validators'] = fake_module

        try:
            settings.GETPAID = {
                'VALIDATORS': [
                    'fake_validators.v1',
                    'fake_validators.v2',
                ],
                'BACKENDS': {
                    'test_backend': {
                        'VALIDATORS': [
                            'fake_validators.v3',
                        ],
                    },
                },
            }

            data = {'backend': 'test_backend'}
            # Run multiple times to verify deterministic ordering
            for _ in range(5):
                call_order.clear()
                run_getpaid_validators(data)
                # The exact order may vary but must be consistent across runs
                if _ == 0:
                    first_order = call_order.copy()
                else:
                    assert call_order == first_order, (
                        f'Validator order changed between runs: '
                        f'{first_order} vs {call_order}'
                    )
        finally:
            del sys.modules['fake_validators']

    def test_validators_no_duplicates(self, settings):
        """Each validator should run exactly once, not duplicated."""
        from getpaid.validators import run_getpaid_validators

        call_count = {'v1': 0}

        def counting_validator(data):
            call_count['v1'] += 1
            return data

        import types
        import sys

        fake_module = types.ModuleType('fake_validators2')
        fake_module.v1 = counting_validator
        sys.modules['fake_validators2'] = fake_module

        try:
            # Same validator in both global and backend lists
            settings.GETPAID = {
                'VALIDATORS': ['fake_validators2.v1'],
                'BACKENDS': {
                    'test_backend': {
                        'VALIDATORS': ['fake_validators2.v1'],
                    },
                },
            }
            data = {'backend': 'test_backend'}
            run_getpaid_validators(data)
            # With set() union, duplicates are already removed, so this should be 1
            assert call_count['v1'] == 1
        finally:
            del sys.modules['fake_validators2']
