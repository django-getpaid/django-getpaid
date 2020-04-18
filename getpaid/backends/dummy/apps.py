from django.apps import AppConfig
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.utils.translation import ugettext_lazy as _


class DummyPluginAppConfig(AppConfig):
    name = "getpaid.backends.dummy"
    label = "getpaid_dummy"
    verbose_name = _("Dummy paywall")

    def ready(self):
        if not settings.DEBUG:
            raise ImproperlyConfigured("Do not use dummy plugin on production!")

        from getpaid.registry import registry

        registry.register(self.module)
