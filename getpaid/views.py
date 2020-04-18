import swapper
from django import http
from django.shortcuts import get_object_or_404
from django.views import View
from django.views.decorators.csrf import csrf_exempt
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
        return payment.prepare_transaction(request=self.request, view=self)

    def form_invalid(self, form):
        return super().form_invalid(form)


new_payment = CreatePaymentView.as_view()


class FallbackView(RedirectView):
    """
    This view (in form of either SuccessView or FailureView) can be used as
    general return view from paywall after completing/rejecting the payment.
    Final url is returned by :meth:`getpaid.models.AbstractPayment.get_return_redirect_url`
    which allows for customization.
    """

    success = None
    permanent = False

    def get_redirect_url(self, *args, **kwargs):
        Payment = swapper.load_model("getpaid", "Payment")
        payment = get_object_or_404(Payment, pk=self.kwargs["pk"])

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
    """
    This view can be used if paywall supports setting callback url with payment data.
    The flow is then passed to :meth:`getpaid.models.AbstractPayment.handle_paywall_callback`.
    """

    def post(self, request, pk, *args, **kwargs):
        Payment = swapper.load_model("getpaid", "Payment")
        payment = get_object_or_404(Payment, pk=pk)
        return payment.handle_paywall_callback(request, *args, **kwargs)


callback = csrf_exempt(CallbackDetailView.as_view())
