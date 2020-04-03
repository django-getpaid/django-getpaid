import swapper
from django.core.exceptions import ImproperlyConfigured
from django.test import RequestFactory, TestCase

from getpaid.registry import registry

from .tools import Plugin

dummy = "getpaid.backends.dummy"

Order = swapper.load_model("getpaid", "Order")
Payment = swapper.load_model("getpaid", "Payment")


class TestModels(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
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

        request = self.factory.get("getpaid:create-payment")

        assert payment.get_paywall_url() == proc.get_paywall_url()
        assert payment.get_paywall_params(request) == proc.get_paywall_params(request)
        assert payment.get_paywall_method() == proc.get_paywall_method()

        with self.assertRaises(NotImplementedError):
            payment.fetch_status()

        assert payment.get_template_names() == [
            "getpaid_dummy_backend/payment_post_form.html"
        ]

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

        with self.assertRaises(ImproperlyConfigured):
            payment.get_template_names()
