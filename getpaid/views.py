"""Payment views for django-getpaid v3."""

import logging

import swapper
from django import http
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from django.views.generic import CreateView, RedirectView

from .callback_security import enforce_callback_security
from .exceptions import GetPaidException
from .forms import PaymentMethodForm
from .runtime import handle_callback_request

logger = logging.getLogger(__name__)


class CreatePaymentView(LoginRequiredMixin, CreateView):
    model = swapper.load_model('getpaid', 'Payment')
    form_class = PaymentMethodForm

    def get(self, request, *args, **kwargs):
        return http.HttpResponseNotAllowed(['POST'])

    def form_valid(self, form):
        payment = form.save()
        return payment.prepare_transaction(request=self.request, view=self)

    def form_invalid(self, form):
        return super().form_invalid(form)


new_payment = CreatePaymentView.as_view()


class FallbackView(RedirectView):
    """Return view from paywall after payment completion/rejection."""

    success = None
    permanent = False

    def get_redirect_url(self, *args, **kwargs):
        Payment = swapper.load_model('getpaid', 'Payment')
        payment = get_object_or_404(Payment, pk=self.kwargs['pk'])
        return payment.get_return_redirect_url(
            request=self.request, success=self.success
        )


class SuccessView(FallbackView):
    success = True


success = SuccessView.as_view()


class FailureView(FallbackView):
    success = False


failure = FailureView.as_view()


class CallbackDetailView(View):
    """Handle paywall callback via PUSH flow.

    This view is csrf_exempt because payment gateways cannot include
    CSRF tokens in their callback requests. Security is provided by:

    1. Backend-specific callback verification in ``verify_callback()``.
    2. Optional per-backend ``callback_ip_allowlist`` checks.
    3. Hard refusal of unsigned backends when ``DEBUG`` is False.

    By default the application-level IP allowlist uses ``REMOTE_ADDR``. If the
    app sits behind a reverse proxy, configure ``GETPAID['CALLBACK_SOURCE_IP_HEADER']``
    and ``GETPAID['CALLBACK_TRUSTED_PROXIES']`` so django-getpaid only trusts
    forwarded client IP data from proxies you control.
    """

    def post(self, request: HttpRequest, pk, *args, **kwargs):
        Payment = swapper.load_model('getpaid', 'Payment')
        payment = get_object_or_404(Payment, pk=pk)
        processor = payment._get_processor()
        try:
            enforce_callback_security(processor, request)
            return handle_callback_request(payment, request, **kwargs)
        except GetPaidException:
            logger.warning('Callback verification failed for payment %s', pk)
            return http.HttpResponseForbidden(b'Callback verification failed')


callback = csrf_exempt(CallbackDetailView.as_view())


class HealthCheckView(View):
    """Simple health check endpoint for the payment subsystem.

    Returns 200 OK with a JSON payload indicating the payment system
    is operational. Useful for Kubernetes liveness/readiness probes
    and monitoring dashboards.

    Does not check downstream dependencies (databases, payment gateways)
    — it only verifies that the payment views are reachable.
    """

    def get(self, request: HttpRequest, *args, **kwargs) -> HttpResponse:
        return http.JsonResponse(
            {
                'status': 'ok',
                'service': 'getpaid',
                'version': _get_version(),
            },
            status=200,
        )


health = HealthCheckView.as_view()


def _get_version() -> str:
    """Return the django-getpaid version string."""
    from . import __version__

    return __version__
