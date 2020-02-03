from django.views import View
from django.views.decorators.csrf import csrf_exempt
from django import http
from django.utils.decorators import method_decorator

from getpaid import utils

from . import PaymentProcessor


def get_request_body(request):  # for easier mocking
    return request.body


@method_decorator(csrf_exempt, name='dispatch')
class ConfirmationWebhook(View):
    """
    This view receives payment status updates from PayU.
    """

    def post(self, request, *args, **kwargs):
        payload = get_request_body(request).decode('utf-8')
        if not payload:
            # logger.error('Got malformed POST request: {}'.format(request.POST))
            return http.HttpResponseBadRequest('MALFORMED')

        ip_address = utils.get_ip_address(request)
        req_payu_sig = request.META.get('HTTP_OPENPAYU_SIGNATURE')
        if not req_payu_sig:
            req_payu_sig = request.META.get('HTTP_X_OPENPAYU_SIGNATURE')
        status = PaymentProcessor.online(payload=payload, ip=ip_address, req_sig=req_payu_sig)

        if status != "OK":
            return http.HttpResponseBadRequest(status)
        return http.HttpResponse(status)
