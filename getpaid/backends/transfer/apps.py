from django.apps import AppConfig
from django.conf import settings
from django.utils.translation import ugettext_lazy as _


class TransferPluginAppConfig(AppConfig):
    name = settings.GETPAID_TRANSFER_SLUG
    label = "getpaid_transfer"
    verbose_name = _("Przelew ręczny")

    def ready(self):
        from getpaid.registry import registry

        registry.register(self.module)
