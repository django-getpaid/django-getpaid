from django.apps import AppConfig


class Config(AppConfig):
    name = 'orders'
    verbose_name = 'application orders'
    label = 'orders'
    default_auto_field = 'django.db.models.AutoField'

    def ready(self):
        # noinspection PyUnresolvedReferences
        from . import signals  # noqa: F401
