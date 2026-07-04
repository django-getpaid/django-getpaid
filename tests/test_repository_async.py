from decimal import Decimal

import pytest
import swapper

from getpaid.repository import DjangoPaymentRepository
from getpaid.types import PaymentStatus as ps

pytestmark = [
    pytest.mark.django_db(transaction=True),
    pytest.mark.asyncio,
]

Payment = swapper.load_model('getpaid', 'Payment')


def _forbid_sync_to_async(*args, **kwargs):
    raise AssertionError('DjangoPaymentRepository async methods must use async ORM APIs directly.')


@pytest.fixture
def repository(monkeypatch):
    monkeypatch.setattr(
        'getpaid.repository.sync_to_async',
        _forbid_sync_to_async,
        raising=False,
    )
    return DjangoPaymentRepository(Payment)


@pytest.fixture
def order(order_factory):
    return order_factory()


@pytest.fixture
def payment(payment_factory):
    return payment_factory()


@pytest.fixture
def payment_for_update(payment_factory):
    return payment_factory(status=ps.NEW)


@pytest.fixture
def order_with_payments(order_factory, payment_factory):
    order = order_factory()
    # Only one non-failed payment per order is allowed by the
    # getpaid_unique_non_failed_payment_per_order constraint.
    first = payment_factory(order=order, status=ps.FAILED)
    second = payment_factory(order=order)
    payment_factory()
    return order, first, second


async def test_create_uses_async_orm(repository, order):

    payment = await repository.create(
        order=order,
        backend='getpaid.backends.dummy',
        amount_required=order.get_total_amount(),
        currency=order.get_currency(),
        description=order.get_description(),
        provider_data={'source': 'test'},
    )

    assert payment.pk is not None
    assert payment.order_id == order.pk
    assert payment.provider_data == {'source': 'test'}


async def test_get_by_id_uses_async_orm(repository, payment):
    fetched = await repository.get_by_id(payment.pk)

    assert fetched.pk == payment.pk
    assert fetched.order_id == payment.order_id


async def test_save_uses_async_orm(repository, payment):
    payment.amount_paid = Decimal('10.00')

    saved = await repository.save(payment)

    assert saved.amount_paid == Decimal('10.00')
    assert saved.last_payment_on is not None


async def test_update_status_uses_async_orm(repository, payment_for_update):
    updated = await repository.update_status(
        payment_for_update.pk,
        ps.PAID,
        external_id='EXT-123',
    )

    assert updated.status == ps.PAID
    assert updated.external_id == 'EXT-123'


async def test_list_by_order_uses_async_orm(repository, order_with_payments):
    order, first, second = order_with_payments

    payments = await repository.list_by_order(order.pk)

    assert {payment.pk for payment in payments} == {first.pk, second.pk}
