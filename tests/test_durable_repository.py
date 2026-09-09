"""Next-major adapter semantics against real Django storage."""

from decimal import Decimal

import pytest

pytest.importorskip(
    'getpaid_core.durable',
    reason='Requires next-major core development checkout',
)

from getpaid_core.durable import MigrationFinding
from getpaid_core.enums import PaymentStatus

from getpaid.durable_repository import DjangoDurablePaymentRepository

pytestmark = pytest.mark.django_db(transaction=True)


def test_migration_reads_stored_payment_not_stale_snapshot(payment_factory):
    payment = payment_factory(
        amount_required=Decimal(100),
        amount_paid=Decimal(40),
        status=PaymentStatus.PARTIAL,
        provider_data={'applied_event_ids': ['old'], 'merchant': 'kept'},
    )
    repository = DjangoDurablePaymentRepository()
    payment.amount_paid = Decimal(99)
    plan = repository.migrate_payment_sync(str(payment.pk))
    stored = repository.get_payment_facts_sync(str(payment.pk))
    assert stored == plan.facts
    assert stored.captured_funds == Decimal(40)
    assert stored.provider_data == {
        'applied_event_ids': ['old'],
        'merchant': 'kept',
    }
    assert plan.findings == (MigrationFinding.UNPROMOTED_EVENT_HISTORY,)
    assert repository.get_operation_sync(str(payment.pk), 'invented') is None
    with pytest.raises(ValueError, match='already initialized'):
        repository.migrate_payment_sync(str(payment.pk))
