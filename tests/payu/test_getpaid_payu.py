import hashlib
import json
import uuid
from decimal import Decimal

import pytest
import swapper
from django.conf import settings
from django.template.response import TemplateResponse
from django_fsm import can_proceed

from getpaid.backends.payu import PaymentProcessor
from getpaid.backends.payu.types import OrderStatus
from getpaid.types import BackendMethod as bm
from getpaid.types import ConfirmationMethod as cm
from getpaid.types import PaymentStatus as ps

pytestmark = pytest.mark.django_db

Order = swapper.load_model("getpaid", "Order")
Payment = swapper.load_model("getpaid", "Payment")

url_post_payment = "https://secure.snd.payu.com/api/v2_1/orders"
url_api_register = "https://secure.snd.payu.com/api/v2_1/orders"


def _prep_conf(api_method: bm = bm.REST, confirm_method: cm = cm.PUSH, is_marketplace=False) -> dict:
    return {
        settings.GETPAID_PAYU_SLUG: {
            "pos_id": 300746,
            "second_key": "b6ca15b0d1020e8094d9b5f8d163db54",
            "client_id": 300746,
            "client_secret": "2ee86a66e5d97e3fadc400c9f19b065d",
            "paywall_method": api_method,
            "confirmation_method": confirm_method,
            "is_marketplace": is_marketplace
        }
    }


def test_post_flow_begin(payment_factory, settings, requests_mock, getpaid_client):
    my_order_id = f"{uuid.uuid4()}"
    requests_mock.post(
        "/api/v2_1/orders",
        json={
            "status": {"statusCode": "SUCCESS", },
            "redirectUri": "https://paywall.example.com/url",
            "orderId": "WZHF5FFDRJ140731GUEST000P01",
            "extOrderId": my_order_id,
        },
    )

    settings.GETPAID_BACKEND_SETTINGS = _prep_conf(api_method=bm.POST)
    payment = payment_factory(external_id=my_order_id)

    result = payment.prepare_transaction(None)
    assert result.status_code == 200
    assert isinstance(result, TemplateResponse)
    assert payment.status == ps.NEW


@pytest.mark.parametrize("response_status", [200, 201, 302])
def test_rest_flow_begin(
    response_status, payment_factory, settings, requests_mock, getpaid_client
):
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

    settings.GETPAID_BACKEND_SETTINGS = _prep_conf(api_method=bm.REST)

    payment = payment_factory(external_id=uuid.uuid4())
    requests_mock.post(str(url_api_register), json={"url": str(url_post_payment)})
    result = payment.prepare_transaction(None)

    assert result.status_code == 302
    assert payment.status == ps.PREPARED


# PULL flow
@pytest.mark.parametrize(
    "remote_status,our_status,callback",
    [
        (OrderStatus.COMPLETED, ps.PARTIAL, "mark_as_paid"),
        (OrderStatus.WAITING_FOR_CONFIRMATION, ps.PRE_AUTH, None),
        (OrderStatus.CANCELED, ps.FAILED, None),
    ],
)
def test_pull_flow(
    remote_status,
    our_status,
    callback,
    payment_factory,
    settings,
    requests_mock,
    getpaid_client,
):
    settings.GETPAID_BACKEND_SETTINGS = _prep_conf(confirm_method=cm.PULL)

    payment = payment_factory(external_id=uuid.uuid4())
    payment.confirm_prepared()
    requests_mock.get(
        f"/api/v2_1/orders/{payment.external_id}",
        json={
            "orders": [
                {
                    "extOrderId": f"{payment.id}",
                    "customerIp": "127.0.0.1",
                    "merchantPosId": getpaid_client.pos_id,
                    "description": "description",
                    "validityTime": 46000,
                    "currencyCode": payment.currency,
                    "totalAmount": f"{payment.amount_required}",
                    "buyer": {},  # doesn't matter now
                    "products": {},  # doesn't matter now
                    "status": remote_status,
                }
            ],
            "status": {"statusCode": "SUCCESS", "statusDesc": "some status"},
        },
    )
    payment.fetch_and_update_status()
    # all confirmed payments are by default marked as PARTIAL
    assert payment.status == our_status
    # and need to be checked and marked if complete
    if callback:
        callback_meth = getattr(payment, callback)
        assert can_proceed(callback_meth)


@pytest.fixture
def marketplace_get_items_mock(monkeypatch):
    items = [
        {
            "products": [],
            "extCustomerId" "1234"
            "amount": Decimal('100.00'),
            "fee": Decimal("15.00")
        }
    ]
    monkeypatch.setattr(Order, "get_items", lambda self: items)


def test_shopping_carts_if_is_marketplace(
    marketplace_get_items_mock,
    getpaid_client,
    settings,
    payment_factory,
    rf
):
    settings.GETPAID_BACKEND_SETTINGS = _prep_conf(is_marketplace=True)
    payment = payment_factory(external_id=uuid.uuid4())
    # payment.confirm_prepared()
    request = rf.post(
        "",
        content_type="application/json"
    )
    processor = PaymentProcessor(payment=payment)
    assert "shoppingCarts" in processor.get_paywall_context(request=request)


def test_products_if_not_marketplace(getpaid_client, settings, payment_factory, rf):
    settings.GETPAID_BACKEND_SETTINGS = _prep_conf(is_marketplace=False)
    payment = payment_factory(external_id=uuid.uuid4())
    # payment.confirm_prepared()
    request = rf.post(
        "",
        content_type="application/json"
    )
    processor = PaymentProcessor(payment=payment)
    assert "products" in processor.get_paywall_context(request=request)


# PUSH flow
@pytest.mark.parametrize(
    "remote_status,our_status",
    [
        (OrderStatus.COMPLETED, ps.PAID),
        (OrderStatus.WAITING_FOR_CONFIRMATION, ps.PRE_AUTH),
        (OrderStatus.CANCELED, ps.FAILED),
    ],
)
def test_push_flow(
    remote_status,
    our_status,
    payment_factory,
    settings,
    requests_mock,
    rf,
    getpaid_client,
):
    settings.GETPAID_BACKEND_SETTINGS = _prep_conf(confirm_method=cm.PUSH)

    payment = payment_factory(external_id=uuid.uuid4())
    payment.confirm_prepared()

    encoded = json.dumps(
        {
            "order": {
                "orderId": "LDLW5N7MF4140324GUEST000P01",
                "extOrderId": f"{payment.id}",
                "orderCreateDate": "2012-12-31T12:00:00",
                "notifyUrl": "http://tempuri.org/notify",
                "customerIp": "127.0.0.1",
                "merchantPosId": "{POS ID (pos_id)}",
                "description": "My order description",
                "currencyCode": payment.currency,
                "totalAmount": getpaid_client._centify(payment.amount_required),
                "buyer": {
                    "email": "john.doe@example.org",
                    "phone": "111111111",
                    "firstName": "John",
                    "lastName": "Doe",
                    "language": "en",
                },
                "payMethod": {"type": "PBL", },
                "products": [
                    {
                        "name": "Product 1",
                        "unitPrice": getpaid_client._centify(payment.amount_required),
                        "quantity": "1",
                    }
                ],
                "status": remote_status,
            },
            "localReceiptDateTime": "2016-03-02T12:58:14.828+01:00",
            "properties": [{"name": "PAYMENT_ID", "value": "151471228"}],
        },
        default=str,
    )
    sig = hashlib.md5(
        f"{encoded}{getpaid_client.second_key}".encode("utf-8")
    ).hexdigest()
    compiled = f"sender=checkout;signature={sig};algorithm=MD5;content=DOCUMENT"

    request = rf.post(
        "",
        content_type="application/json",
        data=encoded,
        HTTP_X_OPENPAYU_SIGNATURE=compiled,
    )
    payment.handle_paywall_callback(request)
    assert payment.status == our_status
