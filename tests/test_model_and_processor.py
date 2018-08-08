import swapper
from django.core.exceptions import ImproperlyConfigured
from django.test import TestCase

from getpaid.registry import registry
from .tools import Plugin

dummy = 'getpaid.backends.dummy'

Order = swapper.load_model('getpaid', 'Order')
Payment = swapper.load_model('getpaid', 'Payment')


class TestModels(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        registry.register(Plugin)

    def test_model_and_dummy_backend(self):
        order = Order.objects.create()
        payment = Payment.objects.create(
            order=order, currency=order.currency, amount=order.get_total_amount(),
            backend=dummy, description=order.get_description()
        )
        proc = payment.get_processor()
        assert isinstance(proc, registry[dummy])

        assert payment.get_redirect_url() == proc.get_redirect_url()
        assert payment.get_redirect_params() == proc.get_redirect_params()
        assert payment.get_redirect_method() == proc.get_redirect_method()

        with self.assertRaises(NotImplementedError):
            payment.get_items()

        with self.assertRaises(NotImplementedError):
            payment.fetch_status()

        assert payment.get_template_names() == ['getpaid_dummy_backend/payment_post_form.html']

    def test_model_and_test_backend(self):
        order = Order.objects.create()
        payment = Payment.objects.create(
            order=order, currency=order.currency, amount=order.get_total_amount(),
            backend=Plugin.slug, description=order.get_description()
        )
        proc = payment.get_processor()
        assert isinstance(proc, registry[Plugin.slug])

        with self.assertRaises(ImproperlyConfigured):
            payment.get_template_names()
