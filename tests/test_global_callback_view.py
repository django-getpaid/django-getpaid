"""Functional tests for the paymentless/global callback view.

Gateways like Stripe deliver every webhook to one Dashboard-configured URL
with no payment pk. ``BackendCallbackView`` resolves the Payment from the
event body via the backend processor's ``extract_callback_correlation`` hook,
then runs the same locked machinery as the per-payment ``CallbackDetailView``.
"""

import json
import uuid

import pytest

from getpaid.backends.dummy.processor import (
    PaymentProcessor as DummyPaymentProcessor,
)
from getpaid.registry import registry
from getpaid.types import PaymentStatus as ps

pytestmark = pytest.mark.django_db


class _GlobalDummyProcessor(DummyPaymentProcessor):
    """Dummy backend that also supports paymentless callbacks.

    Reuses the dummy FSM drive (``new_status``) but adds the correlation
    hook the global view needs, reading the handles straight off the body.
    """

    slug = 'global_dummy'

    @classmethod
    def extract_callback_correlation(cls, data, headers):
        correlation = {}
        if data.get('payment_id'):
            correlation['payment_id'] = str(data['payment_id'])
        if data.get('external_id'):
            correlation['external_id'] = str(data['external_id'])
        return correlation or None


@pytest.fixture(autouse=True)
def _debug_mode(settings):
    # The dummy backend is unsigned; unsigned callbacks are only allowed in
    # DEBUG mode (pytest-django forces DEBUG=False otherwise).
    settings.DEBUG = True


@pytest.fixture(autouse=True)
def _register_global_dummy():
    if _GlobalDummyProcessor.slug not in registry:
        registry.register(_GlobalDummyProcessor)
    yield
    registry.unregister(_GlobalDummyProcessor.slug)


@pytest.fixture
def prepared_payment(payment_factory):
    return payment_factory(
        status=ps.PREPARED,
        backend=_GlobalDummyProcessor.slug,
        external_id=str(uuid.uuid4()),
    )


def _url(backend):
    return f'/payments/callback/{backend}/'


def _post(client, backend, body):
    return client.post(
        _url(backend),
        data=json.dumps(body),
        content_type='application/json',
    )


class TestGlobalCallbackHappyPath:
    def test_resolves_by_payment_id_and_drives_fsm(
        self, client, prepared_payment
    ):
        response = _post(
            client,
            'global_dummy',
            {'payment_id': str(prepared_payment.pk), 'new_status': 'paid'},
        )

        assert response.status_code == 200
        prepared_payment.refresh_from_db()
        assert prepared_payment.status == ps.PAID

    def test_resolves_by_external_id_when_no_payment_id(
        self, client, prepared_payment
    ):
        # Refund / review events carry only the PaymentIntent id, which the
        # adapter matches against Payment.external_id.
        response = _post(
            client,
            'global_dummy',
            {
                'external_id': prepared_payment.external_id,
                'new_status': 'paid',
            },
        )

        assert response.status_code == 200
        prepared_payment.refresh_from_db()
        assert prepared_payment.status == ps.PAID

    def test_locks_resolved_payment_row(
        self, client, prepared_payment, monkeypatch
    ):
        from django.db.models import QuerySet

        locked_models = []
        original = QuerySet.select_for_update

        def spy(qs, *args, **kwargs):
            locked_models.append(qs.model.__name__)
            return original(qs, *args, **kwargs)

        monkeypatch.setattr(QuerySet, 'select_for_update', spy)

        response = _post(
            client,
            'global_dummy',
            {'payment_id': str(prepared_payment.pk), 'new_status': 'paid'},
        )

        assert response.status_code == 200
        assert type(prepared_payment).__name__ in locked_models


class TestGlobalCallbackResolutionFailures:
    def test_unknown_backend_returns_404(self, client):
        response = _post(client, 'no_such_backend', {'payment_id': 'x'})
        assert response.status_code == 404

    def test_backend_without_correlation_hook_returns_404(self, client):
        from tests.tools import Plugin

        if Plugin.slug not in registry:
            registry.register(Plugin)
        try:
            response = _post(client, Plugin.slug, {'payment_id': 'x'})
            assert response.status_code == 404
        finally:
            registry.unregister(Plugin.slug)

    def test_no_matching_payment_is_acked_with_200(self, client):
        # Uncorrelatable / foreign traffic must be acked so the gateway stops
        # retrying (Stripe retries on non-2xx).
        response = _post(
            client,
            'global_dummy',
            {'payment_id': str(uuid.uuid4()), 'new_status': 'paid'},
        )
        assert response.status_code == 200
        assert b'no matching payment' in response.content.lower()

    def test_none_correlation_is_acked_with_200(self, client):
        response = _post(client, 'global_dummy', {'new_status': 'paid'})
        assert response.status_code == 200


class TestGlobalCallbackErrorHandling:
    def test_malformed_json_returns_400(self, client, prepared_payment):
        response = client.post(
            _url('global_dummy'),
            data='{not-json',
            content_type='application/json',
        )
        assert response.status_code == 400
        prepared_payment.refresh_from_db()
        assert prepared_payment.status == ps.PREPARED

    def test_duplicate_is_acked_with_200(self, client, prepared_payment):
        body = {'payment_id': str(prepared_payment.pk), 'new_status': 'paid'}
        first = _post(client, 'global_dummy', body)
        assert first.status_code == 200

        late = _post(
            client,
            'global_dummy',
            {'payment_id': str(prepared_payment.pk), 'new_status': 'failed'},
        )
        assert late.status_code == 200
        assert b'already processed' in late.content.lower()
        prepared_payment.refresh_from_db()
        assert prepared_payment.status == ps.PAID

    def test_verification_failure_returns_403(
        self, client, prepared_payment, monkeypatch
    ):
        from getpaid import views as getpaid_views
        from getpaid.exceptions import InvalidCallbackError

        def failing_security(processor, request):
            raise InvalidCallbackError('bad signature')

        monkeypatch.setattr(
            getpaid_views, 'enforce_callback_security', failing_security
        )

        response = _post(
            client,
            'global_dummy',
            {'payment_id': str(prepared_payment.pk), 'new_status': 'paid'},
        )
        assert response.status_code == 403
