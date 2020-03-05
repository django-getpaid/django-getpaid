from django.apps import AppConfig
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.utils.translation import ugettext_lazy as _


class GetpaidPaynowAppConfig(AppConfig):
    name = "getpaid.backends.paynow"
    label = "getpaid_paynow"
    verbose_name = _("mBank Paynow")

    def ready(self):
        from getpaid.registry import registry

        registry.register(self.module)
