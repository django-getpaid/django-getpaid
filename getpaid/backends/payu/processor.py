""""
Settings:
    pos_id
    second_key
    client_id
    client_secret
"""
import hashlib
import json
import logging
from collections import OrderedDict
from urllib.parse import urljoin

from django import http
from django.conf import settings
from django.db.transaction import atomic
from django.http import HttpResponse
from django.template.response import TemplateResponse
from django.urls import reverse
from django.utils.http import urlencode
from rest_framework import status as http_status

from getpaid.exceptions import LockFailure
from getpaid.post_forms import PaymentHiddenInputsPostForm
from getpaid.processor import BaseProcessor
from getpaid.types import BackendMethod as bm
from getpaid.types import PaymentStatusResponse

from .callback_handler import PayuCallbackHandler
from .client import Client
from .types import Currency, OrderStatus, ResponseStatus

logger = logging.getLogger(__name__)

key_trans = {
    "unit_price": "unitPrice",
    "first_name": "firstName",
    "last_name": "lastName",
    "order_id": "extOrderId",
    "customer_ip": "customerIp",
    "notify_url": "notifyUrl",
}


class PaymentProcessor(BaseProcessor):
    slug = settings.GETPAID_PAYU_SLUG
    display_name = "PayU"
    accepted_currencies = [c.value for c in Currency]
    ok_statuses = [200, 201, 302]
    method = "REST"  #: Supported modes: REST, POST (not recommended!)
    sandbox_url = "https://secure.snd.payu.com/"
    production_url = "https://secure.payu.com/"
    confirmation_method = "PUSH"  #: PUSH - paywall will send POST request to your server; PULL - you need to check the payment status
    post_form_class = PaymentHiddenInputsPostForm
    post_template_name = "getpaid_payu/payment_post_form.html"
    callback_url_name = "getpaid:callback"
    client_class = Client
    _token = None
    _token_expires = None

    # Specifics

    @classmethod
    def get_paywall_baseurl(cls):
        if cls.get_setting("use_sandbox", True):
            return cls.sandbox_url
        return cls.production_url

    @classmethod
    def get_paywall_method(self):
        return self.get_setting("paywall_method", self.method)

    def get_paywall_context(self, request=None, camelize_keys=False, **kwargs):
        context = {
            "notify_url": self.get_notify_url(),
            "continue_url": self.get_continue_url(),
            "customer_ip": self.get_customer_ip(request),
            "description": self.payment.description,
            "currency": self.payment.currency,
            "amount": self.payment.amount_required,
            "order_id": self.payment.get_unique_id(),
            "buyer": self.payment.get_buyer_info(),
        }

        if self.get_setting("is_marketplace", False):
            context["shopping_carts"] = self.get_shopping_carts()
        else:
            context["products"] = self.get_products()

        return context

    def get_notify_url(self):
        backend_url = settings.GETPAID_BACKEND_HOST
        return urljoin(
            backend_url, reverse(self.callback_url_name, kwargs={"pk": self.payment.pk})
        )

    def get_continue_url(self):
        frontend_url = settings.GETPAID_FRONTEND_HOST
        return self.get_setting("continue_url").format(
            frontend_url=frontend_url, payment_id=self.payment.id
        )

    def get_customer_ip(self, request=None):
        customer_ip = "127.0.0.1"
        if request:
            customer_ip = request.META.get("REMOTE_ADDR", customer_ip)
        return customer_ip

    def get_shopping_carts(self):
        shopping_carts = []
        raw_items = self.payment.get_items()
        for shopping_cart in raw_items:
            products = [
                {key_trans.get(k, k): v for k, v in product.items()}
                for product in shopping_cart["products"]
            ]
            shopping_carts.append({**shopping_cart, "products": products})
        return shopping_carts

    def get_products(self):
        raw_products = self.payment.get_items()
        products = []
        for product in raw_products:
            transformed_product = {key_trans.get(k, k): v for k, v in product.items()}
            products.append(transformed_product)
        return products

    @atomic()
    def prepare_transaction(self, request=None, view=None, **kwargs):
        method = self.get_paywall_method().upper()
        if method == bm.REST:
            try:
                results = self.prepare_lock(request=request, **kwargs)
                response = http.HttpResponseRedirect(results["url"])
            except LockFailure as exc:
                logger.error(exc, extra=getattr(exc, "context", None))
                self.payment.fail()
                response = http.HttpResponseRedirect(
                    reverse("getpaid:payment-failure", kwargs={"pk": self.payment.pk})
                )
            self.payment.save()
            return response
        elif method == bm.POST:
            data = self.get_paywall_context(
                request=request, camelize_keys=True, **kwargs
            )
            data["merchantPosId"] = self.get_setting("pos_id")
            url = urljoin(self.get_paywall_baseurl(), "/api/v2_1/orders")
            form = self.get_form(data)
            return TemplateResponse(
                request=request,
                template=self.get_template_names(view=view),
                context={"form": form, "paywall_url": url},
            )

    def handle_paywall_callback(self, request, **kwargs):
        given_signature, expected_signature = self.get_signatures(request)
        if given_signature == expected_signature:
            data = json.loads(request.body)
            PayuCallbackHandler(self.payment).handle(data)
            return HttpResponse(status=http_status.HTTP_200_OK)
        else:
            logger.error(
                f"Received bad signature for payment {self.payment.id}! "
                f"Got '{given_signature}', expected '{expected_signature}'"
            )

    def prepare_lock(self, request=None, **kwargs):
        results = {}
        params = self.get_paywall_context(request=request, **kwargs)
        response = self.client.new_order(**params)
        results["raw_response"] = self.client.last_response
        self.payment.confirm_prepared()
        self.payment.external_id = results["ext_order_id"] = response.get("orderId", "")
        self.payment.redirect_uri = results["url"] = response.get("redirectUri")
        return results

    def charge(self, **kwargs):
        response = self.client.capture(self.payment.external_id)
        result = {
            "raw_response": self.client.last_response,
            "status_desc": response.get("status", {}).get("statusDesc"),
        }
        if response.get("status", {}).get("statusCode") == ResponseStatus.SUCCESS:
            result["success"] = True

        return result

    def release_lock(self):
        response = self.client.cancel_order(self.payment.external_id)
        status = response.get("status", {}).get("statusCode")
        if status == ResponseStatus.SUCCESS:
            return self.payment.amount_locked

    def get_signatures(self, request):
        payu_header_raw = request.headers.get(
            "OpenPayU-Signature"
        ) or request.headers.get("X-OpenPayU-Signature", "")
        payu_header = {
            k: v for k, v in [i.split("=") for i in payu_header_raw.split(";")]
        }
        algo_name = payu_header.get("algorithm", "MD5")
        given_signature = payu_header.get("signature")
        second_key = self.get_setting("second_key")
        algorithm = getattr(hashlib, algo_name.replace("-", "").lower())

        request_body = request.body.decode()
        expected_signature = algorithm(
            f"{request_body}{second_key}".encode("utf-8")
        ).hexdigest()
        return given_signature, expected_signature

    def fetch_payment_status(self) -> PaymentStatusResponse:
        response = self.client.get_order_info(self.payment.external_id)
        results = {"raw_response": self.client.last_response}
        order_data = response.get("orders", [None])[0]

        status = order_data.get("status")
        if status == OrderStatus.NEW:
            results["callback"] = "confirm_prepared"
        elif status == OrderStatus.PENDING:
            results["callback"] = "confirm_prepared"
        elif status == OrderStatus.CANCELED:
            results["callback"] = "fail"
        elif status == OrderStatus.COMPLETED:
            results["callback"] = "confirm_payment"
        elif status == OrderStatus.WAITING_FOR_CONFIRMATION:
            results["callback"] = "confirm_lock"
        return results

    def prepare_form_data(self, post_data, **kwargs):
        pos_id = self.get_setting("pos_id")
        second_key = self.get_setting("second_key")
        algorithm = self.get_setting("algorithm", "SHA-256").upper()
        hasher = getattr(hashlib, algorithm.replace("-", "").lower())
        encoded = urlencode(OrderedDict(sorted(post_data.items())))
        prepared = f"{encoded}&{second_key}".encode("ascii")
        signature = hasher(prepared).hexdigest()
        post_data[
            "OpenPayu-Signature"
        ] = f"signature={signature};algorithm={algorithm};sender={pos_id}"
        return post_data
