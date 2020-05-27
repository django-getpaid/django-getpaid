from django.apps import AppConfig
from django.conf import settings
from django.utils.translation import ugettext_lazy as _


class GetpaidPayUAppConfig(AppConfig):
    name = settings.GETPAID_PAYU_SLUG
    verbose_name = _("PayU")

    def ready(self):
        from getpaid.registry import registry

        registry.register(self.module)
