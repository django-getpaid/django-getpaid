from datetime import datetime
from decimal import Decimal
from urllib.parse import urljoin, urlencode

from django.conf import settings


def _prep_conf() -> dict:
    default_settings = settings.GETPAID_BACKEND_SETTINGS[settings.GETPAID_PAYU_SLUG]
    return {settings.GETPAID_PAYU_SLUG: {**default_settings, "is_marketplace": True}}


def test_verified_submerchant_status(getpaid_client, requests_mock):
    ext_id = "test123"
    url = urljoin(
        getpaid_client.api_url,
        f"/api/v2_1/customers/ext/{ext_id}/status?currencyCode=PLN",
    )
    requests_mock.get(
        url,
        json={
            "customerVerificationStatus": "Verified",
            "name": "Example Company",
            "taxId": "123123123",
            "regon": "123123123",
        },
    )
    status = getpaid_client.submerchant_status(ext_customer_id=ext_id)
    assert status["customerVerificationStatus"] == "Verified"


def test_not_verified_submerchant_status(getpaid_client, requests_mock):
    ext_id = "test123"
    url = urljoin(
        getpaid_client.api_url,
        f"/api/v2_1/customers/ext/{ext_id}/status?currencyCode=PLN",
    )
    requests_mock.get(
        url,
        json={
            "customerVerificationStatus": "NotVerified",
            "name": "Example Company",
            "taxId": "123123123",
            "regon": "123123123",
        },
    )
    status = getpaid_client.submerchant_status(ext_customer_id=ext_id)
    assert status["customerVerificationStatus"] == "NotVerified"


def test_submerchant_balance(getpaid_client, requests_mock):
    ext_id = "test123"
    url = urljoin(
        getpaid_client.api_url,
        f"/api/v2_1/customers/ext/{ext_id}/balances?currencyCode=PLN",
    )
    requests_mock.get(
        url,
        json={
            "balance": {"availableAmount": "5494", "totalAmount": "5500"},
            "status": {"statusCode": "SUCCESS"},
        },
    )
    response = getpaid_client.submerchant_balance(ext_customer_id=ext_id)
    assert response["balance"]["availableAmount"] == Decimal("54.94")
    assert response["balance"]["totalAmount"] == Decimal("55.00")


def test_submerchant_operations(getpaid_client, requests_mock):
    date_from = datetime(2020, 1, 1, 10, 30)
    date_to = datetime(2020, 1, 31, 10, 30)

    ext_id = "test123"
    url = urljoin(
        getpaid_client.api_url, f"/api/v2_1/customers/ext/{ext_id}/operations"
    )
    url += "?" + urlencode(
        {"currencyCode": "PLN", "eventDateFrom": date_from.isoformat(), "eventDateTo": date_to.isoformat(),}
    )
    requests_mock.get(
        url,
        json={
            "operations": [
                {
                    "type": "PAYMENT_RECEIVED",
                    "amount": "1500",
                    "currencyCode": "PLN",
                    "description": "operation description",
                    "status": "COMPLETED",
                    "creationDate": "2016-04-20T11:05:54+02:00",
                    "eventDate": "2016-04-20T12:05:54+02:00",
                    "details": {
                        "orderId": "CWDBL3KD6G170110GUEST000P01",
                        "extOrderId": "105877825874b0c0b47a0",
                        "counterparties": [
                            {
                                "extCustomerId": "35463545",
                                "name": "Alice",
                                "email": "alice@email.com",
                                "products": [
                                    {
                                        "name": "product-x",
                                        "unitPrice": "1500",
                                        "quantity": "1",
                                    }
                                ],
                            }
                        ],
                        "funds": [],
                    },
                }
            ],
            "pageResponse": {"records": "1", "size": "1", "pageCount": "1"},
        },
    )
    response = getpaid_client.submerchant_operations(
        ext_customer_id=ext_id, date_from=date_from, date_to=date_to
    )
    operations = response["operations"]
    assert response["pageResponse"]["size"] == "1"
    assert operations[0]["amount"] == Decimal("15.00")
    assert operations[0]["status"] == "COMPLETED"
    product = operations[0]["details"]["counterparties"][0]["products"][0]
    assert product["unitPrice"] == Decimal("15.00")
