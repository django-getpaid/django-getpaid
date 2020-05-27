from django.conf import settings
from django.test import TestCase

from getpaid import FraudStatus, PaymentStatus
from getpaid.processor import BaseProcessor
from getpaid.registry import registry

dummy = settings.GETPAID_DUMMY_SLUG


class TestRegistry(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()

    def test_register(self):
        assert dummy in settings.INSTALLED_APPS
        # at this point dummy plugin should be registered
        assert dummy in registry
        assert issubclass(registry[dummy], BaseProcessor)

    def test_get_choices(self):
        choices = registry.get_choices("USD")
        assert len(choices) == 1

    def test_url(self):
        # dummy plugin contains at least one example endpoint
        assert len(registry.urls) > 0

    def test_choices(self):
        fraud_choices = FraudStatus.CHOICES
        assert type(fraud_choices) == tuple

        payment_choices = PaymentStatus.CHOICES
        assert type(payment_choices) == tuple
