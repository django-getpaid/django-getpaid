import json
import uuid
from typing import Union

import requests
from django import http
from django.core.exceptions import ImproperlyConfigured
from django.http import HttpResponse, HttpResponseRedirect
from django.template.response import TemplateResponse
from django.urls import reverse

from getpaid.processor import BaseProcessor


class PaymentProcessor(BaseProcessor):
    slug = "dummy"
    display_name = "Dummy"
    accepted_currencies = ["PLN", "EUR"]
    method = "POST"
    template_name = "getpaid_dummy_backend/payment_post_form.html"

    def get_paywall_method(self):
        return self.get_setting("method") or self.method

    def get_template_names(self, view=None) -> list:
        template_name = self.get_setting("POST_TEMPLATE")
        if template_name is None:
            template_name = self.optional_config.get("POST_TEMPLATE")
        if template_name is None:
            template_name = self.template_name
        if template_name is None and hasattr(view, "get_template_names"):
            return view.get_template_names()
        if template_name is None:
            raise ImproperlyConfigured("Couldn't determine template name!")
        return [template_name]

    def get_form(self, post_data):
        from getpaid.forms import PaymentHiddenInputsPostForm

        return PaymentHiddenInputsPostForm(items=post_data)

    def prepare_paywall_headers(self, params):
        token = uuid.uuid4()  # do some authentication stuff
        return {"Authorization": f"Bearer {token}"}

    def handle_paywall_response(self, response):
        # do some handling, maybe update payment status
        return {}

    def process_payment(
        self, request, view
    ) -> Union[HttpResponseRedirect, TemplateResponse]:
        method = self.get_paywall_method()
        params = self.get_paywall_params(request=request)

        if method.upper() == "GET":
            self.payment.change_status("in_progress")
            url = self.get_paywall_url(params)
            return http.HttpResponseRedirect(url)
        elif method.upper() == "POST":
            url = self.get_paywall_url(params)
            context = view.get_context_data(form=self.get_form(params), paywall_url=url)

            return TemplateResponse(
                request=request,
                template=self.get_template_names(view=self),
                context=context,
            )
        elif method.upper() == "REST":
            api_url = self.get_paywall_url()
            headers = self.prepare_paywall_headers(params)
            response = requests.post(api_url, data=params, headers=headers)
            if response.status_code in self.ok_statuses:
                self.payment.change_status("in_progress")
                decoded = self.handle_paywall_response(response)
                url = self.get_paywall_url(decoded)
                return http.HttpResponseRedirect(url)
            return http.HttpResponseRedirect(
                reverse("getpaid:payment-failure", kwargs={"pk": str(self.payment.pk)})
            )
        else:
            raise ImproperlyConfigured("Only GET, POST and REST are supported.")

    def handle_paywall_callback(self, request, *args, **kwargs):
        payload = json.loads(request.body)
        if payload["status"] == "OK":
            self.payment.on_success()
        else:
            self.payment.on_failure()

        return HttpResponse("OK")

    def get_paywall_params(self, request) -> dict:
        extra_args = {}
        if self.get_setting("confirmation_method", "push").lower() == "push":
            extra_args["callback"] = request.build_absolute_uri(
                reverse(
                    f"getpaid:{self.slug}:callback", kwargs={"pk": self.payment.pk}
                ),
            )

        return dict(
            payment=self.payment.pk,
            value=self.payment.amount_required,
            currency=self.payment.currency,
            description=self.payment.description,
            success_url=request.build_absolute_uri(
                reverse("getpaid:payment-success", kwargs={"pk": self.payment.pk})
            ),
            failure_url=request.build_absolute_uri(
                reverse("getpaid:payment-failure", kwargs={"pk": self.payment.pk})
            ),
            **extra_args,
        )

    def get_paywall_url(self, *args, **kwargs):
        return self.get_setting("gateway")
