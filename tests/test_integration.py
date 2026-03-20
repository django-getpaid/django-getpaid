import uuid

import pytest
import swapper
from django.template.response import TemplateResponse

from getpaid.registry import registry
from getpaid.types import PaymentStatus as ps

from .tools import Plugin

pytestmark = pytest.mark.django_db
dummy = 'getpaid.backends.dummy'

Order = swapper.load_model('getpaid', 'Order')
Payment = swapper.load_model('getpaid', 'Payment')


def _prep_conf(paywall_method='REST', confirmation_status='paid'):
    return {
        'getpaid.backends.dummy': {
            'paywall_method': paywall_method,
            'confirmation_status': confirmation_status,
        }
    }


class TestModelProcessor:
    @pytest.fixture(autouse=True)
    def setup_plugin(self):
        if Plugin.slug not in registry:
            registry.register(Plugin)

    def test_model_and_dummy_backend(self):
        order = Order.objects.create()
        payment = Payment.objects.create(
            order=order,
            currency=order.currency,
            amount_required=order.get_total_amount(),
            backend=dummy,
            description=order.get_description(),
        )
        proc = payment._get_processor()
        assert isinstance(proc, registry[dummy])

    def test_model_and_test_backend(self):
        order = Order.objects.create()
        payment = Payment.objects.create(
            order=order,
            currency=order.currency,
            amount_required=order.get_total_amount(),
            backend=Plugin.slug,
            description=order.get_description(),
        )
        proc = payment._get_processor()
        assert isinstance(proc, registry[Plugin.slug])


def test_get_flow_begin(payment_factory, settings):
    settings.GETPAID_BACKEND_SETTINGS = _prep_conf(paywall_method='GET')
    payment = payment_factory(external_id=uuid.uuid4())

    result = payment.prepare_transaction(None)
    assert result.status_code == 302
    payment.refresh_from_db()
    assert payment.status == ps.PREPARED


def test_post_flow_begin(payment_factory, settings, rf):
    settings.GETPAID_BACKEND_SETTINGS = _prep_conf(paywall_method='POST')
    payment = payment_factory(external_id=uuid.uuid4())

    result = payment.prepare_transaction(rf.get('/'))
    assert isinstance(result, TemplateResponse)
    payment.refresh_from_db()
    assert payment.status == ps.PREPARED


def test_rest_flow_begin(payment_factory, settings):
    settings.GETPAID_BACKEND_SETTINGS = _prep_conf(paywall_method='REST')
    payment = payment_factory(external_id=uuid.uuid4())

    result = payment.prepare_transaction(None)
    assert result.status_code == 302
    payment.refresh_from_db()
    assert payment.status == ps.PREPARED


def test_pull_flow_paid(payment_factory, settings):
    settings.GETPAID_BACKEND_SETTINGS = _prep_conf(confirmation_status='paid')
    payment = payment_factory(status=ps.PREPARED, external_id=uuid.uuid4())

    payment.fetch_and_update_status()
    payment.refresh_from_db()

    assert payment.status == ps.PAID


def test_pull_flow_locked(payment_factory, settings):
    settings.GETPAID_BACKEND_SETTINGS = _prep_conf(
        confirmation_status='pre_auth'
    )
    payment = payment_factory(status=ps.PREPARED, external_id=uuid.uuid4())

    payment.fetch_and_update_status()
    payment.refresh_from_db()

    assert payment.status == ps.PRE_AUTH


def test_pull_flow_failed(payment_factory, settings):
    settings.GETPAID_BACKEND_SETTINGS = _prep_conf(confirmation_status='failed')
    payment = payment_factory(status=ps.PREPARED, external_id=uuid.uuid4())

    payment.fetch_and_update_status()
    payment.refresh_from_db()

    assert payment.status == ps.FAILED
