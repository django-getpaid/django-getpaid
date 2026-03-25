import pytest
from django.conf import settings
from django.contrib.auth.models import User
from django.test import override_settings

pytestmark = pytest.mark.django_db


@override_settings(
    GETPAID_BACKEND_SETTINGS={
        'getpaid.backends.dummy': {'paywall_method': 'REST'}
    }
)
def test_create_payment_view_rejects_anonymous_post(client, order_factory):
    order = order_factory()

    response = client.post(
        '/payments/new/',
        data={
            'order': order.pk,
            'amount_required': '1.00',
            'description': 'Tampered description',
            'currency': 'USD',
            'backend': 'dummy',
        },
    )

    assert response.status_code == 302
    assert settings.LOGIN_URL in response.url


@override_settings(
    GETPAID_BACKEND_SETTINGS={
        'getpaid.backends.dummy': {'paywall_method': 'REST'}
    }
)
def test_create_payment_view_allows_authenticated_post(client, order_factory):
    order = order_factory()
    user = User.objects.create(username='tester')
    client.force_login(user)

    response = client.post(
        '/payments/new/',
        data={
            'order': order.pk,
            'amount_required': '1.00',
            'description': 'Tampered description',
            'currency': 'USD',
            'backend': 'dummy',
        },
    )

    assert response.status_code == 302
