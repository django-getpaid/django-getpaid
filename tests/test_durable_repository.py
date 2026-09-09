"""Next-major adapter semantics against real Django storage."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

import pytest
from asgiref.sync import sync_to_async
from django.core.management import call_command

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
    OperatorResolution,
    PaymentObservation,
    RecoveryEvidence,
    run_conformance_suite,
)
from getpaid_core.enums import PaymentStatus
from getpaid_core.exceptions import StateConflictError
from getpaid_core.types import PaymentUpdate

from getpaid.durable_repository import DjangoDurablePaymentRepository

pytestmark = pytest.mark.django_db(transaction=True)


def test_submission_roundtrips_ambiguous_aware_datetime(payment_factory):
    payment = payment_factory(
        amount_required=Decimal(100),
        amount_locked=Decimal(100),
        status=PaymentStatus.PRE_AUTH,
    )
    repository = DjangoDurablePaymentRepository()
    identity = str(payment.pk)
    repository.migrate_payment_sync(identity)
    repository.reserve_operation_sync(
        identity, OperationIntent('capture', OperationType.CHARGE)
    )
    now = datetime(
        2026, 10, 25, 2, 30, tzinfo=ZoneInfo('Europe/Warsaw'), fold=1
    )
    claim = repository.claim_submission_sync(
        identity, 'capture', expected_attempt=0, now=now
    )
    stored = repository.get_operation_sync(identity, 'capture')
    assert stored == claim.operation
    assert stored.submitted_at.tzinfo.key == 'Europe/Warsaw'
    assert stored.submitted_at.fold == 1


async def test_core_conformance_against_database(payment_factory, monkeypatch):
    # Core's suite uses one identity; adapt its fixture constant to this model's
    # UUID primary key, not the repository or any planner behavior.
    monkeypatch.setattr(
        'getpaid_core.durable.conformance.PAYMENT_ID',
        '0a90fbb5-43da-4ead-94e1-d6c4aaebc291',
    )

    @sync_to_async(thread_sensitive=True)
    def factory(facts):
        # Each check requires exactly its facts and an empty TEST database.
        call_command('flush', interactive=False, verbosity=0)
        payment_factory(id=facts.payment_id)
        repository = DjangoDurablePaymentRepository()
        repository.seed_sync(facts)
        return repository

    await run_conformance_suite(factory)


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


def test_observation_conflict_and_audited_resolution_retain_all_evidence(
    payment_factory,
):
    payment = payment_factory(
        amount_required=Decimal(100),
        amount_locked=Decimal(100),
        status=PaymentStatus.PRE_AUTH,
    )
    identity = str(payment.pk)
    repository = DjangoDurablePaymentRepository()
    repository.migrate_payment_sync(identity)
    repository.reserve_operation_sync(
        identity, OperationIntent('capture', OperationType.CHARGE)
    )
    callback = PaymentObservation(
        operation_id='capture',
        outcome=OperationOutcome(
            OperationState.SUCCEEDED, Decimal(30), 'capture-1'
        ),
        provider_event_id='event',
    )
    first = repository.apply_observation_sync(identity, callback)
    assert first.applied
    assert first.operations[0].state == OperationState.SUCCEEDED
    assert not repository.apply_observation_sync(identity, callback).applied
    reviewed = repository.get_operation_sync(identity, 'capture')
    review_facts = repository.get_payment_facts_sync(identity)
    disputed = repository.apply_observation_sync(
        identity,
        PaymentUpdate(paid_amount=Decimal(40), provider_event_id='event'),
    )
    assert not disputed.applied
    assert disputed.facts.captured_funds == Decimal(30)
    assert (
        disputed.facts.observation_conflicts[0].reason == 'conflicting_identity'
    )
    assert (
        disputed.facts
        in repository.list_payments_requiring_reconciliation_sync()
    )
    resolution = OperatorResolution(
        'review',
        'operator',
        'Confirmed ledger',
        ('ledger:1',),
        datetime(2026, 9, 9, tzinfo=UTC),
        OperationOutcome(OperationState.SUCCEEDED, Decimal(40), 'capture-1'),
        clear_payment_reconciliation=True,
    )
    with pytest.raises(StateConflictError):
        repository.resolve_operation_sync(
            identity,
            'capture',
            resolution,
            expected_operation=reviewed,
            expected_facts=review_facts,
        )
    plan = repository.resolve_operation_sync(
        identity,
        'capture',
        resolution,
        expected_operation=reviewed,
        expected_facts=disputed.facts,
    )
    stored = repository.get_operation_sync(identity, 'capture')
    assert stored == plan.operation
    assert stored.resolutions == (resolution,)
    assert stored.conflicting_outcomes == (
        OperationOutcome(OperationState.SUCCEEDED, Decimal(30), 'capture-1'),
    )
    assert (
        repository.get_payment_facts_sync(identity).observation_conflicts
        == disputed.facts.observation_conflicts
    )
    assert plan.facts.captured_funds == Decimal(40)
    assert (
        repository.resolve_operation_sync(
            identity,
            'capture',
            resolution,
            expected_operation=reviewed,
            expected_facts=review_facts,
        )
        == plan
    )
    assert not repository.list_payments_requiring_reconciliation_sync()
    assert not repository.apply_observation_sync(identity, callback).applied
