from django.apps import AppConfig
from getpaid import signals


class Config(AppConfig):
    name = 'orders'
    verbose_name = 'application orders'
    label = 'orders'
