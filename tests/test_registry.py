import pytest
from django.conf import settings

from getpaid import FraudStatus, PaymentStatus
from getpaid.processor import BaseProcessor
from getpaid.registry import registry

from .tools import Plugin

dummy = 'getpaid.backends.dummy'


class TestRegistry:
    @pytest.fixture(autouse=True)
    def setup_plugin(self):
        if Plugin.slug not in registry:
            registry.register(Plugin)

    def test_register(self):
        assert dummy in settings.INSTALLED_APPS
        assert dummy in registry
        assert issubclass(registry[dummy], BaseProcessor)
        assert Plugin.slug in registry

    def test_get_choices(self):
        choices = registry.get_choices('USD')
        assert len(choices) >= 1
        slugs = [c[0] for c in choices]
        assert Plugin.slug in slugs

    def test_url(self):
        assert len(registry.urls) >= 0

    def test_get_all_supported_currency_choices(self):
        choices = registry.get_all_supported_currency_choices()
        currency_codes = {code for code, _label in choices}
        assert 'EUR' in currency_codes
        assert 'USD' in currency_codes
        for code, label in choices:
            assert code == label
            assert len(code) == 3
            assert code == code.upper()

    def test_choices(self):
        fraud_choices = FraudStatus.CHOICES
        assert type(fraud_choices) == tuple

        payment_choices = PaymentStatus.CHOICES
        assert type(payment_choices) == tuple
