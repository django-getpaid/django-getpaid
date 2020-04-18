from pytest_factoryboy import register

from .factories import OrderFactory, PaymentFactory, PaywallEntryFactory

register(PaymentFactory)
register(OrderFactory)
register(PaywallEntryFactory)
