from decimal import Decimal

import pytest
from django.test import override_settings

from getpaid.forms import PaymentMethodForm

pytestmark = pytest.mark.django_db


@override_settings(
    GETPAID_BACKEND_SETTINGS={
        'getpaid.backends.dummy': {'paywall_method': 'REST'}
    }
)
def test_payment_method_form_recomputes_server_controlled_fields(order_factory):
    order = order_factory(total=Decimal('10.00'), currency='EUR')

    form = PaymentMethodForm(
        data={
            'order': order.pk,
            'amount_required': '999.99',
            'description': 'Tampered description',
            'currency': 'USD',
            'backend': 'dummy',
        },
        initial={'order': order, 'currency': order.currency},
    )

    assert form.is_valid(), form.errors

    assert form.cleaned_data['amount_required'] == Decimal('10.00')
    assert form.cleaned_data['description'] == order.get_description()
    assert form.cleaned_data['currency'] == 'EUR'


@override_settings(
    GETPAID_BACKEND_SETTINGS={
        'getpaid.backends.dummy': {'paywall_method': 'REST'}
    }
)
def test_payment_method_form_save_persists_server_controlled_fields(
    order_factory,
):
    order = order_factory(total=Decimal('25.50'), currency='USD')

    form = PaymentMethodForm(
        data={
            'order': order.pk,
            'amount_required': '1.00',
            'description': 'Tampered description',
            'currency': 'EUR',
            'backend': 'dummy',
        },
        initial={'order': order, 'currency': order.currency},
    )

    assert form.is_valid(), form.errors

    payment = form.save()

    assert payment.amount_required == Decimal('25.50')
    assert payment.description == order.get_description()
    assert payment.currency == 'USD'
    assert payment.backend == 'dummy'
