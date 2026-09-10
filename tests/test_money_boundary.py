"""Same-instance Django assignments must be safe before provider dispatch."""

from decimal import Decimal
from unittest.mock import AsyncMock, Mock, patch

import pytest
import swapper
from getpaid_core.enums import BackendMethod
from getpaid_core.exceptions import InvalidTransitionError
from getpaid_core.types import PaymentUpdate, TransactionResult

from getpaid.backends.dummy.processor import PaymentProcessor
from getpaid.status import PaymentStatus

pytestmark = pytest.mark.django_db

Order = swapper.load_model('getpaid', 'Order')
Payment = swapper.load_model('getpaid', 'Payment')


def make_payment():
    return Payment.objects.create(
        order=Order.objects.create(),
        currency='EUR',
        amount_required=Decimal(100),
        backend='getpaid.backends.dummy',
    )


def test_invalid_money_refuses_before_prepare_dispatch():
    payment = make_payment()
    payment.amount_paid = Decimal('NaN')
    with patch.object(
        PaymentProcessor,
        'prepare_transaction',
        new_callable=AsyncMock,
        return_value=TransactionResult(
            method=BackendMethod.REST, redirect_url='https://example.com/pay'
        ),
    ) as dispatch:
        with pytest.raises(InvalidTransitionError):
            payment.prepare_transaction()
        dispatch.assert_not_called()
    payment.refresh_from_db()
    assert payment.status == PaymentStatus.NEW
    assert payment.amount_paid == Decimal(0)


def test_invalid_callback_money_refuses_after_authentication_before_handling(
    rf,
):
    payment = make_payment()
    payment.amount_paid = Decimal('NaN')
    processor = Mock()
    processor.verify_callback = AsyncMock()
    processor.handle_callback = AsyncMock(return_value=PaymentUpdate())
    with pytest.raises(InvalidTransitionError):
        payment.handle_paywall_callback(
            rf.post('/callback/'), processor=processor
        )
    processor.verify_callback.assert_awaited_once()
    processor.handle_callback.assert_not_called()
    payment.refresh_from_db()
    assert payment.status == PaymentStatus.NEW
    assert payment.amount_paid == Decimal(0)
