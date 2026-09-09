"""Next-major adapter semantics against real Django storage."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

pytest.importorskip(
    'getpaid_core.durable',
    reason='Requires next-major core development checkout',
)

from getpaid_core.durable import (
    MigrationFinding,
    OperationIntent,
    OperationOutcome,
    OperationState,
    OperationType,
    RecoveryEvidence,
)
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


def test_reservation_submission_and_response_are_recoverable(payment_factory):
    payment = payment_factory(
        amount_required=Decimal(100),
        amount_locked=Decimal(100),
        status=PaymentStatus.PRE_AUTH,
    )
    identity = str(payment.pk)
    repository = DjangoDurablePaymentRepository()
    repository.migrate_payment_sync(identity)
    intent = OperationIntent(
        'capture',
        OperationType.CHARGE,
        Decimal('30.00'),
        parameters={'items': [Decimal('1.2300'), {'nested': True}]},
    )
    reserved = repository.reserve_operation_sync(identity, intent)
    assert reserved == repository.get_operation_sync(identity, 'capture')
    now = datetime(2026, 9, 9, 12, 30, 0, 123456, tzinfo=UTC)
    claim = repository.claim_submission_sync(
        identity,
        'capture',
        expected_attempt=0,
        now=now,
        retry_until=now + timedelta(hours=1),
        idempotency_scope='merchant',
    )
    assert claim.granted
    assert not repository.claim_submission_sync(
        identity, 'capture', expected_attempt=0, now=now
    ).granted
    stored = repository.get_operation_sync(identity, 'capture')
    assert stored == claim.operation
    assert stored.pending_response_attempts == (1,)
    assert stored.parameters['items'] == (Decimal('1.2300'), {'nested': True})
    assert (
        stored.parameters['items'][0].as_tuple() == Decimal('1.2300').as_tuple()
    )
    repository.record_operation_outcome_sync(
        identity, 'capture', OperationOutcome(OperationState.UNKNOWN)
    )
    assert (
        repository.list_unresolved_operations_sync()[0].state
        == OperationState.UNKNOWN
    )
    settled = repository.record_operation_outcome_sync(
        identity, 'capture', OperationOutcome(OperationState.SUCCEEDED)
    )
    assert settled.facts.captured_funds == Decimal(30)
    assert settled.facts.remaining_authorization == Decimal(70)
    assert settled.operation in repository.list_unresolved_operations_sync()
    evidence = RecoveryEvidence(
        OperationState.SUCCEEDED, Decimal(30), 'capture-1'
    )
    retained = repository.record_operation_failure_sync(
        identity, 'capture', evidence
    )
    assert retained.recovery_evidence == (evidence,)
    assert retained.state == OperationState.SUCCEEDED
    response = repository.record_operation_outcome_sync(
        identity,
        'capture',
        OperationOutcome(OperationState.SUCCEEDED),
        response_attempt=1,
    )
    assert response.operation.pending_response_attempts == ()
    assert response.operation.recovery_evidence == (evidence,)
    assert response.operation in repository.list_unresolved_operations_sync()
    assert repository.get_payment_facts_sync(identity) == response.facts
