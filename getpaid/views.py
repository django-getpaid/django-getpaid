"""Payment views for django-getpaid v3."""

import json
import logging

import swapper
from django import http
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from django.views.generic import CreateView, TemplateView
from getpaid_core.exceptions import (
    BackendNotFoundError,
    InvalidTransitionError,
)

from .abstracts import _handle_paywall_callback
from .adapters import adapt_callback_request, call_processor_verify_callback
from .bridge import bridge
from .callback_security import enforce_callback_security
from .exceptions import GetPaidException
from .forms import PaymentMethodForm
from .registry import registry

logger = logging.getLogger(__name__)


_ownership_warning_emitted = False


class CreatePaymentView(LoginRequiredMixin, CreateView):
    model = swapper.load_model('getpaid', 'Payment')
    form_class = PaymentMethodForm

    def get(self, request, *args, **kwargs):
        return http.HttpResponseNotAllowed(['POST'])

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['order_queryset'] = self.get_order_queryset()
        return kwargs

    def get_order_queryset(self):
        """Return the queryset of orders eligible for payment.

        Override to scope selectable orders per user, e.g.::

            def get_order_queryset(self):
                return Order.objects.filter(user=self.request.user)

        Returning ``None`` lets the form use all orders (the default).
        """
        return

    def validate_order(self, request, order):
        """Hook validating that the user may initiate payment for the order.

        Called after form validation, before the payment is created.
        Raise :class:`django.core.exceptions.PermissionDenied` to reject.

        Default behavior: when the order object exposes a ``user`` or
        ``owner`` attribute, it must match ``request.user``; otherwise
        the request is rejected with 403. When the order has neither
        attribute, the payment is allowed but a security warning is
        logged once — override this method to enforce ownership for
        such models.
        """
        for attribute in ('user', 'owner'):
            if hasattr(order, attribute):
                if getattr(order, attribute) != request.user:
                    raise PermissionDenied(
                        'You are not allowed to pay for this order.'
                    )
                return
        _warn_missing_order_ownership_once()

    def form_valid(self, form):
        self.validate_order(self.request, form.cleaned_data['order'])
        payment = form.save()
        return payment.prepare_transaction(request=self.request, view=self)

    def form_invalid(self, form):
        return super().form_invalid(form)


def _warn_missing_order_ownership_once() -> None:
    global _ownership_warning_emitted  # noqa: PLW0603
    if _ownership_warning_emitted:
        return
    _ownership_warning_emitted = True
    logger.warning(
        'Order model exposes neither a "user" nor an "owner" attribute; '
        'cross-user payment initiation ownership cannot be validated. '
        'Override CreatePaymentView.validate_order() to enforce it.'
    )


new_payment = CreatePaymentView.as_view()


class FallbackView(TemplateView):
    """Return view from paywall after payment completion/rejection.

    Renders a success or failure template with payment context.
    The payment and order are injected into the template context.
    """

    success = None

    def get_template_names(self):
        if self.success:
            return 'getpaid/payment_success.html'
        return 'getpaid/payment_failed.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        Payment = swapper.load_model('getpaid', 'Payment')
        payment = get_object_or_404(Payment, pk=self.kwargs['pk'])
        context['payment'] = payment
        context['order'] = payment.order
        return context


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
        try:
            with transaction.atomic():
                return self._handle_locked_callback(request, pk, **kwargs)
        except json.JSONDecodeError:
            logger.warning(
                'Malformed JSON in callback for payment %s', pk
            )
            return http.HttpResponseBadRequest(b'Malformed JSON payload')
        except InvalidTransitionError:
            # Duplicate or late callback: the event was already applied.
            # Providers retry on non-2xx, so a duplicate must be acked.
            logger.info(
                'Callback for payment %s already processed; acknowledging',
                pk,
            )
            return HttpResponse(b'Already processed')
        except GetPaidException:
            logger.warning('Callback verification failed for payment %s', pk)
            return http.HttpResponseForbidden(b'Callback verification failed')

    def _handle_locked_callback(
        self, request: HttpRequest, pk, **kwargs
    ) -> HttpResponse:
        """Process the callback with the payment row locked for update."""
        Payment = swapper.load_model('getpaid', 'Payment')
        payment = get_object_or_404(
            Payment.objects.select_for_update(), pk=pk
        )
        return _run_locked_callback(request, payment, **kwargs)


callback = csrf_exempt(CallbackDetailView.as_view())


def _run_locked_callback(
    request: HttpRequest, payment, **kwargs
) -> HttpResponse:
    """Verify + apply a callback against an already-locked payment row.

    Shared by the per-payment ``CallbackDetailView`` and the paymentless
    ``BackendCallbackView``: both resolve the payment (by URL pk / by event
    body), then run this — verification gates every state change.
    """
    processor = payment._get_processor()
    enforce_callback_security(processor, request)
    if _uses_semantic_callback(processor):
        return _handle_paywall_callback(
            payment, request, processor=processor, **kwargs,
        )
    call_processor_verify_callback(processor, request)
    return processor.handle_paywall_callback(request, **kwargs)


def _resolve_locked_payment(correlation):
    """Resolve and row-lock the Payment a paymentless webhook refers to.

    ``correlation`` is what the backend's ``extract_callback_correlation``
    returned: our ``payment_id`` (session / intent events) and/or the
    gateway-side ``external_id`` (refund / review events, which carry no
    payment_id). Prefer the pk, then fall back to external_id. Returns
    ``None`` when nothing matches — the caller acks so the gateway stops
    retrying uncorrelatable or foreign traffic.
    """
    if not correlation:
        return None
    Payment = swapper.load_model('getpaid', 'Payment')
    locked = Payment.objects.select_for_update()
    payment_id = correlation.get('payment_id')
    if payment_id:
        try:
            payment = locked.filter(pk=payment_id).first()
        except (ValidationError, ValueError, TypeError):
            # An attacker-supplied handle that is not a valid pk for this
            # model is simply not a match, not a 500.
            payment = None
        if payment is not None:
            return payment
    external_id = correlation.get('external_id')
    if external_id:
        payment = locked.filter(external_id=external_id).first()
        if payment is not None:
            return payment
    return None


class BackendCallbackView(View):
    """Paymentless webhook endpoint, keyed by backend slug in the URL.

    For gateways whose webhook is a single Dashboard-configured URL with no
    payment pk (e.g. Stripe): ``callback/<backend>/``. The backend's processor
    must expose an ``extract_callback_correlation(data, headers)`` classmethod
    returning the handles that locate the local Payment. Once resolved, the
    same locked machinery as :class:`CallbackDetailView` runs — signature
    verification gates every state change, exactly as for the per-payment route
    whose pk is likewise untrusted URL input.
    """

    def post(self, request: HttpRequest, backend, *args, **kwargs):
        try:
            processor_class = registry.get_by_slug(backend)
        except BackendNotFoundError as exc:
            raise Http404(
                f'No payment backend registered for {backend!r}.'
            ) from exc
        extractor = getattr(
            processor_class, 'extract_callback_correlation', None
        )
        if extractor is None:
            raise Http404(
                f'Backend {backend!r} does not support paymentless callbacks.'
            )
        try:
            with transaction.atomic():
                return self._handle_backend_callback(
                    request, extractor, backend, **kwargs
                )
        except json.JSONDecodeError:
            logger.warning(
                'Malformed JSON in paymentless %s callback', backend
            )
            return http.HttpResponseBadRequest(b'Malformed JSON payload')
        except InvalidTransitionError:
            logger.info(
                'Paymentless %s callback already processed; acknowledging',
                backend,
            )
            return HttpResponse(b'Already processed')
        except GetPaidException:
            logger.warning(
                'Paymentless %s callback verification failed', backend
            )
            return http.HttpResponseForbidden(b'Callback verification failed')

    def _handle_backend_callback(
        self, request: HttpRequest, extractor, backend, **kwargs
    ) -> HttpResponse:
        data, headers, _raw_body = adapt_callback_request(request)
        correlation = extractor(data, headers)
        payment = _resolve_locked_payment(correlation)
        if payment is None:
            logger.info(
                'Paymentless %s callback: no payment matched correlation %r',
                backend,
                correlation,
            )
            return HttpResponse(b'No matching payment')
        return _run_locked_callback(request, payment, **kwargs)


backend_callback = csrf_exempt(BackendCallbackView.as_view())


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


def _uses_semantic_callback(processor) -> bool:
    """Return True when the processor implements the core async callback contract."""
    return bridge.is_semantic_callback(processor)


def _get_version() -> str:
    """Return the django-getpaid version string."""
    from . import __version__

    return __version__
