import swapper
from django.shortcuts import get_object_or_404
from django.views import View


class CallbackView(View):
    """
    Each plugin can define its own callbacks and other views.
    """

    def post(self, request, pk, *args, **kwargs):
        Payment = swapper.load_model("getpaid", "Payment")
        payment = get_object_or_404(Payment, pk=pk)
        return payment.handle_paywall_callback(request, *args, **kwargs)


callback = CallbackView.as_view()
