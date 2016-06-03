# coding: utf8
import logging

from django.conf import settings
from django.utils import six
from django.http import HttpResponse, HttpResponseBadRequest
from django.views.generic import View
from django.shortcuts import redirect, get_object_or_404
from django.forms import ValidationError
from django.apps import apps


from getpaid.backends.epaydk import PaymentProcessor
from getpaid.signals import order_additional_validation
from getpaid.utils import qs_to_ordered_params
from .forms import EpaydkOnlineForm, EpaydkCancellForm

if six.PY3:
    unicode = str
logger = logging.getLogger(__name__)


class CallbackView(View):
    """
    This View answers on Epay.dk online request that is acknowledge of payment
    status change.

    The most important logic of this view is delegated
    to ``PaymentProcessor.online()`` method.

    """
    http_method_names = ['get', ]

    def get(self, request, *args, **kwargs):

        cb_secret_path = PaymentProcessor\
            .get_backend_setting('callback_secret_path', '')
        if cb_secret_path:
            if not kwargs.get('secret_path', ''):
                logger.debug("empty secret path")
                return HttpResponseBadRequest('400 Bad Request')

            if cb_secret_path != kwargs.get('secret_path', ''):
                logger.debug("invalid secret path")
                return HttpResponseBadRequest('400 Bad Request')

        form = EpaydkOnlineForm(request.GET)
        if form.is_valid():
            params = qs_to_ordered_params(request.META['QUERY_STRING'])
            if PaymentProcessor.is_received_request_valid(params):
                try:
                    PaymentProcessor.confirmed(form.cleaned_data)
                    return HttpResponse('OK')
                except AssertionError as exc:
                    logger.error("PaymentProcessor.confirmed raised"
                                 " AssertionError: %s", exc, exc_info=1)
            else:
                logger.error("MD5 hash check failed")
        logger.error('CallbackView received invalid request')
        logger.debug("GET: %s", request.GET)
        logger.debug("form errors: %s", form.errors)
        return HttpResponseBadRequest('400 Bad Request')


class AcceptView(View):
    """
    This view is called after the payment is submitted for processing.
    Redirects to GETPAID_SUCCESS_URL_NAME if it's defined
    otherwise to getpaid:success-fallback.
    """

    http_method_names = ['get', ]

    def get(self, request):
        Payment = apps.get_model('getpaid', 'Payment')
        form = EpaydkOnlineForm(request.GET)
        if not form.is_valid():
            logger.debug("EpaydkOnlineForm not valid")
            logger.debug("form errors: %s", form.errors)
            return HttpResponseBadRequest("Bad request")

        params = qs_to_ordered_params(request.META['QUERY_STRING'])
        if not PaymentProcessor.is_received_request_valid(params):
            logger.error("MD5 hash check failed")
            return HttpResponseBadRequest("Bad request")

        payment = get_object_or_404(Payment,
                                    id=form.cleaned_data['orderid'])
        try:
            order_additional_validation\
                .send(sender=self, request=self.request,
                      order=payment.order,
                      backend=PaymentProcessor.BACKEND)
        except ValidationError:
            logger.debug("order_additional_validation raised ValidationError")
            return HttpResponseBadRequest("Bad request")

        try:
            PaymentProcessor.accepted_for_processing(payment_id=payment.id)
        except AssertionError as exc:
            logger.error("PaymentProcessor.accepted_for_processing"
                         " raised AssertionError %s", exc, exc_info=1)
            return HttpResponseBadRequest("Bad request")

        url_name = getattr(settings, 'GETPAID_SUCCESS_URL_NAME', None)
        if url_name:
            return redirect(url_name, pk=payment.order.pk)
        return redirect('getpaid:success-fallback', pk=payment.pk)


class CancelView(View):
    """
    This view is called after the payment is submitted for processing.
    Redirects to GETPAID_FAILURE_URL_NAME if it's defined
    otherwise to getpaid:failure-fallback.
    """
    http_method_names = ['get', ]

    def get(self, request):
        """
        Receives params: orderid as int payment id and error as negative int.
        @warning: epay.dk doesn't send hash param!
        """
        Payment = apps.get_model('getpaid', 'Payment')
        form = EpaydkCancellForm(request.GET)
        if not form.is_valid():
            logger.debug("EpaydkCancellForm not valid")
            logger.debug("form errors: %s", form.errors)
            return HttpResponseBadRequest("Bad request")

        payment = get_object_or_404(Payment, id=form.cleaned_data['orderid'])

        try:
            order_additional_validation\
                .send(sender=self, request=self.request,
                      order=payment.order,
                      backend=PaymentProcessor.BACKEND)
        except ValidationError:
            logger.debug("order_additional_validation raised ValidationError")
            return HttpResponseBadRequest("Bad request")

        PaymentProcessor.cancelled(payment_id=payment.id)

        url_name = getattr(settings, 'GETPAID_FAILURE_URL_NAME', None)
        if url_name:
            return redirect(url_name, pk=payment.order.pk)
        return redirect('getpaid:failure-fallback', pk=payment.pk)
