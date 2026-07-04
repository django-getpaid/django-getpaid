"""Tests for PaymentAdmin actions: error reporting and status filters."""

import logging
from unittest.mock import patch

import pytest
import swapper
from django.contrib import admin as django_admin
from django.contrib import messages
from django.test import RequestFactory

from getpaid.admin import PaymentAdmin
from getpaid.types import PaymentStatus as ps

pytestmark = pytest.mark.django_db

Payment = swapper.load_model('getpaid', 'Payment')


class RecordingAdmin(PaymentAdmin):
    """PaymentAdmin that records message_user calls."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.recorded_messages = []

    def message_user(
        self, request, message, level=messages.INFO, **kwargs
    ):
        self.recorded_messages.append((level, str(message)))


@pytest.fixture
def payment_admin():
    return RecordingAdmin(Payment, django_admin.AdminSite())


@pytest.fixture
def request_(rf: RequestFactory):
    return rf.post('/admin/')


def _messages_at(admin_obj, level):
    return [m for lvl, m in admin_obj.recorded_messages if lvl == level]


class TestChargePayment:
    def test_reports_success_and_failure_counts(
        self, payment_admin, request_, payment_factory, caplog
    ):
        payment_factory(status=ps.PRE_AUTH)
        bad = payment_factory(status=ps.PRE_AUTH)

        original_charge = Payment.charge

        def flaky_charge(self, *args, **kwargs):
            if self.pk == bad.pk:
                raise RuntimeError('gateway exploded')
            return original_charge(self, *args, **kwargs)

        with (
            patch.object(Payment, 'charge', flaky_charge),
            caplog.at_level(logging.ERROR, logger='getpaid.admin'),
        ):
            payment_admin.charge_payment(
                request_, Payment.objects.all()
            )

        success_messages = _messages_at(payment_admin, messages.SUCCESS)
        error_messages = _messages_at(payment_admin, messages.ERROR)
        assert any('1' in m for m in success_messages)
        assert any('1' in m for m in error_messages)
        assert any(
            'gateway exploded' in record.exc_text
            for record in caplog.records
            if record.exc_text
        )

    def test_ignores_payments_not_in_pre_auth(
        self, payment_admin, request_, payment_factory
    ):
        payment_factory(status=ps.NEW)

        with patch.object(Payment, 'charge') as mock_charge:
            payment_admin.charge_payment(request_, Payment.objects.all())

        mock_charge.assert_not_called()
        assert _messages_at(payment_admin, messages.ERROR) == []

    def test_uses_enum_not_hardcoded_string(self):
        import inspect

        from getpaid import admin as admin_module

        source = inspect.getsource(admin_module)
        assert "'pre-auth'" not in source
        assert "'paid'" not in source


class TestReleaseLock:
    def test_reports_failure_via_messages_error(
        self, payment_admin, request_, payment_factory
    ):
        payment_factory(status=ps.PRE_AUTH)

        with patch.object(
            Payment,
            'release_lock',
            side_effect=RuntimeError('boom'),
        ):
            payment_admin.release_lock_action(
                request_, Payment.objects.all()
            )

        assert _messages_at(payment_admin, messages.ERROR)
        assert not _messages_at(payment_admin, messages.SUCCESS)


class TestStartRefund:
    def test_reports_success(
        self, payment_admin, request_, payment_factory
    ):
        payment_factory(status=ps.PAID)

        with patch.object(Payment, 'start_refund'):
            payment_admin.start_refund(request_, Payment.objects.all())

        assert _messages_at(payment_admin, messages.SUCCESS)
        assert not _messages_at(payment_admin, messages.ERROR)
