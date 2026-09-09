"""Recorded-money storage: core semantics over complete, persisted evidence."""

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

pytest.importorskip(
    'getpaid_core.recorded_money', reason='Requires upcoming core'
)

from getpaid_core.enums import PaymentStatus
from getpaid_core.exceptions import (
    InvalidTransitionError,
    OperationConflictError,
)
from getpaid_core.recorded_money import (
    RECORDED_MONEY_BACKEND,
    RecordedMoneyCommand,
    RecordedMoneyKind,
    RecordingCorrectionReason,
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


def correction(identity='correction', target='receipt'):
    return RecordedMoneyCommand(
        identity,
        RecordedMoneyKind.CORRECTION,
        'reviewer:2',
        target_command_id=target,
        correction_reason=RecordingCorrectionReason.INCORRECT_AMOUNT,
        note='Correct mistaken assertion',
    )


def test_replay_after_correction_and_replacement_retains_original(
    recorded_root,
):
    payment, repository = recorded_root
    identity = str(payment.pk)
    command = receipt(evidence_reference='ledger:1')
    original = repository.record_money_sync(identity, command, now=NOW)
    inverse = repository.record_money_sync(identity, correction(), now=NOW)
    assert inverse.facts.captured_funds == Decimal(0)
    assert inverse.facts.status == PaymentStatus.PREPARED
    assert inverse.entry.evidence_reference == 'ledger:1'
    assert inverse.entry.signed_amount == Decimal('-40.00')
    replacement = repository.record_money_sync(
        identity, receipt('replacement', '60'), now=NOW
    )
    for retry in (replace(command, amount=Decimal('40.000')), correction()):
        replay = repository.record_money_sync(
            identity, retry, now=NOW + timedelta(days=1)
        )
        assert not replay.applied
        assert replay.facts == replacement.facts
        assert replay.entry.recorded_at == NOW
    assert repository.get_recorded_money_history_sync(identity) == (
        original.entry,
        inverse.entry,
        replacement.entry,
    )
    with pytest.raises(OperationConflictError):
        repository.record_money_sync(
            identity, replace(command, actor='different'), now=NOW
        )


@pytest.mark.parametrize('zero_summary', [False, True])
@pytest.mark.parametrize(
    'action',
    [
        'reserve_operation',
        'claim_submission',
        'record_operation_outcome',
        'record_operation_failure',
        'apply_observation',
        'resolve_operation',
    ],
)
def test_provider_mutations_refuse_before_any_planner(
    recorded_root, monkeypatch, action, zero_summary
):
    from unittest.mock import Mock

    from getpaid_core.types import PaymentUpdate

    import getpaid.durable_repository as module

    payment, repository = recorded_root
    identity = str(payment.pk)
    repository.record_money_sync(identity, receipt(), now=NOW)
    if zero_summary:
        repository.record_money_sync(identity, correction(), now=NOW)
    planners = [
        'plan_reservation',
        'plan_submission',
        'plan_outcome',
        'plan_operation_failure',
        'plan_observation',
        'plan_resolution',
    ]
    spies = [
        Mock(side_effect=AssertionError('provider planner invoked'))
        for _ in planners
    ]
    for name, spy in zip(planners, spies, strict=True):
        monkeypatch.setattr(module, name, spy)
    args, kwargs = {
        'reserve_operation': ((None,), {}),
        'claim_submission': (('absent',), {'expected_attempt': 0, 'now': NOW}),
        'record_operation_outcome': (('absent', None), {}),
        'record_operation_failure': (('absent', None), {}),
        'apply_observation': ((PaymentUpdate(),), {}),
        'resolve_operation': (
            ('absent', None),
            {'expected_operation': None, 'expected_facts': None},
        ),
    }[action]
    with pytest.raises(InvalidTransitionError, match='recorded-money'):
        getattr(repository, action + '_sync')(identity, *args, **kwargs)
    for spy in spies:
        spy.assert_not_called()


@pytest.mark.parametrize('initializer', ['seed', 'migrate_payment'])
@pytest.mark.parametrize('source', ['recorded', 'provider'])
def test_generic_initializers_cannot_create_or_convert_recorded_roots(
    payment_factory, initializer, source
):
    from getpaid_core.durable import PaymentFacts

    payment = payment_factory(
        backend=RECORDED_MONEY_BACKEND if source == 'recorded' else 'provider'
    )
    repository = DjangoDurablePaymentRepository()
    identity = str(payment.pk)
    facts = PaymentFacts(
        identity,
        Decimal(100),
        RECORDED_MONEY_BACKEND if source == 'provider' else 'provider',
    )
    if initializer == 'migrate_payment' and source == 'provider':
        facts = replace(facts, backend='provider')
        repository.seed_sync(facts)
        with pytest.raises(InvalidTransitionError):
            repository.record_money_sync(identity, receipt(), now=NOW)
        return
    argument = facts if initializer == 'seed' else identity
    with pytest.raises(InvalidTransitionError, match='record_money'):
        getattr(repository, initializer + '_sync')(argument)


def repayment(identity='repayment', amount='10.00'):
    return RecordedMoneyCommand(
        identity,
        RecordedMoneyKind.REPAYMENT,
        'operator:1',
        Decimal(amount),
        NOW,
        evidence_reference='bank:repaid',
    )


def test_repayment_correction_keeps_evidence_and_receipt_cannot_unfund_it(
    recorded_root,
):
    payment, repository = recorded_root
    identity = str(payment.pk)
    original = repository.record_money_sync(identity, receipt(), now=NOW)
    repaid = repository.record_money_sync(identity, repayment(), now=NOW)
    assert repaid.facts.refunded_funds == Decimal(10)
    with pytest.raises(InvalidTransitionError):
        repository.record_money_sync(identity, correction(), now=NOW)
    assert repository.get_recorded_money_history_sync(identity) == (
        original.entry,
        repaid.entry,
    )
    withdrawn = repository.record_money_sync(
        identity, correction('withdraw-repayment', 'repayment'), now=NOW
    )
    assert withdrawn.entry.signed_amount == Decimal(10)
    assert withdrawn.entry.evidence_reference == 'bank:repaid'
    assert withdrawn.facts.refunded_funds == Decimal(0)
    repository.record_money_sync(identity, correction(), now=NOW)
    assert len(repository.get_recorded_money_history_sync(identity)) == 4


@pytest.mark.parametrize(
    'changes',
    [
        {'backend': 'provider'},
        {'amount_paid': Decimal(1)},
        {'amount_refunded': Decimal(1)},
        {'amount_locked': Decimal(1)},
        {'external_id': 'provider-handle'},
        {'provider_data': {'benign': True}},
        {'fraud_status': 'accepted'},
        {'fraud_message': 'evidence'},
        {'status': PaymentStatus.PAID},
        {'status': PaymentStatus.CANCELLED},
    ],
)
def test_initialization_refuses_truthful_unclean_source(recorded_root, changes):
    from getpaid.durable_models import (
        DurablePaymentState,
        DurableRecordedMoneyEntry,
    )

    payment, repository = recorded_root
    type(payment).objects.filter(pk=payment.pk).update(**changes)
    with pytest.raises(InvalidTransitionError):
        repository.record_money_sync(str(payment.pk), receipt(), now=NOW)
    assert not DurablePaymentState.objects.exists()
    assert not DurableRecordedMoneyEntry.objects.exists()


@pytest.mark.parametrize(
    'command', [receipt(amount='101'), repayment(), correction()]
)
def test_first_core_refusal_leaves_no_initialization(recorded_root, command):
    from getpaid.durable_models import (
        DurablePaymentState,
        DurableRecordedMoneyEntry,
    )

    payment, repository = recorded_root
    with pytest.raises(InvalidTransitionError):
        repository.record_money_sync(str(payment.pk), command, now=NOW)
    assert not DurablePaymentState.objects.exists()
    assert not DurableRecordedMoneyEntry.objects.exists()


def test_backdated_business_time_never_reorders_commits(recorded_root):
    payment, repository = recorded_root
    identity = str(payment.pk)
    original = repository.record_money_sync(
        identity, receipt(), now=NOW + timedelta(days=2)
    )
    backdated = repository.record_money_sync(
        identity,
        replace(
            receipt('backdated', '20'), occurred_at=NOW - timedelta(days=1)
        ),
        now=NOW + timedelta(days=2),
    )
    history = repository.get_recorded_money_history_sync(identity)
    assert history == (original.entry, backdated.entry)


def test_zero_summary_does_not_erase_history_or_reread_retired_fields(
    recorded_root,
):
    payment, repository = recorded_root
    identity = str(payment.pk)
    repository.record_money_sync(identity, receipt(), now=NOW)
    repository.record_money_sync(identity, correction(), now=NOW)
    type(payment).objects.filter(pk=payment.pk).update(
        backend='retired', amount_paid=Decimal(99)
    )
    retry = repository.record_money_sync(identity, receipt(), now=NOW)
    assert not retry.applied
    assert retry.facts.captured_funds == Decimal(0)
    assert len(repository.get_recorded_money_history_sync(identity)) == 2
    with pytest.raises(OperationConflictError):
        repository.record_money_sync(identity, receipt(amount='50'), now=NOW)


@pytest.mark.parametrize(
    'missing', ['uninitialized', 'nonexistent', 'provider']
)
def test_history_reader_never_invents_empty_history(payment_factory, missing):
    payment = payment_factory()
    identity = str(payment.pk)
    repository = DjangoDurablePaymentRepository()
    if missing == 'provider':
        repository.migrate_payment_sync(identity)
    elif missing == 'nonexistent':
        identity = '00000000-0000-0000-0000-000000000000'
    with pytest.raises(
        InvalidTransitionError if missing == 'provider' else KeyError
    ):
        repository.get_recorded_money_history_sync(identity)


@pytest.mark.parametrize('initialized', [False, True])
@pytest.mark.parametrize('failure', ['outer', 'second_write'])
def test_entry_facts_and_application_write_roll_back(
    recorded_root, monkeypatch, initialized, failure
):
    from django.db import models

    from getpaid.durable_models import (
        DurablePaymentState,
        DurableRecordedMoneyEntry,
    )

    payment, repository = recorded_root
    identity = str(payment.pk)
    if initialized:
        repository.record_money_sync(identity, receipt(), now=NOW)
    before = (
        repository.get_payment_facts_sync(identity) if initialized else None
    )
    if failure == 'second_write':
        original_update = models.QuerySet.update

        def fail_facts(queryset, **kwargs):
            if queryset.model is DurablePaymentState:
                raise RuntimeError('injected failure')
            return original_update(queryset, **kwargs)

        monkeypatch.setattr(models.QuerySet, 'update', fail_facts)
    with pytest.raises(RuntimeError, match='injected failure'):  # noqa: PT012
        with repository.atomic():
            repository.record_money_sync(
                identity, receipt('second', '20'), now=NOW
            )
            type(payment).objects.filter(pk=payment.pk).update(
                description='allocation'
            )
            raise RuntimeError('injected failure')
    payment.refresh_from_db()
    assert payment.description != 'allocation'
    assert DurableRecordedMoneyEntry.objects.count() == int(initialized)
    if initialized:
        assert repository.get_payment_facts_sync(identity) == before
    else:
        assert not DurablePaymentState.objects.exists()


async def test_async_record_and_history_share_sync_semantics(recorded_root):
    from asgiref.sync import sync_to_async
    from django.db import connections

    payment, repository = recorded_root
    try:
        first = await repository.record_money(
            str(payment.pk), receipt(), now=NOW
        )
        assert await repository.get_recorded_money_history(str(payment.pk)) == (
            first.entry,
        )
        assert not (
            await repository.record_money(str(payment.pk), receipt(), now=NOW)
        ).applied
    finally:
        await sync_to_async(connections.close_all, thread_sensitive=True)()


@pytest.mark.parametrize(
    'manager_name', ['objects', '_base_manager', '_default_manager']
)
@pytest.mark.parametrize(
    'action',
    [
        'create',
        'update',
        'delete',
        'bulk_create',
        'bulk_update',
        'get_or_create',
        'update_or_create',
    ],
)
def test_recorded_entry_public_managers_refuse(
    recorded_root, manager_name, action
):
    from getpaid.durable_models import (
        DurableRecordedMoneyEntry,
        DurableStorageReadOnlyError,
    )
    from tests import test_durable_storage_guards as guards

    payment, repository = recorded_root
    repository.record_money_sync(str(payment.pk), receipt(), now=NOW)
    row = DurableRecordedMoneyEntry.objects.get()
    manager = getattr(DurableRecordedMoneyEntry, manager_name)
    with pytest.raises(DurableStorageReadOnlyError):
        guards._attempt_write(manager, row, action)


def test_recorded_entry_instance_and_deletion_guards(recorded_root):
    from django.db.models.deletion import ProtectedError

    from getpaid.durable_models import (
        DurableRecordedMoneyEntry,
        DurableStorageReadOnlyError,
    )

    payment, repository = recorded_root
    repository.record_money_sync(str(payment.pk), receipt(), now=NOW)
    row = DurableRecordedMoneyEntry.objects.get()
    for action in (row.save, row.save_base, row.delete):
        with pytest.raises(DurableStorageReadOnlyError):
            action()
    for root in (payment, payment.order):
        with pytest.raises(ProtectedError):
            root.delete()


async def test_recorded_entry_async_writers_refuse(recorded_root):
    from asgiref.sync import sync_to_async
    from django.db import connections

    from getpaid.durable_models import (
        DurableRecordedMoneyEntry,
        DurableStorageReadOnlyError,
    )

    payment, repository = recorded_root
    try:
        await repository.record_money(str(payment.pk), receipt(), now=NOW)
        row = await DurableRecordedMoneyEntry.objects.aget()
        calls = [
            row.asave,
            row.adelete,
            lambda: DurableRecordedMoneyEntry.objects.acreate(pk=row.pk),
            lambda: DurableRecordedMoneyEntry.objects.aupdate(pk=row.pk),
            lambda: DurableRecordedMoneyEntry.objects.all().adelete(),
            lambda: DurableRecordedMoneyEntry.objects.abulk_create([row]),
            lambda: DurableRecordedMoneyEntry.objects.abulk_update(
                [row], ['record']
            ),
            lambda: DurableRecordedMoneyEntry.objects.aget_or_create(pk=row.pk),
            lambda: DurableRecordedMoneyEntry.objects.aupdate_or_create(
                pk=row.pk
            ),
        ]
        for call in calls:
            with pytest.raises(DurableStorageReadOnlyError):
                await call()
    finally:
        await sync_to_async(connections.close_all, thread_sensitive=True)()


@pytest.mark.parametrize('contamination', ['operation', 'replay'])
def test_complete_provider_histories_are_supplied_to_core(
    recorded_root, contamination
):
    from django.db import models
    from getpaid_core.durable import (
        OperationRecord,
        OperationState,
        OperationType,
    )

    from getpaid.durable_codec import dump_record
    from getpaid.durable_models import (
        DurableOperation,
        DurablePaymentState,
        DurableReplay,
    )

    payment, repository = recorded_root
    identity = str(payment.pk)
    first = repository.record_money_sync(identity, receipt(), now=NOW)
    state = DurablePaymentState.objects.get()
    if contamination == 'replay':
        row = DurableReplay(
            payment=state,
            backend='provider',
            event_identity='old',
            content_digest='a' * 64,
        )
    else:
        operation = OperationRecord(
            payment_id=identity,
            operation_id='old',
            operation_type=OperationType.PREPARE,
            state=OperationState.SUCCEEDED,
            resolved_amount=Decimal(100),
            parameters_digest='digest',
            starting_captured=Decimal(0),
            starting_refunded=Decimal(0),
        )
        row = DurableOperation(
            payment=state,
            operation_id='old',
            record=dump_record(operation),
            unresolved=False,
        )
    # Deliberately inject corrupt history through the private ORM bypass.
    models.QuerySet(model=type(row)).bulk_create([row])
    with pytest.raises(InvalidTransitionError, match='uncontaminated'):
        repository.record_money_sync(identity, receipt(), now=NOW)
    assert repository.get_payment_facts_sync(identity) == first.facts
    assert repository.get_recorded_money_history_sync(identity) == (
        first.entry,
    )


def test_required_amount_is_immutable(recorded_root):
    from getpaid.durable_models import DurablePaymentState

    payment, repository = recorded_root
    facts = repository.record_money_sync(
        str(payment.pk), receipt(), now=NOW
    ).facts
    with pytest.raises(ValueError, match='identity'):
        repository._write_facts(
            DurablePaymentState.objects.get(),
            replace(facts, amount_required=Decimal(200)),
        )
