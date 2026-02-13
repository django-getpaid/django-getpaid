"""Tests for BaseProcessor and security features."""

from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest
import swapper
from django.http import HttpResponse
from django.test import RequestFactory

from getpaid.exceptions import GetPaidException
from getpaid.processor import BaseProcessor
from getpaid.views import CallbackDetailView


class ConcreteProcessor(BaseProcessor):
    """Minimal concrete processor for testing."""

    display_name = 'Test'
    accepted_currencies = ['EUR']
    slug = 'test_proc'

    def prepare_transaction(self, request=None, view=None, **kwargs):
        return MagicMock(status_code=302, url='/redirect')


class VerifyingProcessor(ConcreteProcessor):
    """Processor that implements verify_callback."""

    slug = 'verifying_proc'

    def verify_callback(self, request, **kwargs):
        sig = request.headers.get('X-Signature', '')
        if sig != 'valid-signature':
            raise GetPaidException('Invalid callback signature')


class TestVerifyCallback:
    def test_base_processor_has_verify_callback(self):
        assert hasattr(BaseProcessor, 'verify_callback')

    def test_base_verify_callback_is_noop_by_default(self):
        mock_payment = MagicMock()
        mock_payment.backend = 'test_proc'
        proc = ConcreteProcessor(mock_payment)
        mock_request = MagicMock()
        proc.verify_callback(mock_request)

    def test_custom_verify_callback_rejects_invalid(self):
        mock_payment = MagicMock()
        mock_payment.backend = 'verifying_proc'
        proc = VerifyingProcessor(mock_payment)

        bad_request = MagicMock()
        bad_request.headers = {'X-Signature': 'bad'}

        with pytest.raises(
            GetPaidException, match='Invalid callback signature'
        ):
            proc.verify_callback(bad_request)

    def test_custom_verify_callback_accepts_valid(self):
        mock_payment = MagicMock()
        mock_payment.backend = 'verifying_proc'
        proc = VerifyingProcessor(mock_payment)

        good_request = MagicMock()
        good_request.headers = {'X-Signature': 'valid-signature'}

        proc.verify_callback(good_request)


@pytest.mark.django_db
class TestGetOurBaseurl:
    def test_with_request_uses_request_host(self, rf, settings):
        settings.DEBUG = True
        request = rf.get('/')
        url = BaseProcessor.get_our_baseurl(request)
        assert url.startswith('http')
        assert '://' in url
        assert url.endswith('/')

    def test_without_request_uses_sites_framework(self, settings):
        from django.contrib.sites.models import Site

        Site.objects.update_or_create(
            id=settings.SITE_ID,
            defaults={'domain': 'example.com', 'name': 'Example'},
        )
        settings.DEBUG = False
        url = BaseProcessor.get_our_baseurl(request=None)
        assert 'example.com' in url
        assert url.startswith('https://')
        assert url.endswith('/')

    def test_without_request_no_hardcoded_localhost(self, settings):
        from django.contrib.sites.models import Site

        Site.objects.update_or_create(
            id=settings.SITE_ID,
            defaults={'domain': 'myshop.com', 'name': 'My Shop'},
        )
        url = BaseProcessor.get_our_baseurl(request=None)
        assert '127.0.0.1' not in url

    def test_production_uses_https(self, rf, settings):
        settings.DEBUG = False
        request = rf.get('/')
        url = BaseProcessor.get_our_baseurl(request)
        assert url.startswith('https://')

    def test_debug_uses_http(self, rf, settings):
        settings.DEBUG = True
        request = rf.get('/')
        url = BaseProcessor.get_our_baseurl(request)
        assert url.startswith('http://')


@pytest.mark.django_db
class TestCallbackViewSecurity:
    @pytest.fixture(autouse=True)
    def setup_payment(self):
        from tests.factories import OrderFactory

        self.factory = RequestFactory()
        self.order = OrderFactory()
        Payment = swapper.load_model('getpaid', 'Payment')
        self.payment = Payment.objects.create(
            order=self.order,
            amount_required=Decimal(str(self.order.get_total_amount())),
            currency=self.order.currency,
            description='Test payment',
            backend='getpaid.backends.dummy',
        )

    def test_callback_view_calls_verify_callback(self):
        request = self.factory.post(f'/payments/callback/{self.payment.pk}/')

        mock_processor = MagicMock()
        mock_processor.verify_callback = MagicMock()
        mock_processor.handle_paywall_callback = MagicMock(
            return_value=HttpResponse('OK')
        )

        with patch.object(
            type(self.payment),
            '_get_processor',
            return_value=mock_processor,
        ):
            view = CallbackDetailView()
            view.request = request
            response = view.post(request, pk=self.payment.pk)

        mock_processor.verify_callback.assert_called_once_with(request)
        assert response.status_code == 200

    def test_callback_view_returns_403_on_verify_failure(self):
        request = self.factory.post(f'/payments/callback/{self.payment.pk}/')

        mock_processor = MagicMock()
        mock_processor.verify_callback = MagicMock(
            side_effect=GetPaidException('Bad signature')
        )
        mock_processor.handle_paywall_callback = MagicMock(
            return_value=HttpResponse('OK')
        )

        with patch.object(
            type(self.payment),
            '_get_processor',
            return_value=mock_processor,
        ):
            view = CallbackDetailView()
            view.request = request
            response = view.post(request, pk=self.payment.pk)

        assert response.status_code == 403
        mock_processor.handle_paywall_callback.assert_not_called()

    def test_callback_view_proceeds_when_verify_passes(self):
        request = self.factory.post(f'/payments/callback/{self.payment.pk}/')

        mock_processor = MagicMock()
        mock_processor.verify_callback = MagicMock()
        mock_processor.handle_paywall_callback = MagicMock(
            return_value=HttpResponse('OK', status=200)
        )

        with patch.object(
            type(self.payment),
            '_get_processor',
            return_value=mock_processor,
        ):
            view = CallbackDetailView()
            view.request = request
            response = view.post(request, pk=self.payment.pk)

        mock_processor.verify_callback.assert_called_once_with(request)
        mock_processor.handle_paywall_callback.assert_called_once()
        assert response.status_code == 200
