"""Legacy entrypoints must not treat durable roots as payable snapshots."""

from decimal import Decimal
from unittest.mock import Mock

import pytest
from asgiref.sync import sync_to_async

pytest.importorskip('getpaid_core.durable', reason='Requires upcoming core')

from getpaid.durable_models import DurableStorageReadOnlyError
from getpaid.durable_repository import DjangoDurablePaymentRepository
from getpaid.repository import DjangoPaymentRepository

pytestmark = pytest.mark.django_db(transaction=True)


@pytest.fixture
def stale_root(payment_factory):
    payment = payment_factory()
    # Cache absence before cutover: ownership checks must issue a fresh query.
    assert not hasattr(payment, 'durable_state')
    DjangoDurablePaymentRepository().migrate_payment_sync(str(payment.pk))
    return payment


@pytest.mark.parametrize(
    'action', ['save', 'save_base', 'repository_save', 'read', 'list']
)
def test_stale_legacy_reads_and_writes_refuse(stale_root, action):
    payment = stale_root
    repository = DjangoPaymentRepository(type(payment))
    calls = {
        'save': payment.save,
        'save_base': payment.save_base,
        'repository_save': lambda: repository._save(payment),
        'read': lambda: repository._get_by_id(payment.pk),
        'list': lambda: repository._list_by_order(payment.order_id),
    }
    payment.amount_paid = Decimal(99)
    with pytest.raises(DurableStorageReadOnlyError):
        calls[action]()
    payment.refresh_from_db()
    assert payment.amount_paid == Decimal(0)


@pytest.mark.parametrize('explicit', [False, True])
def test_callback_refuses_before_resolution_verification_or_dispatch(
    stale_root, rf, monkeypatch, explicit
):
    from getpaid.bridge import bridge
    from getpaid.registry import registry

    processor = Mock()
    resolve = Mock(side_effect=AssertionError('processor resolved'))
    verify = Mock(side_effect=AssertionError('callback verified'))
    dispatch = Mock(side_effect=AssertionError('provider dispatched'))
    monkeypatch.setattr(type(registry), '__getitem__', resolve)
    monkeypatch.setattr(bridge, 'call_verify_callback', verify)
    monkeypatch.setattr(bridge, 'call', dispatch)
    kwargs = {'processor': processor} if explicit else {}
    with pytest.raises(DurableStorageReadOnlyError):
        stale_root.handle_paywall_callback(rf.post('/'), **kwargs)
    resolve.assert_not_called()
    verify.assert_not_called()
    dispatch.assert_not_called()
    assert not processor.mock_calls


def test_stale_backend_does_not_resolve_a_processor(stale_root, monkeypatch):
    import importlib

    stale_root.backend = 'an.unregistered.provider'
    resolve = Mock(side_effect=AssertionError('module imported'))
    monkeypatch.setattr(importlib, 'import_module', resolve)
    with pytest.raises(DurableStorageReadOnlyError):
        stale_root._get_processor()
    resolve.assert_not_called()


@pytest.mark.parametrize('action', ['save', 'asave', 'read', 'list', 'update'])
async def test_async_legacy_entrypoints_refuse(stale_root, action):
    repository = DjangoPaymentRepository(type(stale_root))
    calls = {
        'save': lambda: repository.save(stale_root),
        'asave': stale_root.asave,
        'read': lambda: repository.get_by_id(stale_root.pk),
        'list': lambda: repository.list_by_order(stale_root.order_id),
        'update': lambda: repository.update_status(stale_root.pk, 'paid'),
    }
    with pytest.raises(DurableStorageReadOnlyError):
        await calls[action]()
    from django.db import connections

    await sync_to_async(connections.close_all, thread_sensitive=True)()


def test_constructed_snapshot_with_existing_pk_cannot_save(stale_root):
    snapshot = type(stale_root)(pk=stale_root.pk)
    with pytest.raises(DurableStorageReadOnlyError):
        snapshot.save()
