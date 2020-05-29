import pytest
import swapper
from django.conf import settings

from getpaid.exceptions import PayoutFailure
from getpaid.types import PayoutStatus

SHOP_ID = "shop"

pytestmark = pytest.mark.django_db

Payout = swapper.load_model("getpaid", "Payout")

ERROR_RESPONSE = {
    "status": {
        "statusCode": "BUSINESS_ERROR",
        "severity": "ERROR",
        "code": 8352,
        "codeLiteral": "NOT_ENOUGH_FUNDS",
    }
}

SUCCESS_RESPONSE = {
    "payout": {
        "payoutId": "b3e4fc98c6894239864a9d6941f0fe76",
        "extPayoutId": "PAYOUT23423423423",
        "extCustomerId": "12345678",
        "status": "PENDING",
    },
    "status": {"statusCode": "SUCCESS"},
}


@pytest.fixture
def success_payout_response_mocked(requests_mock):
    response = SUCCESS_RESPONSE
    requests_mock.post(url="/api/v2_1/payouts", json=response, status_code=201)


@pytest.fixture
def failed_payout_response_mocked(requests_mock):
    response = ERROR_RESPONSE
    requests_mock.post(url="/api/v2_1/payouts", json=response, status_code=400)


class TestClient:
    def test_payout(self, getpaid_client, success_payout_response_mocked):
        response = getpaid_client.payout(
            shop_id=SHOP_ID, ext_customer_id=None, amount=None, description=None,
        )
        assert "payout" in response


class TestModel:
    def test_success_status(self, oauth_mocked, success_payout_response_mocked):
        payout = Payout.objects.create(
            shop_id=SHOP_ID, backend=settings.GETPAID_PAYU_SLUG
        )
        payout.start_payout()
        payout = Payout.objects.get()
        assert payout.status == PayoutStatus.SUCCESS
        assert payout.external_id == SUCCESS_RESPONSE["payout"]["payoutId"]

    def test_failed_status(self, oauth_mocked, failed_payout_response_mocked):
        payout = Payout.objects.create(
            shop_id=SHOP_ID, backend=settings.GETPAID_PAYU_SLUG
        )
        with pytest.raises(PayoutFailure):
            payout.start_payout()
        payout = Payout.objects.get()
        assert payout.status == PayoutStatus.FAILED
        assert payout.failed_code == str(ERROR_RESPONSE["status"]["code"])

    def test_require_fields_if_marketplace(
        self, settings, getpaid_client, success_payout_response_mocked
    ):
        getpaid_client.is_marketplace = True
        slug = settings.GETPAID_PAYU_SLUG
        default_settings = settings.GETPAID_BACKEND_SETTINGS[slug]
        setting_before = settings.GETPAID_BACKEND_SETTINGS[slug]
        settings.GETPAID_BACKEND_SETTINGS[slug] = {
            **default_settings,
            "is_marketplace": True,
        }
        with pytest.raises(AssertionError):
            getpaid_client.payout(shop_id=SHOP_ID)
        settings.GETPAID_BACKEND_SETTINGS[slug] = setting_before
