import os
import uuid

import pytest
import swapper
from django.template.response import TemplateResponse
from django.test import TestCase
from django.urls import reverse, reverse_lazy
from django_fsm import can_proceed

from getpaid.registry import registry
from getpaid.status import PaymentStatus as ps

from .tools import Plugin

pytestmark = pytest.mark.django_db
dummy = "getpaid.backends.dummy"

Order = swapper.load_model("getpaid", "Order")
Payment = swapper.load_model("getpaid", "Payment")

url_post_payment = reverse_lazy("paywall:gateway")
url_api_register = reverse_lazy("paywall:api_register")
url_api_operate = reverse_lazy("paywall:api_operate")


class TestModelProcessor(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
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
        proc = payment.get_processor()
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
        proc = payment.get_processor()
        assert isinstance(proc, registry[Plugin.slug])


def test_get_flow_begin(payment_factory, settings, live_server, requests_mock, rf):
    os.environ["_PAYWALL_URL"] = live_server.url
    settings.GETPAID_BACKEND_SETTINGS = {"getpaid.backends.dummy": {"method": "GET"}}
    payment = payment_factory(external_id=uuid.uuid4())

    result = payment.prepare_transaction(None)
    assert result.status_code == 302


def test_post_flow_begin(payment_factory, settings, live_server, requests_mock, rf):
    os.environ["_PAYWALL_URL"] = live_server.url
    settings.GETPAID_BACKEND_SETTINGS = {"getpaid.backends.dummy": {"method": "POST"}}
    payment = payment_factory(external_id=uuid.uuid4())

    result = payment.prepare_transaction(None)
    assert result.status_code == 200
    assert isinstance(result, TemplateResponse)
    assert payment.status == ps.PREPARED


def test_rest_flow_begin(payment_factory, settings, live_server, requests_mock, rf):
    os.environ["_PAYWALL_URL"] = live_server.url
    settings.GETPAID_BACKEND_SETTINGS = {"getpaid.backends.dummy": {"method": "REST"}}

    payment = payment_factory(external_id=uuid.uuid4())
    requests_mock.post(str(url_api_register), json={"url": str(url_post_payment)})
    result = payment.prepare_transaction(None)

    assert result.status_code == 302
    assert payment.status == ps.PREPARED


# PULL flow
def test_pull_flow_paid(payment_factory, settings, live_server, requests_mock, rf):
    os.environ["_PAYWALL_URL"] = live_server.url
    settings.GETPAID_BACKEND_SETTINGS = {
        "getpaid.backends.dummy": {"confirmation_method": "PULL"}
    }

    payment = payment_factory(external_id=uuid.uuid4())
    payment.confirm_prepared()

    url_get_status = reverse("paywall:get_status", kwargs={"pk": payment.external_id})
    requests_mock.get(url_get_status, json={"payment_status": ps.PAID})
    payment.fetch_and_update_status()
    # all confirmed payments are by default marked as PARTIAL
    assert payment.status == ps.PARTIAL
    # and need to be checked and marked if complete
    assert can_proceed(payment.mark_as_paid)


def test_pull_flow_locked(payment_factory, settings, live_server, requests_mock, rf):
    os.environ["_PAYWALL_URL"] = live_server.url
    settings.GETPAID_BACKEND_SETTINGS = {
        "getpaid.backends.dummy": {"confirmation_method": "PULL"}
    }

    payment = payment_factory(external_id=uuid.uuid4())
    payment.confirm_prepared()

    url_get_status = reverse("paywall:get_status", kwargs={"pk": payment.external_id})
    requests_mock.get(url_get_status, json={"payment_status": ps.PRE_AUTH})
    payment.fetch_and_update_status()
    assert payment.status == ps.PRE_AUTH


def test_pull_flow_failed(payment_factory, settings, live_server, requests_mock, rf):
    os.environ["_PAYWALL_URL"] = live_server.url
    settings.GETPAID_BACKEND_SETTINGS = {
        "getpaid.backends.dummy": {"confirmation_method": "PULL"}
    }

    payment = payment_factory(external_id=uuid.uuid4())
    payment.confirm_prepared()

    url_get_status = reverse("paywall:get_status", kwargs={"pk": payment.external_id})
    requests_mock.get(url_get_status, json={"payment_status": ps.FAILED})
    payment.fetch_and_update_status()
    assert payment.status == ps.FAILED


# PUSH flow
def test_push_flow_paid(payment_factory, settings, live_server, requests_mock, rf):
    os.environ["_PAYWALL_URL"] = live_server.url
    settings.GETPAID_BACKEND_SETTINGS = {
        "getpaid.backends.dummy": {"confirmation_method": "PUSH"}
    }

    payment = payment_factory(external_id=uuid.uuid4())
    payment.confirm_prepared()

    request = rf.post("", content_type="application/json", data={"new_status": ps.PAID})
    payment.handle_paywall_callback(request)
    assert payment.status == ps.PAID


def test_push_flow_locked(payment_factory, settings, live_server, requests_mock, rf):
    os.environ["_PAYWALL_URL"] = live_server.url
    settings.GETPAID_BACKEND_SETTINGS = {
        "getpaid.backends.dummy": {"confirmation_method": "PUSH"}
    }

    payment = payment_factory(external_id=uuid.uuid4())
    payment.confirm_prepared()

    request = rf.post(
        "", content_type="application/json", data={"new_status": ps.PRE_AUTH}
    )
    payment.handle_paywall_callback(request)
    assert payment.status == ps.PRE_AUTH


def test_push_flow_failed(payment_factory, settings, live_server, requests_mock, rf):
    os.environ["_PAYWALL_URL"] = live_server.url
    settings.GETPAID_BACKEND_SETTINGS = {
        "getpaid.backends.dummy": {"confirmation_method": "PUSH"}
    }

    payment = payment_factory(external_id=uuid.uuid4())
    payment.confirm_prepared()

    request = rf.post(
        "", content_type="application/json", data={"new_status": ps.FAILED}
    )
    payment.handle_paywall_callback(request)
    assert payment.status == ps.FAILED
