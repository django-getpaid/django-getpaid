from django.apps import AppConfig


class Config(AppConfig):
    name = "orders"
    verbose_name = "application orders"
    label = "orders"

    def ready(self):
        # noinspection PyUnresolvedReferences
        from . import signals
