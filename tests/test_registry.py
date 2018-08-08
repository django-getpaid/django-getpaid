from django.conf import settings
from django.test import TestCase

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
        assert len(registry.urls) > 0
