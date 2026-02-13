from django.apps import AppConfig


class Config(AppConfig):
    name = 'paywall'
    verbose_name = 'paywall simulator'
    label = 'paywall'
    default_auto_field = 'django.db.models.AutoField'
