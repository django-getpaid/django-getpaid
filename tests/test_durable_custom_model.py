"""Run explicitly with --ds=tests.settings_durable."""

from decimal import Decimal

import pytest
from django.conf import settings
from django.core.management import call_command

pytest.importorskip(
    'getpaid_core.durable',
    reason='Requires next-major core development checkout',
)

pytestmark = [
    pytest.mark.skipif(
        settings.GETPAID_PAYMENT_MODEL != 'durable_test_app.Payment',
        reason='Requires tests.settings_durable',
    ),
    pytest.mark.django_db(transaction=True, databases='__all__'),
]


def test_recorded_money_custom_model_alias_and_legacy_guard():
    from datetime import UTC, datetime

    from getpaid_core.recorded_money import (
        RECORDED_MONEY_BACKEND,
        RecordedMoneyCommand,
        RecordedMoneyKind,
    )

    from getpaid.durable_models import (
        DurablePaymentState,
        DurableRecordedMoneyEntry,
        DurableStorageReadOnlyError,
    )
    from getpaid.durable_repository import DjangoDurablePaymentRepository
    from getpaid.repository import DjangoPaymentRepository
    from tests.durable_test_app.models import Order, Payment

    for alias in ('default', 'storage'):
        order = Order.objects.using(alias).create(
            name=alias, total=Decimal(100), currency='EUR'
        )
        Payment.objects.using(alias).create(
            id='same-identity',
            order=order,
            amount_required=Decimal(100),
            backend=RECORDED_MONEY_BACKEND
            if alias == 'storage'
            else 'getpaid.backends.dummy',
            currency='EUR',
        )
    stale = Payment.objects.using('storage').get(pk='same-identity')
    repository = DjangoDurablePaymentRepository(using='storage')
    now = datetime(2026, 9, 10, tzinfo=UTC)
    command = RecordedMoneyCommand(
        'receipt', RecordedMoneyKind.RECEIPT, 'actor', Decimal('12.3400'), now
    )
    plan = repository.record_money_sync('same-identity', command, now=now)
    assert plan.facts.captured_funds == Decimal('12.34')
    assert repository.get_recorded_money_history_sync('same-identity') == (
        plan.entry,
    )
    for model in (DurablePaymentState, DurableRecordedMoneyEntry):
        assert model.objects.using('storage').count() == 1
        assert not model.objects.using('default').exists()
    for call in (stale.save, stale.save_base, stale._get_processor):
        with pytest.raises(DurableStorageReadOnlyError):
            call()
    default = DjangoPaymentRepository(Payment)._get_by_id('same-identity')
    default.save()
    assert default.backend == 'getpaid.backends.dummy'
    with pytest.raises(KeyError):
        DjangoDurablePaymentRepository().get_recorded_money_history_sync(
            'same-identity'
        )
    with pytest.raises(RuntimeError, match='application rollback'):  # noqa: PT012
        with repository.atomic():
            repository.record_money_sync(
                'same-identity',
                RecordedMoneyCommand(
                    'second',
                    RecordedMoneyKind.RECEIPT,
                    'actor',
                    Decimal(10),
                    now,
                ),
                now=now,
            )
            Order.objects.using('storage').filter(pk=stale.order_id).update(
                name='allocation'
            )
            raise RuntimeError('application rollback')
    assert (
        Order.objects.using('storage').get(pk=stale.order_id).name == 'storage'
    )
    assert repository.get_recorded_money_history_sync('same-identity') == (
        plan.entry,
    )


def test_batch_custom_string_keys_joined_manager_and_storage_alias():
    from datetime import UTC, datetime

    from getpaid_core.recorded_money import (
        RECORDED_MONEY_BACKEND,
        RecordedMoneyCommand,
        RecordedMoneyKind,
    )

    from getpaid.durable_repository import DjangoDurablePaymentRepository
    from tests.durable_test_app.models import Order, Payment

    repository = DjangoDurablePaymentRepository(Payment, using='storage')
    now = datetime(2026, 9, 20, tzinfo=UTC)
    expected = {}
    for identity in ('second', 'first'):
        order = Order.objects.using('storage').create(
            name=identity, total=Decimal(100), currency='EUR'
        )
        Payment.objects.using('storage').create(
            id=identity,
            order=order,
            amount_required=Decimal(100),
            backend=RECORDED_MONEY_BACKEND,
            currency='EUR',
        )
        plan = repository.record_money_sync(
            identity,
            RecordedMoneyCommand(
                f'receipt:{identity}',
                RecordedMoneyKind.RECEIPT,
                'operator:1',
                Decimal(10),
                now,
            ),
            now=now,
        )
        expected[identity] = (plan.entry,)
    assert (
        repository.get_recorded_money_histories_sync([
            'second',
            'first',
            'second',
        ])
        == expected
    )
    assert not DjangoDurablePaymentRepository().get_recorded_money_histories_sync([])
    with pytest.raises(KeyError):
        DjangoDurablePaymentRepository().get_recorded_money_histories_sync([
            'second',
            'first',
        ])


def test_custom_string_identity_and_all_storage_stay_on_selected_alias():
    from getpaid_core.durable import OperationIntent, OperationType
    from getpaid_core.enums import PaymentStatus
    from getpaid_core.types import PaymentUpdate

    from getpaid.durable_models import (
        DurableOperation,
        DurablePaymentState,
        DurableReplay,
    )
    from getpaid.durable_repository import DjangoDurablePaymentRepository
    from tests.durable_test_app.models import Order, Payment

    order = Order.objects.using('storage').create(
        name='custom', total=Decimal(100), currency='EUR'
    )
    Payment.objects.using('storage').create(
        id='string-payment',
        order=order,
        amount_required=Decimal(100),
        backend='test-provider',
        currency='EUR',
        status=PaymentStatus.PREPARED,
    )
    repository = DjangoDurablePaymentRepository(Payment, using='storage')
    plan = repository.migrate_payment_sync('string-payment')
    assert plan.facts.payment_id == 'string-payment'
    repository.apply_observation_sync(
        'string-payment',
        PaymentUpdate(paid_amount=Decimal(40), provider_event_id='capture'),
    )
    repository.reserve_operation_sync(
        'string-payment', OperationIntent('refund', OperationType.START_REFUND)
    )
    assert (
        repository.get_payment_facts_sync('string-payment').status
        == PaymentStatus.REFUND_STARTED
    )
    assert len(repository.list_unresolved_operations_sync()) == 1
    for model in (DurablePaymentState, DurableOperation, DurableReplay):
        assert model.objects.using('storage').count() == 1
        assert not model.objects.using('default').exists()
    call_command(
        'makemigrations',
        'getpaid',
        'durable_test_app',
        check=True,
        dry_run=True,
        verbosity=0,
    )
    call_command(
        'migrate', database='storage', check_unapplied=True, verbosity=0
    )


def test_legacy_normalization_keeps_same_instance_edits_on_storage_alias():
    from getpaid_core.enums import PaymentStatus

    from tests.durable_test_app.models import Order, Payment

    for alias in ('default', 'storage'):
        order = Order.objects.using(alias).create(
            name=alias, total=Decimal(100), currency='EUR'
        )
        Payment.objects.using(alias).create(
            id='legacy-alias',
            order=order,
            amount_required=Decimal(100),
            backend='getpaid.backends.dummy.processor',
            currency='EUR',
        )
    payment = Payment.objects.using('storage').get(pk='legacy-alias')
    payment.status = PaymentStatus.PRE_AUTH
    payment.amount_required = '120'
    payment.amount_paid = 20
    payment.amount_locked = '80'
    payment.amount_refunded = '0'
    payment.charge(amount=30)
    assert payment.amount_paid == Decimal(50)
    assert payment.amount_locked == Decimal(50)
    payment.refresh_from_db()
    assert payment.amount_required == Decimal(120)
    assert payment.amount_paid == Decimal(50)
    assert payment.amount_locked == Decimal(50)
    assert payment.status == PaymentStatus.PARTIAL
    untouched = Payment.objects.using('default').get(pk='legacy-alias')
    assert untouched.amount_required == Decimal(100)
    assert untouched.amount_paid == Decimal(0)
    assert untouched.status == PaymentStatus.NEW
