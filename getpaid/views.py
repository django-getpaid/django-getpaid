import requests
import swapper
from django import http
from django.conf import settings
from django.core import exceptions
from django.shortcuts import get_object_or_404, resolve_url
from django.template.response import TemplateResponse
from django.urls import reverse
from django.views import View
from django.views.generic import CreateView, RedirectView

from .forms import PaymentMethodForm


class CreatePaymentView(CreateView):
    model = swapper.load_model("getpaid", "Payment")
    form_class = PaymentMethodForm

    def get(self, request, *args, **kwargs):
        """
        This view operates only on POST requests from order view where
        you select payment method
        """
        return http.HttpResponseNotAllowed(["POST"])

    def form_valid(self, form):
        payment = form.save()

        method = payment.get_paywall_method()
        params = payment.get_paywall_params(request=self.request)

        if method.upper() == "GET":
            payment.change_status("in_progress")
            url = payment.get_paywall_url(params)
            return http.HttpResponseRedirect(url)
        elif method.upper() == "POST":
            url = payment.get_paywall_url(params)
            context = self.get_context_data(
                form=payment.get_form(params), gateway_url=url
            )

            return TemplateResponse(
                request=self.request,
                template=payment.get_template_names(view=self),
                context=context,
            )
        elif method.upper() == "REST":
            api_url = payment.get_paywall_url()
            headers = payment.prepare_paywall_headers(params)
            response = requests.post(api_url, data=params, headers=headers)
            if response.status_code == 200:
                payment.change_status("in_progress")
                decoded = payment.handle_paywall_response(response)
                url = payment.get_paywall_url(decoded)
                return http.HttpResponseRedirect(url)
            return http.HttpResponseRedirect(
                reverse("getpaid:payment-failure", kwargs={"pk": str(payment.pk)})
            )
        else:
            raise exceptions.ImproperlyConfigured(
                "Only GET, POST and REST are supported."
            )

    def form_invalid(self, form):
        raise exceptions.PermissionDenied


class FallbackView(RedirectView):
    """
    FallbackView (in form of either SuccessView or FailureView) handles the
    return from payment broker.
    """

    success = None
    permanent = False

    def get_redirect_url(self, *args, **kwargs):
        Payment = swapper.load_model("getpaid", "Payment")

        getpaid_settings = getattr(settings, "GETPAID", {})
        payment = get_object_or_404(Payment, pk=self.kwargs["pk"])
        if self.success:
            payment.on_success()
            url = getattr(getpaid_settings, "SUCCESS_URL", None)
        else:
            payment.on_failure()
            url = getattr(getpaid_settings, "FAILURE_URL", None)

        if url is not None:
            return resolve_url(
                url, pk=payment.order.pk
            )  # we may want to return to the Order summary or smth
        return resolve_url(payment.order.get_return_url(payment, success=self.success))


class SuccessView(FallbackView):
    success = True


class FailureView(FallbackView):
    success = False


class CallbackView(View):
    def post(self, request, pk, *args, **kwargs):
        Payment = swapper.load_model("getpaid", "Payment")
        payment = get_object_or_404(Payment, pk=pk)
        return payment.handle_paywall_callback(request, *args, **kwargs)
