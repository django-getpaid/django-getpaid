from django.conf import settings
from django.test import TestCase

from getpaid.processor import BaseProcessor
from getpaid.registry import registry

dummy = 'getpaid.backends.dummy'


class Plugin(BaseProcessor):
    display_name = 'Test plugin'
    accepted_currencies = ['EUR', 'USD']
    slug = 'test_plugin'

    def get_redirect_url(self):
        return 'test'

    def get_redirect_params(self):
        return {}


class TestRegistry(TestCase):

    def setUp(self):
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

    def tearDown(self):
        pass
