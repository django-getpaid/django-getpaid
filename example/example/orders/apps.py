from django.apps import AppConfig
from getpaid import signals


class Config(AppConfig):
    name = 'example.orders'
    verbose_name = 'application orders'
    label = 'orders'

    def ready(self):
        from . import listeners
        signals.new_payment_query.connect(listeners.new_payment_query_listener)
        signals.payment_status_changed.connect(listeners.payment_status_changed_listener)
        signals.user_data_query.connect(listeners.user_data_query_listener)
