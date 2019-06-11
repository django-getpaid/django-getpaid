import requests
from django.views.generic import FormView

from .forms import DummyQuestionForm


class DummyAuthorizationView(FormView):
    """
    This view simulates the behavior of payment broker
    """

    form_class = DummyQuestionForm
    template_name = "getpaid_dummy_backend/fake_gateway_authorization_form.html"
    success = None

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        params = self.request.POST or self.request.GET  # both cases for testability
        context["payment"] = params.get("payment")
        context["value"] = params.get("value")
        context["currency"] = params.get("currency")
        context["description"] = params.get("description")
        context["callback"] = params.get("callback")
        context["success_url"] = params.get("success_url")
        context["failure_url"] = params.get("failure_url")
        return context

    def get_success_url(self):
        if self.success:
            return self.form.cleaned_data["success_url"]
        return self.form.cleaned_data["failure_url"]

    def form_valid(self, form):
        self.form = form
        url = self.request.build_absolute_uri(form.cleaned_data["callback"])
        # TODO: call post from delayed subprocess
        if form.cleaned_data["authorize_payment"] == "1":
            self.success = True
            requests.post(url, json={"status": "OK"})
        else:
            self.success = False
            requests.post(url, json={"status": "FAIL"})
        return super().form_valid(form)
