import json

from django.http import HttpResponse
from django.urls import reverse

from getpaid.processor import BaseProcessor


class PaymentProcessor(BaseProcessor):
    slug = "dummy"
    display_name = "Dummy"
    accepted_currencies = ["PLN", "EUR"]
    method = "POST"
    template_name = "getpaid_dummy_backend/payment_post_form.html"

    def handle_callback(self, request, *args, **kwargs):
        payload = json.loads(request.data)
        if payload["status"] == "OK":
            self.payment.on_success()
        else:
            self.payment.on_failure()

        return HttpResponse("OK")

    def get_redirect_params(self):
        extra_args = {}
        if self.get_setting("confirmation_method", "push").lower() == "push":
            extra_args["callback"] = (
                reverse("getpaid:callback-detail", kwargs=dict(pk=self.payment.pk)),
            )

        return dict(
            payment=self.payment.pk,
            value=self.payment.amount,
            currency=self.payment.currency,
            description=self.payment.description,
            success_url=reverse(
                "getpaid:payment-success", kwargs=dict(pk=self.payment.pk)
            ),
            failure_url=reverse(
                "getpaid:payment-failure", kwargs=dict(pk=self.payment.pk)
            ),
            **extra_args,
        )

    def get_redirect_url(self):
        return reverse("getpaid:dummy:gateway")
