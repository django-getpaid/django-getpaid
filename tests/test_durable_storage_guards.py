"""Ordinary ORM writers cannot erase replay or retained audit evidence."""

from decimal import Decimal

import pytest
from django.db import models
from django.db.models.deletion import ProtectedError

pytest.importorskip(
    'getpaid_core.durable',
    reason='Requires next-major core development checkout',
)

from getpaid_core.durable import OperationIntent, OperationType
from getpaid_core.enums import PaymentStatus
from getpaid_core.types import PaymentUpdate

from getpaid.durable_models import (
    DurableOperation,
    DurablePaymentState,
    DurableReplay,
    DurableStorageReadOnlyError,
)
from getpaid.durable_repository import DjangoDurablePaymentRepository

pytestmark = pytest.mark.django_db(transaction=True)


def test_migration_supports_implicit_default_payment(settings, monkeypatch):
    import importlib.util
    from pathlib import Path

    monkeypatch.delattr(settings, 'GETPAID_PAYMENT_MODEL')
    path = (
        Path(__file__).resolve().parents[1]
        / 'getpaid/migrations/0010_durablepaymentstate_durableoperation_durablereplay.py'
    )
    spec = importlib.util.spec_from_file_location('migration_probe', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert ('getpaid', '__first__') in module.Migration.dependencies


@pytest.fixture
def retained_rows(payment_factory):
    payment = payment_factory(
        amount_required=Decimal(100), status=PaymentStatus.PREPARED
    )
    repository = DjangoDurablePaymentRepository()
    identity = str(payment.pk)
    repository.migrate_payment_sync(identity)
    repository.apply_observation_sync(
        identity,
        PaymentUpdate(paid_amount=Decimal(40), provider_event_id='event'),
    )
    repository.reserve_operation_sync(
        identity, OperationIntent('refund', OperationType.START_REFUND)
    )
    return payment, (
        DurablePaymentState.objects.get(),
        DurableOperation.objects.get(),
        DurableReplay.objects.get(),
    )


@pytest.mark.parametrize(
    'manager_name', ['objects', '_default_manager', '_base_manager']
)
@pytest.mark.parametrize(
    'action',
    [
        'update',
        'delete',
        'bulk_create',
        'bulk_update',
        'get_or_create',
        'update_or_create',
    ],
)
def test_public_querysets_refuse_writes(retained_rows, manager_name, action):
    for row in retained_rows[1]:
        manager = getattr(type(row), manager_name)
        with pytest.raises(DurableStorageReadOnlyError):
            _attempt_write(manager, row, action)


def _attempt_write(manager, row, action):
    if action == 'update':
        manager.filter(pk=row.pk).update(pk=row.pk)
    elif action == 'delete':
        manager.filter(pk=row.pk).delete()
    elif action == 'bulk_create':
        manager.bulk_create(
            [row],
            update_conflicts=True,
            update_fields=['id'],
            unique_fields=['id'],
        )
    elif action == 'bulk_update':
        manager.bulk_update([row], ['id'])
    else:
        getattr(manager, action)(pk=row.pk)


def test_instances_and_roots_cannot_destroy_retained_rows(retained_rows):
    payment, rows = retained_rows
    for row in rows:
        with pytest.raises(DurableStorageReadOnlyError):
            row.save()
        with pytest.raises(DurableStorageReadOnlyError):
            row.delete()
    with pytest.raises(ProtectedError):
        payment.delete()
    with pytest.raises(ProtectedError):
        payment.order.delete()


async def test_async_orm_paths_refuse_writes(retained_rows):
    for row in retained_rows[1]:
        with pytest.raises(DurableStorageReadOnlyError):
            await row.asave()
        with pytest.raises(DurableStorageReadOnlyError):
            await type(row).objects.aupdate(pk=row.pk)


def test_observation_rolls_back_facts_operations_and_replay(
    retained_rows, monkeypatch
):
    payment, _rows = retained_rows
    repository = DjangoDurablePaymentRepository()
    identity = str(payment.pk)
    before = repository.get_payment_facts_sync(identity)
    original = models.QuerySet.bulk_create

    def fail_replay(queryset, *args, **kwargs):
        if queryset.model is DurableReplay:
            raise RuntimeError('storage failed')
        return original(queryset, *args, **kwargs)

    monkeypatch.setattr(models.QuerySet, 'bulk_create', fail_replay)
    with pytest.raises(RuntimeError, match='storage failed'):
        repository.apply_observation_sync(
            identity,
            PaymentUpdate(paid_amount=Decimal(70), provider_event_id='new'),
        )
    assert repository.get_payment_facts_sync(identity) == before
    assert DurableReplay.objects.count() == 1


def test_audit_write_failure_rolls_back_settlement(retained_rows, monkeypatch):
    from datetime import UTC, datetime

    from getpaid_core.durable import (
        OperationOutcome,
        OperationState,
        OperatorResolution,
    )

    payment, _rows = retained_rows
    repository = DjangoDurablePaymentRepository()
    identity = str(payment.pk)
    before = repository.get_payment_facts_sync(identity)
    operation = repository.get_operation_sync(identity, 'refund')
    resolution = OperatorResolution(
        'review',
        'operator',
        'Confirmed',
        ('ledger:refund',),
        datetime(2026, 9, 9, tzinfo=UTC),
        OperationOutcome(OperationState.SUCCEEDED),
    )
    original = models.QuerySet.update

    def fail_audit(queryset, *args, **kwargs):
        if queryset.model is DurableOperation:
            raise RuntimeError('audit storage failed')
        return original(queryset, *args, **kwargs)

    monkeypatch.setattr(models.QuerySet, 'update', fail_audit)
    with pytest.raises(RuntimeError, match='audit storage failed'):
        repository.resolve_operation_sync(
            identity,
            'refund',
            resolution,
            expected_operation=operation,
            expected_facts=before,
        )
    assert repository.get_payment_facts_sync(identity) == before
    assert repository.get_operation_sync(identity, 'refund') == operation


def test_outer_application_transaction_rolls_back_both_writes(retained_rows):
    payment, _rows = retained_rows
    repository = DjangoDurablePaymentRepository()
    identity = str(payment.pk)
    before = repository.get_payment_facts_sync(identity)
    # Multiple writes deliberately share the transaction whose rollback is tested.
    with pytest.raises(RuntimeError, match='allocation failed'):  # noqa: PT012
        with repository.atomic():
            repository.apply_observation_sync(
                identity,
                PaymentUpdate(paid_amount=Decimal(70), provider_event_id='new'),
            )
            type(payment).objects.filter(pk=payment.pk).update(
                description='application write'
            )
            raise RuntimeError('allocation failed')
    payment.refresh_from_db()
    assert payment.description != 'application write'
    assert repository.get_payment_facts_sync(identity) == before
    assert DurableReplay.objects.count() == 1
