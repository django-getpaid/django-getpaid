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
