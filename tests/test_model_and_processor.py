import os

import swapper
from django.test import LiveServerTestCase, RequestFactory

from getpaid.registry import registry

from .tools import Plugin

dummy = "getpaid.backends.dummy"

Order = swapper.load_model("getpaid", "Order")
Payment = swapper.load_model("getpaid", "Payment")


class TestModels(LiveServerTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        os.environ["_PAYWALL_URL"] = cls.live_server_url
        registry.register(Plugin)
        cls.factory = RequestFactory()

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
