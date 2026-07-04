from django.apps import AppConfig


class GetpaidConfig(AppConfig):
    name = 'getpaid'
    default_auto_field = 'django.db.models.AutoField'

    def ready(self):
        # Register configuration system checks.
        from . import checks  # noqa: F401
