import uuid
from decimal import Decimal

import pytest
import swapper
from django.urls import reverse_lazy
from pytest import raises

from getpaid.backends.payu.types import Currency
from getpaid.exceptions import (
    ChargeFailure,
    CommunicationError,
    GetPaidException,
    LockFailure,
    RefundFailure,
)

pytestmark = pytest.mark.django_db

Order = swapper.load_model("getpaid", "Order")
Payment = swapper.load_model("getpaid", "Payment")

url_post_payment = "https://secure.snd.payu.com/api/v2_1/orders"
url_api_register = "https://secure.snd.payu.com/api/v2_1/orders"
url_api_operate = reverse_lazy("paywall:api_operate")


@pytest.mark.parametrize(
    "before,after",
    [
        ({"unitPrice": 100}, {"unitPrice": Decimal("1")}),
        ({"amount": 100}, {"amount": Decimal("1")}),
        ([{"amount": 100}], [{"amount": Decimal("1")}]),
        ({"internal": {"amount": 100}}, {"internal": {"amount": Decimal("1")}}),
        ({"internal": [{"amount": 100}]}, {"internal": [{"amount": Decimal("1")}]}),
        (
            [{"internal": [{"amount": 100}]}, ],
            [{"internal": [{"amount": Decimal("1")}]}, ],
        ),
    ],
)
def test_normalize(before, after, getpaid_client):
    result = getpaid_client._normalize(before)
    assert result == after


@pytest.mark.parametrize(
    "before,after",
    [
        ({"unitPrice": 1}, {"unitPrice": 100}),
        ({"amount": 1}, {"amount": 100}),
        ({"unitPrice": 1.0}, {"unitPrice": 100}),
        ({"unitPrice": Decimal("1")}, {"unitPrice": 100}),
        ([{"unitPrice": Decimal("1")}], [{"unitPrice": 100}]),
        ({"internal": {"unitPrice": Decimal("1")}}, {"internal": {"unitPrice": 100}}),
        (
            {"internal": [{"unitPrice": Decimal("1")}]},
            {"internal": [{"unitPrice": 100}]},
        ),
        (
            [{"internal": [{"unitPrice": Decimal("1")}]}],
            [{"internal": [{"unitPrice": 100}]}],
        ),
    ],
)
def test_centify(before, after, getpaid_client):
    result = getpaid_client._centify(before)
    assert result == after


@pytest.mark.parametrize("response_status", [200, 201, 302])
def test_new_order(response_status, getpaid_client, requests_mock):
    my_order_id = f"{uuid.uuid4()}"
    requests_mock.post(
        "/api/v2_1/orders",
        json={
            "status": {"statusCode": "SUCCESS", },
            "redirectUri": "https://paywall.example.com/url",
            "orderId": "WZHF5FFDRJ140731GUEST000P01",
            "extOrderId": my_order_id,
        },
        status_code=response_status,
    )

    result = getpaid_client.new_order(
        amount=20, currency=Currency.PLN, order_id=my_order_id
    )
    assert "status" in result
    assert "redirectUri" in result
    assert "orderId" in result
    assert "extOrderId" in result


@pytest.mark.parametrize("response_status", [400, 401, 403, 500, 501])
def test_new_order_failure(response_status, getpaid_client, requests_mock):
    my_order_id = f"{uuid.uuid4()}"
    requests_mock.post(
        "/api/v2_1/orders", text="FAILURE", status_code=response_status,
    )
    with raises(LockFailure):
        getpaid_client.new_order(amount=20, currency=Currency.PLN, order_id=my_order_id)


def test_refund(getpaid_client, requests_mock):
    ext_order_id = "WZHF5FFDRJ140731GUEST000P01"
    requests_mock.post(
        f"/api/v2_1/orders/{ext_order_id}/refunds",
        json={
            "orderId": "WZHF5FFDRJ140731GUEST000P01",
            "refund": {
                "refundId": "86821",
                "extRefundId": "20151031133322",
                "amount": "100",
                "currencyCode": "PLN",
                "description": "Uznanie 86821 Refund",
                "creationDateTime": "2015-10-31T13:33:22.396+01:00",
                "status": "PENDING",
                "statusDateTime": "2015-10-31T13:33:22.718+01:00",
            },
            "status": {
                "statusCode": "SUCCESS",
                "statusDesc": "Refund queued for processing",
            },
        },
    )
    result = getpaid_client.refund(order_id=ext_order_id)
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
    with raises(RefundFailure):
        getpaid_client.refund(order_id=ext_order_id)


@pytest.mark.parametrize("response_status", [400, 401, 403, 500, 501])
def test_cancel_order_failure(response_status, getpaid_client, requests_mock):
    ext_order_id = "WZHF5FFDRJ140731GUEST000P01"
    requests_mock.delete(
        f"/api/v2_1/orders/{ext_order_id}", text="FAILURE", status_code=response_status,
    )
    with raises(GetPaidException):
        getpaid_client.cancel_order(order_id=ext_order_id)


@pytest.mark.parametrize("response_status", [400, 401, 403, 500, 501])
def test_capture_failure(response_status, getpaid_client, requests_mock):
    ext_order_id = "WZHF5FFDRJ140731GUEST000P01"
    requests_mock.put(
        f"/api/v2_1/orders/{ext_order_id}/status",
        text="FAILURE",
        status_code=response_status,
    )
    with raises(ChargeFailure):
        getpaid_client.capture(order_id=ext_order_id)


@pytest.mark.parametrize("response_status", [400, 401, 403, 500, 501])
def test_get_order_info_failure(response_status, getpaid_client, requests_mock):
    ext_order_id = "WZHF5FFDRJ140731GUEST000P01"
    requests_mock.get(
        f"/api/v2_1/orders/{ext_order_id}", text="FAILURE", status_code=response_status,
    )
    with raises(CommunicationError):
        getpaid_client.get_order_info(order_id=ext_order_id)


@pytest.mark.parametrize("response_status", [400, 401, 403, 500, 501])
def test_get_shop_info_failure(response_status, getpaid_client, requests_mock):
    requests_mock.get(
        f"/api/v2_1/shops/{getpaid_client.pos_id}",
        text="FAILURE",
        status_code=response_status,
    )
    with raises(CommunicationError):
        getpaid_client.get_shop_info(shop_id=getpaid_client.pos_id)
