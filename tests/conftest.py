from pytest_factoryboy import register

from .factories import OrderFactory, PaywallEntryFactory

register(OrderFactory)
register(PaywallEntryFactory)
