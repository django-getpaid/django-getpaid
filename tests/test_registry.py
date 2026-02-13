from django.conf import settings
from django.test import TestCase

from getpaid import FraudStatus, PaymentStatus
from getpaid.processor import BaseProcessor
from getpaid.registry import registry

from .tools import Plugin

dummy = 'getpaid.backends.dummy'


class TestRegistry(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        registry.register(Plugin)

    def test_register(self):
        assert dummy in settings.INSTALLED_APPS
        # at this point dummy plugin should be registered
        assert dummy in registry
        assert issubclass(registry[dummy], BaseProcessor)

        assert Plugin.slug in registry

    def test_get_choices(self):
        choices = registry.get_choices('USD')
        assert len(choices) == 1
        assert choices[0][0] == Plugin.slug

    def test_url(self):
        # dummy plugin contains at least one example endpoint
        assert len(registry.urls) > 0

    def test_get_all_supported_currency_choices(self):
        """Test that get_all_supported_currency_choices returns currencies
        from registered backends (not iterating dict keys as strings)."""
        choices = registry.get_all_supported_currency_choices()
        # Plugin has accepted_currencies = ['EUR', 'USD']
        # Dummy has accepted_currencies = ['PLN', 'EUR', 'GBP', 'USD']
        currency_codes = {code for code, _label in choices}
        # At minimum, the Plugin's currencies should appear
        assert 'EUR' in currency_codes
        assert 'USD' in currency_codes
        # Each choice should be (CODE, CODE) tuple
        for code, label in choices:
            assert code == label
            assert len(code) == 3
            assert code == code.upper()

    def test_choices(self):
        fraud_choices = FraudStatus.CHOICES
        assert type(fraud_choices) == tuple

        payment_choices = PaymentStatus.CHOICES
        assert type(payment_choices) == tuple
