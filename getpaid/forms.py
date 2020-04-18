import swapper
from django import forms
from django.conf import settings
from django.utils.translation import gettext_lazy as _

from getpaid.validators import run_getpaid_validators

Order = swapper.load_model("getpaid", "Order")


class PaymentMethodForm(forms.ModelForm):
    """
    Usable example.
    Displays all available payments backends as choice list.
    """

    order = forms.ModelChoiceField(
        widget=forms.HiddenInput, queryset=Order.objects.all()
    )

    class Meta:
        model = swapper.load_model("getpaid", "Payment")
        fields = ["order", "amount_required", "description", "currency", "backend"]
        widgets = {
            "amount_required": forms.HiddenInput,
            "description": forms.HiddenInput,
            "currency": forms.HiddenInput,
        }

    def __init__(self, *args, **kwargs):
        from .registry import registry

        super().__init__(*args, **kwargs)
        order = self.initial.get("order")
        currency = getattr(order, "currency", None) or self.data.get("currency")
        if order is not None:
            self.initial["amount_required"] = order.get_total_amount()
            self.initial["description"] = order.get_description()
        backends = registry.get_choices(currency)
        params = dict(
            choices=backends,
            initial=backends[0][0] if len(backends) == 1 else "",
            label=_("Payment backend"),
            widget=forms.RadioSelect,
        )
        hide_lonely = getattr(settings, "GETPAID", {}).get("HIDE_LONELY_PLUGIN", False)
        if hide_lonely and len(backends) == 1:
            params["initial"] = backends[0][0]
            params["widget"] = forms.HiddenInput

        self.fields["backend"] = forms.ChoiceField(**params)

    def clean_order(self):
        if hasattr(self.cleaned_data["order"], "is_ready_for_payment"):
            if not self.cleaned_data["order"].is_ready_for_payment():
                raise forms.ValidationError(_("Order is not ready for payment."))
        return self.cleaned_data["order"]

    def clean(self):
        cleaned_data = super().clean()
        return run_getpaid_validators(cleaned_data)
