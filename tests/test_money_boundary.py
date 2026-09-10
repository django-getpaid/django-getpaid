"""Same-instance Django assignments must be safe before provider dispatch."""

from decimal import Decimal, InvalidOperation
from unittest.mock import AsyncMock, Mock, patch

import pytest
import swapper
from getpaid_core.enums import BackendMethod
from getpaid_core.exceptions import InvalidTransitionError
from getpaid_core.types import PaymentUpdate, TransactionResult

from getpaid.backends.dummy.processor import PaymentProcessor
from getpaid.flow_adapter import DjangoPaymentFlowAdapter
from getpaid.status import FraudStatus, PaymentStatus

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


@pytest.mark.parametrize(
    'field',
    ['amount_required', 'amount_paid', 'amount_locked', 'amount_refunded'],
)
@pytest.mark.parametrize('value', [Decimal('NaN'), Decimal('Infinity'), '-1'])
def test_invalid_money_refuses_before_prepare_dispatch(field, value):
    payment = make_payment()
    setattr(payment, field, value)
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


@pytest.mark.parametrize(
    'operation',
    ['charge', 'fetch_status', 'start_refund', 'cancel_refund', 'release_lock'],
)
@pytest.mark.parametrize(
    'field',
    ['amount_required', 'amount_paid', 'amount_locked', 'amount_refunded'],
)
@pytest.mark.parametrize('value', ['NaN', 'Infinity', '-1', 'not-money', None])
def test_invalid_money_refuses_other_dispatch(operation, field, value):
    payment = make_payment()
    payment.status = {
        'charge': PaymentStatus.PRE_AUTH,
        'fetch_status': PaymentStatus.PREPARED,
        'start_refund': PaymentStatus.PAID,
        'cancel_refund': PaymentStatus.REFUND_STARTED,
        'release_lock': PaymentStatus.PRE_AUTH,
    }[operation]
    payment.amount_paid = Decimal(100) if 'refund' in operation else Decimal(0)
    payment.amount_locked = (
        Decimal(100) if operation in {'charge', 'release_lock'} else Decimal(0)
    )
    setattr(payment, field, value)
    method = (
        'fetch_payment_status' if operation == 'fetch_status' else operation
    )
    with patch.object(
        PaymentProcessor, method, new_callable=AsyncMock
    ) as dispatch:
        with pytest.raises((InvalidTransitionError, InvalidOperation)):
            getattr(payment, operation)()
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


@pytest.mark.parametrize('representation', [int, str])
@pytest.mark.parametrize('entrypoint', ['model', 'adapter'])
@pytest.mark.parametrize(
    'operation',
    [
        'prepare',
        'charge',
        'fetch_status',
        'start_refund',
        'cancel_refund',
        'release_lock',
    ],
)
def test_numeric_assignments_on_same_instance(
    operation, entrypoint, representation
):
    payment = make_payment()
    states = {
        'prepare': PaymentStatus.NEW,
        'charge': PaymentStatus.PRE_AUTH,
        'fetch_status': PaymentStatus.PREPARED,
        'start_refund': PaymentStatus.PAID,
        'cancel_refund': PaymentStatus.REFUND_STARTED,
        'release_lock': PaymentStatus.PRE_AUTH,
    }
    payment.status = states[operation]
    # Caller edits differ from the stored row: normalization must not reload it.
    payment.amount_required = representation(120)
    paid = 20 if operation == 'charge' else 120 if 'refund' in operation else 0
    payment.amount_paid = representation(paid)
    payment.amount_locked = representation(
        80 if operation in {'charge', 'release_lock'} else 0
    )
    payment.amount_refunded = representation(0)
    payment.provider_data = {'caller': 'kept'}
    target = (
        payment
        if entrypoint == 'model'
        else DjangoPaymentFlowAdapter(payment, Payment)
    )
    method = (
        'prepare_transaction'
        if operation == 'prepare' and entrypoint == 'model'
        else operation
    )
    kwargs = (
        {'amount': Decimal(30)}
        if operation in {'charge', 'start_refund'}
        else {}
    )
    getattr(target, method)(**kwargs)
    assert all(
        isinstance(getattr(payment, field), Decimal)
        for field in (
            'amount_required',
            'amount_paid',
            'amount_locked',
            'amount_refunded',
        )
    )
    assert payment.amount_required == Decimal(120)
    assert payment.provider_data['caller'] == 'kept'
    if operation == 'charge':
        assert payment.amount_paid == Decimal(50)
        assert payment.amount_locked == Decimal(50)
    elif operation == 'fetch_status':
        assert payment.amount_paid == Decimal(120)
    payment.refresh_from_db()
    assert payment.amount_required == Decimal(120)
    if operation == 'charge':
        assert payment.amount_paid == Decimal(50)
        assert payment.amount_locked == Decimal(50)


@pytest.mark.parametrize('representation', [int, str])
@pytest.mark.parametrize(
    ('method', 'expected'),
    [
        ('flag_as_fraud', FraudStatus.REJECTED),
        ('flag_as_legit', FraudStatus.ACCEPTED),
        ('flag_for_check', FraudStatus.CHECK),
    ],
)
def test_fraud_normalizes_same_instance_assignments(
    representation, method, expected
):
    payment = make_payment()
    payment.amount_required = representation(120)
    payment.amount_paid = representation(10)
    payment.amount_locked = representation(20)
    payment.amount_refunded = representation(5)
    getattr(payment, method)(message='Review evidence')
    assert payment.fraud_status == expected
    assert payment.fraud_message == 'Review evidence'
    assert (
        payment.amount_required,
        payment.amount_paid,
        payment.amount_locked,
        payment.amount_refunded,
    ) == (Decimal(120), Decimal(10), Decimal(20), Decimal(5))
    assert isinstance(payment.amount_required, Decimal)


@pytest.mark.parametrize('representation', [int, str])
def test_callback_normalizes_same_instance_assignments(rf, representation):
    payment = make_payment()
    payment.status = PaymentStatus.PREPARED
    payment.amount_required = representation(120)
    payment.amount_paid = representation(0)
    payment.amount_locked = representation(0)
    payment.amount_refunded = representation(0)
    response = payment.handle_paywall_callback(
        rf.post('/callback/', {'new_status': 'paid'})
    )
    assert response.status_code == 200
    assert payment.amount_paid == Decimal(120)
    payment.refresh_from_db()
    assert payment.amount_required == Decimal(120)
    assert payment.amount_paid == Decimal(120)
    assert payment.status == PaymentStatus.PAID


def test_failed_authentication_does_not_normalize_or_handle_callback(rf):
    payment = make_payment()
    payment.amount_required = 'invalid'
    processor = Mock()
    processor.verify_callback = AsyncMock(
        side_effect=PermissionError('Untrusted callback')
    )
    processor.handle_callback = AsyncMock()
    with pytest.raises(PermissionError, match='Untrusted callback'):
        payment.handle_paywall_callback(
            rf.post('/callback/'), processor=processor
        )
    processor.handle_callback.assert_not_called()
    assert payment.amount_required == 'invalid'
    assert payment.status == PaymentStatus.NEW
