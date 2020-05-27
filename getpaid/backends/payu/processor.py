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
from django_fsm import can_proceed
from getpaid.exceptions import LockFailure
from getpaid.post_forms import PaymentHiddenInputsPostForm
from getpaid.processor import BaseProcessor
from getpaid.types import BackendMethod as bm
from getpaid.types import PaymentStatusResponse

from .client import Client
from .types import Currency, OrderStatus, RefundStatus, ResponseStatus

logger = logging.getLogger(__name__)


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
    client_class = Client
    _token = None
    _token_expires = None

    # Specifics

    def get_our_baseurl(self, request=None):
        if request is None:
            return "http://127.0.0.1/"
        return super().get_our_baseurl(request)

    def prepare_form_data(self, post_data):
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

    # Helper methods

    def get_paywall_context(self, request=None, camelize_keys=False, **kwargs):
        # TODO: configurable buyer info inclusion
        """
        "buyer" is optional
        :param request: request creating the payment
        :return: dict that unpacked will be accepted by :meth:`Client.new_order`
        """
        loc = "127.0.0.1"
        our_baseurl = self.get_our_baseurl(request)
        key_trans = {
            "unit_price": "unitPrice",
            "first_name": "firstName",
            "last_name": "lastName",
            "order_id": "extOrderId",
            "customer_ip": "customerIp",
            "notify_url": "notifyUrl",
        }

        raw_items = self.payment.get_items()

        context = {
            "order_id": self.payment.get_unique_id(),
            "customer_ip": loc if not request else request.META.get("REMOTE_ADDR", loc),
            "description": self.payment.description,
            "currency": self.payment.currency,
            "amount": self.payment.amount_required,
        }

        if self.get_setting("is_marketplace", False):
            shopping_carts = []
            for shopping_cart in raw_items:
                products = [
                    {key_trans.get(k, k): v for k, v in product.items()}
                    for product in shopping_cart["products"]
                ]
                shopping_carts.append({
                    **shopping_cart,
                    "products": products
                })
            context["shoppingCarts"] = shopping_carts
        else:
            products = [
                {key_trans.get(k, k): v for k, v in product.items()}
                for product in raw_items
            ]
            context["products"] = products

        if self.get_setting("confirmation_method", self.confirmation_method) == "PUSH":
            context["notify_url"] = urljoin(
                our_baseurl, reverse("getpaid:callback", kwargs={"pk": self.payment.pk})
            )
        if camelize_keys:
            return {key_trans.get(k, k): v for k, v in context.items()}
        return context

    def get_paywall_method(self):
        return self.get_setting("paywall_method", self.method)

    # Communication with paywall

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
            url = self.get_main_url()
            form = self.get_form(data)
            return TemplateResponse(
                request=request,
                template=self.get_template_names(view=view),
                context={"form": form, "paywall_url": url},
            )

    def handle_paywall_callback(self, request, **kwargs):
        payu_header_raw = request.headers.get(
            "Openpayu-Signature"
        ) or request.headers.get("X-Openpayu-Signature", "")

        if not payu_header_raw:
            return HttpResponse("NO SIGNATURE", status=400)
        payu_header = {
            k: v for k, v in [i.split("=") for i in payu_header_raw.split(";")]
        }
        algo_name = payu_header.get("algorithm", "MD5")
        signature = payu_header.get("signature")
        second_key = self.get_setting("second_key")
        algorithm = getattr(hashlib, algo_name.replace("-", "").lower())

        body = request.body.decode()

        expected_signature = algorithm(
            f"{body}{second_key}".encode("utf-8")
        ).hexdigest()

        if expected_signature == signature:
            data = json.loads(body)

            if "order" in data:
                order_data = data.get("order")
                status = order_data.get("status")
                if status == OrderStatus.COMPLETED:
                    if can_proceed(self.payment.confirm_payment):
                        self.payment.confirm_payment()
                        if can_proceed(self.payment.mark_as_paid):
                            self.payment.mark_as_paid()
                    else:
                        logger.debug(
                            "Cannot confirm payment",
                            extra={
                                "payment_id": self.payment.id,
                                "payment_status": self.payment.status,
                            },
                        )
                elif status == OrderStatus.CANCELED:
                    self.payment.fail()
                elif status == OrderStatus.WAITING_FOR_CONFIRMATION:
                    if can_proceed(self.payment.confirm_lock):
                        self.payment.confirm_lock()
                    else:
                        logger.debug(
                            "Already locked",
                            extra={
                                "payment_id": self.payment.id,
                                "payment_status": self.payment.status,
                            },
                        )
            elif "refund" in data:
                refund_data = data.get("refund")
                status = refund_data.get("status")
                if status == RefundStatus.FINALIZED:
                    amount = refund_data.get("amount") / 100
                    self.payment.confirm_refund(amount)
                    if can_proceed(self.payment.mark_as_refunded):
                        self.payment.mark_as_refunded()
                elif status == RefundStatus.CANCELED:
                    self.payment.cancel_refund()
                    if can_proceed(self.payment.mark_as_paid):
                        self.payment.mark_as_paid()
            self.payment.save()
            return HttpResponse("OK")
        else:
            logger.error(
                f"Received bad signature for payment {self.payment.id}! "
                f"Got '{signature}', expected '{expected_signature}'"
            )
            return HttpResponse(
                "BAD SIGNATURE", status=422
            )  # https://httpstatuses.com/422

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

    def get_main_url(self, data=None) -> str:
        baseurl = self.get_paywall_baseurl()
        return urljoin(baseurl, "/api/v2_1/orders")

    def prepare_lock(self, request=None, **kwargs):
        results = {}
        params = self.get_paywall_context(request=request, **kwargs)
        response = self.client.new_order(**params)
        results["raw_response"] = self.client.last_response
        results["url"] = response.get("redirectUri")
        self.payment.confirm_prepared()
        self.payment.external_id = results["ext_order_id"] = response.get("orderId", "")
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
