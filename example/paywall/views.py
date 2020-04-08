import json

import requests
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.views.decorators.csrf import csrf_exempt
from django.views.generic import FormView

from .forms import QuestionForm
from .models import PaymentEntry


class AuthorizationView(FormView):
    """
    This view simulates the behavior of payment broker
    """

    form_class = QuestionForm
    template_name = "paywall/fake_gateway_authorization_form.html"
    success = None

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        params = self.request.POST or self.request.GET  # both cases for testability
        if "pay_id" in params:
            obj = get_object_or_404(PaymentEntry, id=params.get("pay_id"))
            context["payment"] = obj.payment
            context["value"] = obj.value
            context["currency"] = obj.currency
            context["description"] = obj.description
            context["callback"] = obj.callback
            context["success_url"] = obj.success_url
            context["failure_url"] = obj.failure_url
            context["message"] = "Presenting pre-registered payment"
        else:
            context["payment"] = params.get("payment")
            context["value"] = params.get("value")
            context["currency"] = params.get("currency")
            context["description"] = params.get("description")
            context["callback"] = params.get("callback", "")
            context["success_url"] = params.get("success_url", "")
            context["failure_url"] = params.get("failure_url", "")
            context["message"] = "Presenting directly requested payment"
        return context

    def get_success_url(self):
        if self.success:
            return self.form.cleaned_data["success_url"]
        return self.form.cleaned_data["failure_url"]

    def form_valid(self, form):
        self.form = form
        url = self.request.build_absolute_uri(form.cleaned_data["callback"])
        # TODO: call post from delayed subprocess
        if url:
            if form.cleaned_data["authorize_payment"] == "1":
                self.success = True
                requests.post(url, json={"status": "OK"})
            else:
                self.success = False
                requests.post(url, json={"status": "FAIL"})
        return super().form_valid(form)


@csrf_exempt
def register_payment(request):
    legal_fields = [
        "payment",
        "value",
        "currency",
        "description",
        "callback",
        "success_url",
        "failure_url",
    ]
    params = {k: v for k, v in json.loads(request.body).items() if k in legal_fields}
    payment = PaymentEntry.objects.create(**params)

    url = request.build_absolute_uri(reverse("paywall:gateway"))
    url += f"?pay_id={payment.id}"

    content = {"url": url}
    return JsonResponse(content)
