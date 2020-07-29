from django.conf import settings
from django.test import TestCase

from getpaid import FraudStatus, PaymentStatus
from getpaid.processor import BaseProcessor
from getpaid.registry import registry

transfer = settings.GETPAID_TRANSFER_SLUG


class TestRegistry(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()

    def test_register(self):
        assert transfer in settings.INSTALLED_APPS
        # at this point transfer plugin should be registered
        assert transfer in registry
        assert issubclass(registry[transfer], BaseProcessor)

    def test_get_choices(self):
        choices = registry.get_choices("USD")
        assert len(choices) == 1

    def test_url(self):
        # transfer plugin contains no urls
        assert len(registry.urls) == 0
