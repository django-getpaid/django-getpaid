import json

import swapper
from django.shortcuts import get_object_or_404
from django.views import View

from .processor import PaymentProcessor


class CallbackView(View):
    """
    Dedicated callback view, since payNow does not support dynamic callback urls.
    """

    def post(self, request, *args, **kwargs):
        external_id = json.loads(request.data).get("paymentId")
        Payment = swapper.load_model("getpaid", "Payment")
        payment = get_object_or_404(
            Payment, external_id=external_id, backend=PaymentProcessor.path
        )
        return payment.handle_callback(request, *args, **kwargs)
