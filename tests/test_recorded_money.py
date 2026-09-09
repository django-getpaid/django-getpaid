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
