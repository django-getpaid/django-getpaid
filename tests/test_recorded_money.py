"""Recorded-money storage: core semantics over complete, persisted evidence."""

from datetime import UTC, datetime
from decimal import Decimal

import pytest

pytest.importorskip(
    'getpaid_core.recorded_money', reason='Requires upcoming core'
)

from getpaid_core.enums import PaymentStatus
from getpaid_core.recorded_money import (
    RECORDED_MONEY_BACKEND,
    RecordedMoneyCommand,
    RecordedMoneyKind,
)

from getpaid.durable_repository import DjangoDurablePaymentRepository

pytestmark = pytest.mark.django_db(transaction=True)
NOW = datetime(2026, 9, 10, 12, tzinfo=UTC)


def receipt(identity='receipt', amount='40.00', **kwargs):
    return RecordedMoneyCommand(
        identity,
        RecordedMoneyKind.RECEIPT,
        'operator:1',
        Decimal(amount),
        NOW,
        **kwargs,
    )


@pytest.fixture
def recorded_root(payment_factory):
    payment = payment_factory(
        backend=RECORDED_MONEY_BACKEND,
        amount_required=Decimal('100.00'),
        status=PaymentStatus.NEW,
    )
    return payment, DjangoDurablePaymentRepository()


def test_first_partial_receipt_is_persisted_and_read_back(recorded_root):
    payment, repository = recorded_root
    identity = str(payment.pk)
    plan = repository.record_money_sync(identity, receipt(), now=NOW)
    assert plan.applied
    assert plan.facts.captured_funds == Decimal('40.00')
    assert plan.facts.refunded_funds == Decimal(0)
    assert plan.facts.status == PaymentStatus.PARTIAL
    assert repository.get_payment_facts_sync(identity) == plan.facts
    assert repository.get_recorded_money_history_sync(identity) == (plan.entry,)
    payment.refresh_from_db()
    assert payment.amount_paid == Decimal(0)
