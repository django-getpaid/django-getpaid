import factory

from .models import Order, Payment


class OrderFactory(factory.DjangoModelFactory):

    class Meta:
        model = Order

    name = factory.Sequence(lambda n: "order {}".format(n))


class PaymentFactory(factory.DjangoModelFactory):

    class Meta:
        model = Payment

    order = factory.SubFactory(OrderFactory)
    amount = 200
    currency = "PLN"
    backend = "getpaid.backends.payu"
