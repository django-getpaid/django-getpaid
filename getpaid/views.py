import swapper
from django import http
from django.conf import settings
from django.core import exceptions
from django.shortcuts import get_object_or_404, resolve_url
from django.template.response import TemplateResponse
from django.utils.http import urlencode
from django.views import View
from django.views.generic import CreateView, RedirectView

from .forms import PaymentMethodForm


class CreatePaymentView(CreateView):
    model = swapper.load_model("getpaid", "Payment")
    form_class = PaymentMethodForm

    # template_name = "getpaid/payment_post_form.html"

    def get_form(self, form_class=None):
        if form_class is None:
            form_class = self.get_form_class()
        currency = self.kwargs["currency"]
        return form_class(currency=currency, **self.get_form_kwargs())

    def get(self, request, *args, **kwargs):
        """
        This view operates only on POST requests from order view where
        you select payment method
        """
        return http.HttpResponseNotAllowed(["POST"])

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        return kwargs

    def form_valid(self, form):
        payment = form.save()

        url = payment.get_redirect_url()
        method = payment.get_redirect_method()
        params = payment.get_redirect_params()
        payment.change_status("in_progress")
        if method.upper() == "GET":
            if params:
                url = "{url}?{params}".format(url=url, params=urlencode(params))
            return http.HttpResponseRedirect(url)
        elif method.upper() == "POST":
            context = self.get_context_data(
                form=payment.get_form(params), gateway_url=url
            )

            return TemplateResponse(
                request=self.request,
                # template=self.get_template_names(),
                template=payment.get_template_names(view=self),
                context=context,
            )
        else:
            raise exceptions.ImproperlyConfigured("Only GET and POST supported.")

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
        return resolve_url(
            payment.order.get_redirect_url(payment, success=self.success)
        )


class SuccessView(FallbackView):
    success = True


class FailureView(FallbackView):
    success = False


class CallbackView(View):
    def post(self, request, pk, *args, **kwargs):
        Payment = swapper.load_model("getpaid", "Payment")
        payment = get_object_or_404(Payment, pk=pk)
        return payment.handle_callback(request, *args, **kwargs)
