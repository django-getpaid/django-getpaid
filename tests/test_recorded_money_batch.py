"""Public batch read of complete, authoritative recorded-money evidence."""

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
NOW = datetime(2026, 9, 20, tzinfo=UTC)


def test_batch_returns_two_truthful_receipt_histories(payment_factory):
    repository = DjangoDurablePaymentRepository()
    histories = {}
    for amount in ('20.00', '45.00'):
        payment = payment_factory(
            backend=RECORDED_MONEY_BACKEND,
            amount_required=Decimal('100.00'),
            status=PaymentStatus.NEW,
        )
        identity = str(payment.pk)
        plan = repository.record_money_sync(
            identity,
            RecordedMoneyCommand(
                f'receipt:{amount}',
                RecordedMoneyKind.RECEIPT,
                'operator:1',
                Decimal(amount),
                NOW,
            ),
            now=NOW,
        )
        histories[identity] = (plan.entry,)
    assert (
        repository.get_recorded_money_histories_sync(reversed(tuple(histories)))
        == histories
    )


def _recorded_payment(payment_factory, repository, *, amount='20.00'):
    payment = payment_factory(
        backend=RECORDED_MONEY_BACKEND,
        amount_required=Decimal('100.00'),
        status=PaymentStatus.NEW,
    )
    identity = str(payment.pk)
    plan = repository.record_money_sync(
        identity,
        RecordedMoneyCommand(
            f'receipt:{identity}',
            RecordedMoneyKind.RECEIPT,
            'operator:1',
            Decimal(amount),
            NOW,
        ),
        now=NOW,
    )
    return payment, plan


def test_batch_retains_corrections_repayments_and_retired_root_is_not_authority(
    payment_factory,
):
    from getpaid_core.recorded_money import (
        RecordingCorrectionReason,
        project_recorded_money,
    )

    repository = DjangoDurablePaymentRepository()
    first, original = _recorded_payment(payment_factory, repository)
    second, another = _recorded_payment(
        payment_factory, repository, amount='60'
    )
    identity = str(first.pk)
    correction = repository.record_money_sync(
        identity,
        RecordedMoneyCommand(
            'correction',
            RecordedMoneyKind.CORRECTION,
            'reviewer:2',
            target_command_id=original.entry.command.command_id,
            correction_reason=RecordingCorrectionReason.INCORRECT_AMOUNT,
            note='Correction reviewed',
        ),
        now=NOW,
    )
    replacement = repository.record_money_sync(
        identity,
        RecordedMoneyCommand(
            'replacement',
            RecordedMoneyKind.RECEIPT,
            'operator:1',
            Decimal(40),
            NOW,
        ),
        now=NOW,
    )
    repayment = repository.record_money_sync(
        identity,
        RecordedMoneyCommand(
            'repayment',
            RecordedMoneyKind.REPAYMENT,
            'operator:1',
            Decimal(10),
            NOW,
            evidence_reference='bank:1',
        ),
        now=NOW,
    )
    type(first).objects.filter(pk=first.pk).update(
        backend='retired',
        status=PaymentStatus.CANCELLED,
        amount_paid=Decimal(99),
    )
    expected = (
        original.entry,
        correction.entry,
        replacement.entry,
        repayment.entry,
    )
    histories = repository.get_recorded_money_histories_sync([
        str(second.pk),
        identity,
        identity,
    ])
    assert histories == {str(second.pk): (another.entry,), identity: expected}
    assert histories[identity] == repository.get_recorded_money_history_sync(
        identity
    )
    assert project_recorded_money(histories[identity]) == repayment.projection
    assert (
        project_recorded_money(histories[str(second.pk)]) == another.projection
    )
    assert repayment.facts.refunded_funds == Decimal(10)


def test_batch_empty_and_mixed_failures_are_all_or_nothing(payment_factory):
    from django.core.exceptions import ValidationError
    from django.db import connection
    from django.test.utils import CaptureQueriesContext
    from getpaid_core.exceptions import InvalidTransitionError

    repository = DjangoDurablePaymentRepository()
    recorded, plan = _recorded_payment(payment_factory, repository)
    with CaptureQueriesContext(connection) as queries:
        assert repository.get_recorded_money_histories_sync(iter(())) == {}
    assert len(queries) == 0
    assert repository.get_recorded_money_histories_sync([
        str(recorded.pk).upper(),
        str(recorded.pk),
    ]) == {str(recorded.pk): (plan.entry,)}
    uninitialized = payment_factory()
    with pytest.raises(KeyError):
        repository.get_recorded_money_histories_sync([
            str(recorded.pk),
            str(uninitialized.pk),
        ])
    with pytest.raises(KeyError):
        repository.get_recorded_money_histories_sync([
            str(recorded.pk),
            '00000000-0000-0000-0000-000000000000',
        ])
    provider = payment_factory()
    repository.migrate_payment_sync(str(provider.pk))
    with pytest.raises(InvalidTransitionError, match='recorded-money'):
        repository.get_recorded_money_histories_sync([
            str(recorded.pk),
            str(provider.pk),
        ])
    with pytest.raises(ValidationError):
        repository.get_recorded_money_histories_sync(['not-a-uuid'])


def test_batch_query_budget_is_independent_of_roots_and_entry_count(
    payment_factory,
):
    from django.db import connection
    from django.test.utils import CaptureQueriesContext

    repository = DjangoDurablePaymentRepository()
    identities = []
    for count in range(25):
        payment, _plan = _recorded_payment(payment_factory, repository)
        identities.append(str(payment.pk))
        for entry in range(count % 3):
            repository.record_money_sync(
                str(payment.pk),
                RecordedMoneyCommand(
                    f'extra:{entry}',
                    RecordedMoneyKind.RECEIPT,
                    'operator:1',
                    Decimal(1),
                    NOW,
                ),
                now=NOW,
            )

    def measured(ids):
        with CaptureQueriesContext(connection) as queries:
            histories = repository.get_recorded_money_histories_sync(ids)
        assert len(histories) == len(set(ids))
        assert all(histories[identity] for identity in ids)
        assert all(
            not query['sql']
            .lstrip()
            .upper()
            .startswith(('UPDATE', 'INSERT', 'DELETE'))
            for query in queries
        )
        return len(queries)

    assert measured(identities[:1]) == measured(identities)
    assert measured(identities) == (
        7 if connection.vendor == 'postgresql' else 6
    )


def test_batch_propagates_corrupt_entry_and_operation_records(payment_factory):
    from django.db import models

    from getpaid.durable_models import (
        DurableOperation,
        DurableRecordedMoneyEntry,
    )

    repository = DjangoDurablePaymentRepository()
    first, _plan = _recorded_payment(payment_factory, repository)
    second, _plan = _recorded_payment(payment_factory, repository)
    ids = [str(first.pk), str(second.pk)]
    entry = DurableRecordedMoneyEntry.objects.get(payment__payment_id=first.pk)
    models.QuerySet(model=DurableRecordedMoneyEntry).filter(pk=entry.pk).update(
        record={'version': 999}
    )
    with pytest.raises((ValueError, TypeError)):
        repository.get_recorded_money_histories_sync(ids)
    models.QuerySet(model=DurableRecordedMoneyEntry).filter(pk=entry.pk).update(
        record=entry.record
    )
    state = DurableRecordedMoneyEntry.objects.get(
        payment__payment_id=first.pk
    ).payment
    models.QuerySet(model=DurableOperation).bulk_create([
        DurableOperation(
            payment=state,
            operation_id='corrupt',
            record={'version': 999},
            unresolved=False,
        )
    ])
    with pytest.raises((ValueError, TypeError)):
        repository.get_recorded_money_histories_sync(ids)


async def test_batch_async_wrapper_returns_same_histories(payment_factory):
    from asgiref.sync import sync_to_async
    from django.db import connections

    repository = DjangoDurablePaymentRepository()

    def prepare():
        first, original = _recorded_payment(payment_factory, repository)
        second, another = _recorded_payment(payment_factory, repository)
        return [str(second.pk), str(first.pk)], {
            str(first.pk): (original.entry,),
            str(second.pk): (another.entry,),
        }

    identities, expected = await sync_to_async(prepare, thread_sensitive=True)()
    try:
        assert (
            await repository.get_recorded_money_histories(identities)
            == expected
        )
    finally:
        await sync_to_async(connections.close_all, thread_sensitive=True)()
