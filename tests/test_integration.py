import uuid

import pytest
import swapper
from django.template.response import TemplateResponse
from getpaid_core.fsm import create_payment_machine

from getpaid.registry import registry
from getpaid.types import BackendMethod as bm
from getpaid.types import ConfirmationMethod as cm
from getpaid.types import PaymentStatus as ps

from .tools import Plugin

pytestmark = pytest.mark.django_db
dummy = 'getpaid.backends.dummy'

Order = swapper.load_model('getpaid', 'Order')
Payment = swapper.load_model('getpaid', 'Payment')


def _prep_conf(api_method: bm = bm.REST, confirm_method: cm = cm.PUSH) -> dict:
    return {
        'getpaid.backends.dummy': {
            'paywall_method': api_method,
            'confirmation_method': confirm_method,
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


def test_get_flow_begin(payment_factory, settings, rf):
    settings.GETPAID_BACKEND_SETTINGS = _prep_conf(api_method=bm.GET)
    payment = payment_factory(external_id=uuid.uuid4())

    result = payment.prepare_transaction(None)
    assert result.status_code == 302


def test_post_flow_begin(payment_factory, settings, rf):
    settings.GETPAID_BACKEND_SETTINGS = _prep_conf(api_method=bm.POST)
    payment = payment_factory(external_id=uuid.uuid4())

    result = payment.prepare_transaction(None)
    assert result.status_code == 200
    assert isinstance(result, TemplateResponse)
    assert payment.status == ps.PREPARED


def test_rest_flow_begin(payment_factory, settings, rf):
    settings.GETPAID_BACKEND_SETTINGS = _prep_conf(api_method=bm.REST)
    payment = payment_factory(external_id=uuid.uuid4())

    result = payment.prepare_transaction(None)
    assert result.status_code == 302
    assert payment.status == ps.PREPARED


def test_pull_flow_paid(payment_factory, settings):
    settings.GETPAID_BACKEND_SETTINGS = {
        'getpaid.backends.dummy': {
            'confirmation_method': cm.PULL,
            'confirmation_status': 'paid',
        }
    }

    payment = payment_factory(external_id=uuid.uuid4())
    create_payment_machine(payment)
    payment.confirm_prepared()

    payment.fetch_and_update_status()
    assert payment.status == ps.PARTIAL
    create_payment_machine(payment)
    assert payment.may_trigger('mark_as_paid')


def test_pull_flow_locked(payment_factory, settings):
    settings.GETPAID_BACKEND_SETTINGS = {
        'getpaid.backends.dummy': {
            'confirmation_method': cm.PULL,
            'confirmation_status': 'pre_auth',
        }
    }

    payment = payment_factory(external_id=uuid.uuid4())
    create_payment_machine(payment)
    payment.confirm_prepared()

    payment.fetch_and_update_status()
    assert payment.status == ps.PRE_AUTH


def test_pull_flow_failed(payment_factory, settings):
    settings.GETPAID_BACKEND_SETTINGS = {
        'getpaid.backends.dummy': {
            'confirmation_method': cm.PULL,
            'confirmation_status': 'failed',
        }
    }

    payment = payment_factory(external_id=uuid.uuid4())
    create_payment_machine(payment)
    payment.confirm_prepared()

    payment.fetch_and_update_status()
    assert payment.status == ps.FAILED


def test_push_flow_paid(payment_factory, settings, rf):
    settings.GETPAID_BACKEND_SETTINGS = _prep_conf(confirm_method=cm.PUSH)

    payment = payment_factory(external_id=uuid.uuid4())
    create_payment_machine(payment)
    payment.confirm_prepared()

    request = rf.post(
        '', content_type='application/json', data={'new_status': ps.PAID}
    )
    payment.handle_paywall_callback(request)
    assert payment.status == ps.PAID


def test_push_flow_locked(payment_factory, settings, rf):
    settings.GETPAID_BACKEND_SETTINGS = _prep_conf(confirm_method=cm.PUSH)

    payment = payment_factory(external_id=uuid.uuid4())
    create_payment_machine(payment)
    payment.confirm_prepared()

    request = rf.post(
        '', content_type='application/json', data={'new_status': ps.PRE_AUTH}
    )
    payment.handle_paywall_callback(request)
    assert payment.status == ps.PRE_AUTH


def test_push_flow_failed(payment_factory, settings, rf):
    settings.GETPAID_BACKEND_SETTINGS = _prep_conf(confirm_method=cm.PUSH)

    payment = payment_factory(external_id=uuid.uuid4())
    create_payment_machine(payment)
    payment.confirm_prepared()

    request = rf.post(
        '', content_type='application/json', data={'new_status': ps.FAILED}
    )
    payment.handle_paywall_callback(request)
    assert payment.status == ps.FAILED
