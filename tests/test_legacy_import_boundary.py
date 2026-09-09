"""Normal Django imports must not require upcoming durable core modules."""

import os
import subprocess  # noqa: S404
import sys


def test_normal_model_and_legacy_imports_do_not_load_upcoming_core():
    script = """
import importlib.abc
import sys
class ForbidUpcoming(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname == "getpaid_core.recorded_money" or fullname.startswith("getpaid_core.durable"):
            raise AssertionError("Normal imports reached upcoming core")
sys.meta_path.insert(0, ForbidUpcoming())
import django
django.setup()
import getpaid.models
import getpaid.abstracts
import getpaid.flow_adapter
import getpaid.repository
"""
    result = subprocess.run(  # noqa: S603 — literal import probe, no external input
        [sys.executable, '-c', script],
        env={
            **os.environ,
            'DJANGO_SETTINGS_MODULE': 'tests.settings_default_payment',
        },
        text=True,
        capture_output=True,
        timeout=30,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_default_payment_model_records_money_in_isolated_memory_database():
    import pytest

    pytest.importorskip(
        'getpaid_core.recorded_money', reason='Requires upcoming core'
    )
    script = """
import django
django.setup()
from django.core.management import call_command
from django.db import connection
assert connection.vendor == "sqlite" and connection.settings_dict["NAME"] == ":memory:"
call_command("migrate", verbosity=0)
from datetime import datetime, UTC
from decimal import Decimal
from getpaid.models import Payment
from tests.default_order_app.models import Order
from getpaid.durable_repository import DjangoDurablePaymentRepository
from getpaid_core.recorded_money import RECORDED_MONEY_BACKEND, RecordedMoneyCommand, RecordedMoneyKind
payment = Payment.objects.create(order=Order.objects.create(), amount_required=Decimal(100), currency="EUR", backend=RECORDED_MONEY_BACKEND)
now = datetime(2026, 9, 10, tzinfo=UTC)
repository = DjangoDurablePaymentRepository()
plan = repository.record_money_sync(str(payment.pk), RecordedMoneyCommand("receipt", RecordedMoneyKind.RECEIPT, "actor", Decimal(40), now), now=now)
assert plan.facts.captured_funds == Decimal(40)
assert repository.get_recorded_money_history_sync(str(payment.pk)) == (plan.entry,)
"""
    env = {
        **os.environ,
        'DJANGO_SETTINGS_MODULE': 'tests.settings_default_payment',
    }
    env.pop('TEST_DATABASE_URL', None)
    result = subprocess.run(  # noqa: S603 — literal isolated database probe
        [sys.executable, '-c', script],
        env=env,
        text=True,
        capture_output=True,
        timeout=30,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
