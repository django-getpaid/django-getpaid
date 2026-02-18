"""Payment views for django-getpaid v3."""

import logging

import swapper
from django import http
from django.http import HttpRequest
from django.shortcuts import get_object_or_404
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from django.views.generic import CreateView, RedirectView

from .adapters import call_processor_verify_callback
from .exceptions import GetPaidException
from .forms import PaymentMethodForm

logger = logging.getLogger(__name__)


class CreatePaymentView(CreateView):
    model = swapper.load_model('getpaid', 'Payment')
    form_class = PaymentMethodForm

    def get(self, request, *args, **kwargs):
        return http.HttpResponseNotAllowed(['POST'])

    def form_valid(self, form):
        payment = form.save()
        return payment._get_processor().prepare_transaction(
            request=self.request, view=self
        )

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
    """Handle paywall callback via PUSH flow."""

    def post(self, request: HttpRequest, pk, *args, **kwargs):
        Payment = swapper.load_model('getpaid', 'Payment')
        payment = get_object_or_404(Payment, pk=pk)
        processor = payment._get_processor()
        try:
            call_processor_verify_callback(processor, request)
        except GetPaidException:
            logger.warning('Callback verification failed for payment %s', pk)
            return http.HttpResponseForbidden('Callback verification failed')
        return processor.handle_paywall_callback(request, *args, **kwargs)


callback = csrf_exempt(CallbackDetailView.as_view())
