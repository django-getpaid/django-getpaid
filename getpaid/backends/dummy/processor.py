""""
Settings:
    pos_id
    second_key
    client_id
    client_secret
"""
import json
import logging
import os
from urllib.parse import urljoin

import requests
from django.http import HttpResponse, HttpResponseRedirect
from django.template.response import TemplateResponse
from django.urls import reverse, reverse_lazy
from django_fsm import can_proceed

from getpaid.post_forms import PaymentHiddenInputsPostForm
from getpaid.processor import BaseProcessor
from getpaid.status import PaymentStatus as ps

logger = logging.getLogger(__name__)


class PaymentProcessor(BaseProcessor):
    slug = "dummy"
    display_name = "Dummy"
    accepted_currencies = [
        "PLN",
        "EUR",
    ]
    ok_statuses = [200]
    method = "REST"  # Supported modes: REST, POST, GET
    confirmation_method = "PUSH"  # PUSH or PULL
    post_form_class = PaymentHiddenInputsPostForm
    post_template_name = "dummy/payment_post_form.html"
    _token = None
    standard_url = reverse_lazy("paywall:gateway")
    api_url = reverse_lazy("paywall:api_register")

    def get_paywall_method(self):
        return self.get_setting("paywall_method", self.method)

    def get_confirmation_method(self):
        return self.get_setting("confirmation_method", self.confirmation_method).upper()

    def get_paywall_baseurl(self, request=None, **kwargs):
        if request is None:
            base = os.environ.get("_PAYWALL_URL")
        else:
            base = os.environ["_PAYWALL_URL"] = request.build_absolute_uri("/")
        if self.get_paywall_method() == "REST":
            return urljoin(base, str(self.api_url))
        return urljoin(base, str(self.standard_url))

    def get_params(self):
        base = self.get_paywall_baseurl()
        params = {
            "ext_id": self.payment.id,
            "value": self.payment.amount_required,
            "currency": self.payment.currency,
            "description": self.payment.description,
            "success_url": urljoin(
                base,
                reverse("getpaid:payment-success", kwargs={"pk": str(self.payment.pk)}),
            ),
            "failure_url": urljoin(
                base,
                reverse("getpaid:payment-failure", kwargs={"pk": str(self.payment.pk)}),
            ),
        }
        if self.get_confirmation_method() == "PUSH":
            params["callback"] = urljoin(
                base, reverse("getpaid:callback", kwargs={"pk": str(self.payment.pk)})
            )
        return {k: str(v) for k, v in params.items()}

    # Specifics
    def prepare_transaction(self, request, view=None, **kwargs):
        target_url = self.get_paywall_baseurl(request)
        params = self.get_params()
        method = self.get_paywall_method()
        if method == "REST":
            response = requests.post(target_url, json=params)
            if response.status_code in self.ok_statuses:
                self.payment.confirm_prepared()
                self.payment.save()
            return HttpResponseRedirect(response.json()["url"])
        elif method == "POST":
            self.payment.confirm_prepared()
            self.payment.save()
            form = self.get_form(params)
            return TemplateResponse(
                request=request,
                template=self.get_template_names(view=view),
                context={"form": form, "paywall_url": target_url},
            )
        else:
            # GET payments are a bit tricky. You can either confirm payment as
            # prepared here, or on successful return from paywall.
            self.payment.confirm_prepared()
            self.payment.save()
            return HttpResponseRedirect(target_url)

    def handle_paywall_callback(self, request, **kwargs):
        new_status = json.loads(request.body).get("new_status")
        if new_status is None:
            raise ValueError("Got no status")
        elif new_status == ps.FAILED:
            self.payment.fail()
        elif new_status == ps.PRE_AUTH:
            self.payment.confirm_lock()
        elif new_status == ps.PAID:
            if can_proceed(self.payment.confirm_lock):  # GET flow needs this
                self.payment.confirm_lock()
            if can_proceed(self.payment.confirm_payment):
                self.payment.confirm_payment()
                if can_proceed(self.payment.mark_as_paid):
                    self.payment.mark_as_paid()
                elif can_proceed(self.payment.mark_as_refunded):
                    self.payment.mark_as_refunded()
        else:
            raise ValueError(f"Unhandled new status {new_status}")
        self.payment.save()
        return HttpResponse("OK")

    def fetch_payment_status(self, **kwargs):
        base = self.get_paywall_baseurl()
        response = requests.get(
            urljoin(
                base,
                reverse(
                    "paywall:get_status", kwargs={"pk": str(self.payment.external_id)}
                ),
            )
        )
        if response.status_code not in self.ok_statuses:
            raise Exception("Error occurred!")
        status = response.json()["payment_status"]
        results = {}
        if status == ps.PAID:
            results["callback"] = "confirm_payment"
        elif status == ps.PRE_AUTH:
            results["callback"] = "confirm_lock"
        elif status == ps.PREPARED:
            results["callback"] = "confirm_prepared"
        elif status == ps.FAILED:
            results["callback"] = "fail"
        return results

    def charge(self, amount=None, **kwargs):
        url = urljoin(self.get_paywall_baseurl(), reverse("paywall:api_operate"))
        requests.post(
            url, json={"id": str(self.payment.external_id), "new_status": ps.PAID}
        )

    def release_lock(self, **kwargs):
        url = urljoin(self.get_paywall_baseurl(), reverse("paywall:api_operate"))
        requests.post(
            url, json={"id": str(self.payment.external_id), "new_status": ps.REFUNDED}
        )

    def start_refund(self, amount=None, **kwargs):
        url = urljoin(self.get_paywall_baseurl(), reverse("paywall:api_operate"))
        requests.post(
            url,
            json={
                "id": str(self.payment.external_id),
                "new_status": ps.REFUND_STARTED,
            },
        )

    def cancel_refund(self, **kwargs):
        url = urljoin(self.get_paywall_baseurl(), reverse("paywall:api_operate"))
        requests.post(
            url, json={"id": str(self.payment.external_id), "new_status": ps.PAID}
        )
