import json
from decimal import Decimal

import httpx
import pytest
import swapper
from django.test import RequestFactory
from getpaid_paynow.client import PaynowClient

from getpaid.types import PaymentStatus as ps
from getpaid.views import callback as callback_view

pytestmark = pytest.mark.django_db

Payment = swapper.load_model('getpaid', 'Payment')


class FakePaynowAsyncClient:
    requests: list[dict] = []

    def __init__(self, *args, **kwargs) -> None:
        self.timeout = kwargs.get('timeout')

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        return None

    async def request(
        self,
        method,
        url,
        *,
        headers=None,
        content=None,
        params=None,
    ):
        self.requests.append(
            {
                'method': method,
                'url': url,
                'headers': headers or {},
                'content': content,
                'params': params,
            }
        )
        request = httpx.Request(
            method=method,
            url=url,
            headers=headers,
            content=content,
            params=params,
        )
        return httpx.Response(
            201,
            json={
                'redirectUrl': 'https://paywall.paynow.pl/pay/PAY-123',
                'paymentId': 'PAY-123',
                'status': 'NEW',
            },
            request=request,
        )


def test_paynow_happy_path_integrates_django_core_and_provider(
    settings,
    payment_factory,
    monkeypatch,
):
    settings.GETPAID_BACKEND_SETTINGS = {
        'paynow': {
            'api_key': 'api-key',
            'signature_key': 'secret-key',
            'continue_url': 'https://merchant.example/return/{payment_id}',
            'timeout': 7.5,
        }
    }
    FakePaynowAsyncClient.requests.clear()
    monkeypatch.setattr(
        'getpaid_paynow.client.httpx.AsyncClient',
        FakePaynowAsyncClient,
    )

    payment = payment_factory(
        backend='paynow',
        currency='PLN',
        amount_required=Decimal('12.34'),
    )

    response = payment.prepare_transaction()

    assert response.status_code == 302
    assert response.url == 'https://paywall.paynow.pl/pay/PAY-123'
    payment.refresh_from_db()
    assert payment.status == ps.PREPARED
    assert payment.external_id == 'PAY-123'

    create_request = FakePaynowAsyncClient.requests[0]
    assert create_request['method'] == 'POST'
    assert create_request['url'] == 'https://api.sandbox.paynow.pl/v3/payments'
    assert json.loads(create_request['content'])['amount'] == 1234
    assert json.loads(create_request['content'])['currency'] == 'PLN'

    payload = {
        'paymentId': 'PAY-123',
        'status': 'CONFIRMED',
        'modifiedAt': '2026-05-27T12:00:00Z',
    }
    raw_body = json.dumps(payload)
    signature = PaynowClient(
        api_key='api-key',
        signature_key='secret-key',
        api_url='https://api.sandbox.paynow.pl',
    )._calculate_notification_signature(raw_body)

    request = RequestFactory().generic(
        'POST',
        f'/payments/callback/{payment.pk}/',
        raw_body,
        content_type='application/json',
        HTTP_SIGNATURE=signature,
    )
    callback_response = callback_view(request, pk=payment.pk)

    assert callback_response.status_code == 200
    payment.refresh_from_db()
    assert payment.status == ps.PAID
    assert payment.amount_paid == Decimal('12.34')
    assert payment.provider_data['paynow_status'] == 'CONFIRMED'
