"""Tests for order-ownership validation in CreatePaymentView."""

import logging

import pytest
import swapper
from django.contrib.auth.models import User

pytestmark = pytest.mark.django_db

Order = swapper.load_model('getpaid', 'Order')

BACKEND_SETTINGS = {'getpaid.backends.dummy': {'paywall_method': 'REST'}}


@pytest.fixture(autouse=True)
def _dummy_rest_backend(settings):
    settings.GETPAID_BACKEND_SETTINGS = BACKEND_SETTINGS


def _post_payment(client, order):
    return client.post(
        '/payments/new/',
        data={
            'order': order.pk,
            'amount_required': '1.00',
            'description': 'x',
            'currency': 'EUR',
            'backend': 'dummy',
        },
    )


@pytest.fixture
def owner():
    return User.objects.create(username='owner')


@pytest.fixture
def intruder():
    return User.objects.create(username='intruder')


class TestOrderOwnership:
    @pytest.fixture(autouse=True)
    def _order_owned_by_owner(self, monkeypatch, owner):
        # The example Order model has no user field; simulate one so the
        # default ownership check kicks in.
        monkeypatch.setattr(
            Order,
            'user',
            property(lambda self: User.objects.get(username='owner')),
            raising=False,
        )

    def test_owner_can_create_payment(self, client, order_factory, owner):
        order = order_factory()
        client.force_login(owner)

        response = _post_payment(client, order)

        assert response.status_code == 302

    def test_non_owner_is_rejected_with_403(
        self, client, order_factory, intruder
    ):
        order = order_factory()
        client.force_login(intruder)

        response = _post_payment(client, order)

        assert response.status_code == 403
        assert not order.payments.exists()


class TestOwnerAttributeSupport:
    def test_owner_attribute_is_honored(
        self, client, order_factory, monkeypatch, intruder
    ):
        monkeypatch.setattr(
            Order,
            'owner',
            property(lambda self: User.objects.get(username='owner')),
            raising=False,
        )
        User.objects.create(username='owner')
        order = order_factory()
        client.force_login(intruder)

        response = _post_payment(client, order)

        assert response.status_code == 403


class TestOrdersWithoutOwnership:
    def test_allowed_but_warns_once(
        self, client, order_factory, owner, caplog, monkeypatch
    ):
        from getpaid import views as getpaid_views

        monkeypatch.setattr(
            getpaid_views, '_ownership_warning_emitted', False
        )
        client.force_login(owner)

        with caplog.at_level(logging.WARNING, logger='getpaid.views'):
            first = _post_payment(client, order_factory())
            second = _post_payment(client, order_factory())

        assert first.status_code == 302
        assert second.status_code == 302
        ownership_warnings = [
            record
            for record in caplog.records
            if 'ownership' in record.getMessage().lower()
        ]
        assert len(ownership_warnings) == 1


class TestFormQuerysetInjection:
    def test_view_can_scope_order_queryset(
        self, client, order_factory, owner
    ):
        """A view-provided queryset restricts which orders can be paid."""
        from getpaid.forms import PaymentMethodForm

        order = order_factory()
        other = order_factory()

        form = PaymentMethodForm(
            data={
                'order': other.pk,
                'amount_required': '1.00',
                'description': 'x',
                'currency': 'EUR',
                'backend': 'dummy',
            },
            order_queryset=Order.objects.filter(pk=order.pk),
        )

        assert not form.is_valid()
        assert 'order' in form.errors
