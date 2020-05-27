from django.conf import settings
from django.test import TestCase

from getpaid import FraudStatus, PaymentStatus
from getpaid.processor import BaseProcessor
from getpaid.registry import registry

payu = settings.GETPAID_PAYU_SLUG


class TestRegistry(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()

    def test_register(self):
        assert payu in settings.INSTALLED_APPS
        # at this point payu plugin should be registered
        assert payu in registry
        assert issubclass(registry[payu], BaseProcessor)

    def test_url(self):
        # payu plugin contains at least one example endpoint
        assert len(registry.urls) > 0

    def test_choices(self):
        fraud_choices = FraudStatus.CHOICES
        assert type(fraud_choices) == tuple

        payment_choices = PaymentStatus.CHOICES
        assert type(payment_choices) == tuple
