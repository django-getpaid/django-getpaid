import pytest
import swapper
from django.conf import settings
from django.template.loader import render_to_string

from getpaid.backends.transfer import PaymentProcessor
from getpaid.registry import registry

pytestmark = pytest.mark.django_db
transfer = settings.GETPAID_TRANSFER_SLUG

Order = swapper.load_model("getpaid", "Order")
Payment = swapper.load_model("getpaid", "Payment")


def test_model_and_transfer_backend():
    order = Order.objects.create()
    payment = Payment.objects.create(
        order=order,
        currency=order.currency,
        amount_required=order.get_total_amount(),
        backend=transfer,
        description=order.get_description(),
    )
    proc = payment.get_processor()
    assert isinstance(proc, registry[transfer])


def test_prepare_transaction_set_message(payment_factory):
    payment = payment_factory()
    payment.prepare_transaction()
    template = PaymentProcessor.default_message_template
    assert payment.message == render_to_string(
        template, {"order": payment.order, "payment": payment,}
    )
