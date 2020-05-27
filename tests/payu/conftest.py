import pytest
from pytest_factoryboy import register

from getpaid.backends.payu.client import Client
from .factories import PaymentFactory

register(PaymentFactory)


@pytest.fixture
def getpaid_client(requests_mock):
    requests_mock.post(
        "/pl/standard/user/oauth/authorize",
        json={
            "access_token": "7524f96e-2d22-45da-bc64-778a61cbfc26",
            "token_type": "bearer",
            "expires_in": 43199,
            "grant_type": "client_credentials",
        },
    )
    yield Client(
        api_url="https://example.com/",
        pos_id=300746,
        second_key="b6ca15b0d1020e8094d9b5f8d163db54",
        oauth_id=300746,
        oauth_secret="2ee86a66e5d97e3fadc400c9f19b065d",
    )
