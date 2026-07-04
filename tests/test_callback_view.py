"""Functional tests for CallbackDetailView (locking + error handling)."""

import json
import uuid

import pytest

from getpaid.types import PaymentStatus as ps

pytestmark = pytest.mark.django_db


def _url(payment):
    return f'/payments/callback/{payment.pk}/'


@pytest.fixture(autouse=True)
def _debug_mode(settings):
    # The dummy backend is unsigned; unsigned callbacks are only allowed
    # in DEBUG mode (pytest-django forces DEBUG=False otherwise).
    settings.DEBUG = True


@pytest.fixture
def prepared_payment(payment_factory):
    return payment_factory(status=ps.PREPARED, external_id=str(uuid.uuid4()))


def _post_status(client, payment, new_status):
    return client.post(
        _url(payment),
        data=json.dumps({'new_status': new_status}),
        content_type='application/json',
    )


class TestCallbackHappyPath:
    def test_paid_callback_updates_payment(self, client, prepared_payment):
        response = _post_status(client, prepared_payment, 'paid')

        assert response.status_code == 200
        prepared_payment.refresh_from_db()
        assert prepared_payment.status == ps.PAID
        assert prepared_payment.amount_paid == (
            prepared_payment.amount_required
        )

    def test_preauth_callback_updates_payment(self, client, prepared_payment):
        response = _post_status(client, prepared_payment, 'pre-auth')

        assert response.status_code == 200
        prepared_payment.refresh_from_db()
        assert prepared_payment.status == ps.PRE_AUTH

    def test_callback_locks_payment_row(
        self, client, prepared_payment, monkeypatch
    ):
        """The payment row must be fetched with select_for_update."""
        from django.db.models import QuerySet

        locked_models = []
        original = QuerySet.select_for_update

        def spy(qs, *args, **kwargs):
            locked_models.append(qs.model.__name__)
            return original(qs, *args, **kwargs)

        monkeypatch.setattr(QuerySet, 'select_for_update', spy)

        response = _post_status(client, prepared_payment, 'paid')

        assert response.status_code == 200
        assert type(prepared_payment).__name__ in locked_models


class TestCallbackErrorHandling:
    def test_malformed_json_returns_400(self, client, prepared_payment):
        response = client.post(
            _url(prepared_payment),
            data='{not-json',
            content_type='application/json',
        )

        assert response.status_code == 400
        prepared_payment.refresh_from_db()
        assert prepared_payment.status == ps.PREPARED

    def test_duplicate_callback_is_acked_with_200(
        self, client, prepared_payment
    ):
        """Providers retry on non-2xx; duplicate events must be acked."""
        first = _post_status(client, prepared_payment, 'paid')
        assert first.status_code == 200

        second = _post_status(client, prepared_payment, 'paid')

        assert second.status_code == 200
        prepared_payment.refresh_from_db()
        assert prepared_payment.status == ps.PAID
        # Core treats repeated PAYMENT_CAPTURED as idempotent — the paid
        # amount must not be double-counted.
        assert prepared_payment.amount_paid == (
            prepared_payment.amount_required
        )

    def test_late_conflicting_callback_is_acked_with_200(
        self, client, prepared_payment
    ):
        """A late, no-longer-applicable event is acked, not rejected.

        Providers retry on non-2xx, so an InvalidTransitionError must
        result in HTTP 200 with an 'already processed' body.
        """
        first = _post_status(client, prepared_payment, 'paid')
        assert first.status_code == 200

        late = _post_status(client, prepared_payment, 'failed')

        assert late.status_code == 200
        assert b'already processed' in late.content.lower()
        prepared_payment.refresh_from_db()
        assert prepared_payment.status == ps.PAID

    def test_verification_failure_still_returns_403(
        self, client, prepared_payment, monkeypatch
    ):
        from getpaid import views as getpaid_views
        from getpaid.exceptions import InvalidCallbackError

        def failing_security(processor, request):
            raise InvalidCallbackError('bad signature')

        monkeypatch.setattr(
            getpaid_views,
            'enforce_callback_security',
            failing_security,
        )

        response = _post_status(client, prepared_payment, 'paid')

        assert response.status_code == 403
