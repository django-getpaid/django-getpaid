import json

import swapper
from django.http import HttpResponseBadRequest
from django.shortcuts import get_object_or_404
from django.views import View


class CallbackView(View):
    """
    Callback endpoint for the dummy backend's PUSH confirmation flow.

    Accepts POST requests with a JSON body containing:
        - payment_id: the payment's external_id (UUID)
        - new_status: the new payment status to apply

    Delegates actual processing to the payment's handle_paywall_callback.
    """

    def post(self, request, *args, **kwargs):
        try:
            data = json.loads(request.body)
        except (json.JSONDecodeError, ValueError):
            return HttpResponseBadRequest('Invalid JSON')

        payment_id = data.get('payment_id')
        if not payment_id:
            return HttpResponseBadRequest('Missing payment_id')

        Payment = swapper.load_model('getpaid', 'Payment')
        payment = get_object_or_404(
            Payment,
            external_id=payment_id,
            backend='getpaid.backends.dummy',
        )
        return payment.handle_paywall_callback(request, *args, **kwargs)
