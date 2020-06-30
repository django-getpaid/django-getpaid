import pytest
import swapper

from getpaid import PaymentStatus
from getpaid.exceptions import RefundFailure

Order = swapper.load_model("getpaid", "Order")
Payment = swapper.load_model("getpaid", "Payment")

ORDER_ID = "test123"

pytestmark = pytest.mark.django_db


@pytest.fixture
def start_refund_response_mock(requests_mock):
    mock = {
        "orderId": ORDER_ID,
        "refund": {
            "dispositions": {
                "instrumentAmount": "1000",
                "walletAmount": "0",
                "couponAmount": "0",
            },
            "refundId": "5000006708",
            "extRefundId": "0685691c-6c42-4448-b100-3e9e1b2e7a56",
            "amount": "1000",
            "currencyCode": "PLN",
            "description": "Uznanie 5000006708 Zwrot",
            "creationDateTime": "2020-05-28T21:21:28.517+02:00",
            "status": "PENDING",
            "statusDateTime": "2020-05-28T21:21:28.683+02:00",
        },
        "status": {
            "statusCode": "SUCCESS",
            "statusDesc": "Refund queued for processing",
        },
    }
    requests_mock.post(
        f"/api/v2_1/orders/{ORDER_ID}/refunds", json=mock, status_code=200,
    )


def test_start_refund(oauth_mocked, start_refund_response_mock, payment_factory):
    payment = payment_factory(status=PaymentStatus.PAID, external_id=ORDER_ID)
    payment.start_refund()
    payment.save()
    payment = Payment.objects.get()
    assert payment.status == PaymentStatus.REFUND_STARTED
    assert payment.refund_description
    assert payment.external_refund_id
    assert payment.refund_status_desc


def test_invalid_amount(start_refund_response_mock, payment_factory):
    payment = payment_factory(status=PaymentStatus.PAID, amount_paid=1)
    with pytest.raises(ValueError):
        payment.start_refund(amount=10)


def test_refund(getpaid_client, start_refund_response_mock):
    result = getpaid_client.refund(order_id=ORDER_ID, ext_refund_id="random_payment_id")
    assert "orderId" in result
    assert "status" in result
    assert "refund" in result


@pytest.mark.parametrize("response_status", [400, 401, 403, 500, 501])
def test_refund_failure(response_status, getpaid_client, requests_mock):
    ext_order_id = "WZHF5FFDRJ140731GUEST000P01"
    requests_mock.post(
        f"/api/v2_1/orders/{ext_order_id}/refunds",
        text="FAILURE",
        status_code=response_status,
    )
    with pytest.raises(RefundFailure):
        getpaid_client.refund(order_id=ext_order_id, ext_refund_id="random_id")
