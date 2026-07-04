import json

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


class TestHealthCheck:
    """Tests for the /payments/health/ health check endpoint."""

    def test_health_check_returns_200(self, client):
        """Health check returns 200 OK with JSON payload."""
        response = client.get('/payments/health/')
        assert response.status_code == 200
        data = json.loads(response.content)
        assert data['status'] == 'ok'
        assert data['service'] == 'getpaid'
        assert 'version' in data

    def test_health_check_does_not_require_auth(self, client):
        """Health check is public — no authentication required."""
        response = client.get('/payments/health/')
        assert response.status_code == 200

    def test_health_check_version_matches_package(self, client):
        """Health check version string matches __version__."""
        import getpaid

        response = client.get('/payments/health/')
        data = json.loads(response.content)
        assert data['version'] == getpaid.__version__


class TestFallbackViewDefaultTemplates:
    """SuccessView/FailureView must render with package-shipped templates.

    The example project overrides getpaid/payment_success.html and
    getpaid/payment_failed.html; the package must still work without them.
    """

    APP_DIRS_ONLY_TEMPLATES = [
        {
            'BACKEND': 'django.template.backends.django.DjangoTemplates',
            'DIRS': [],  # no project-level template overrides
            'APP_DIRS': True,
            'OPTIONS': {'context_processors': []},
        }
    ]

    @override_settings(TEMPLATES=APP_DIRS_ONLY_TEMPLATES)
    def test_success_view_renders_default_template(
        self, client, payment_factory
    ):
        payment = payment_factory()

        response = client.get(f'/payments/success/{payment.pk}/')

        assert response.status_code == 200
        assert response.templates[0].name == 'getpaid/payment_success.html'
        assert str(payment.pk).encode() in response.content

    @override_settings(TEMPLATES=APP_DIRS_ONLY_TEMPLATES)
    def test_failure_view_renders_default_template(
        self, client, payment_factory
    ):
        payment = payment_factory()

        response = client.get(f'/payments/failure/{payment.pk}/')

        assert response.status_code == 200
        assert response.templates[0].name == 'getpaid/payment_failed.html'
        assert str(payment.pk).encode() in response.content
