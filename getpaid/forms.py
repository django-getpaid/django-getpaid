from django.forms import forms
from django.forms.fields import ChoiceField
from django.forms.models import ModelChoiceField
from django.forms.widgets import HiddenInput
from django.utils.translation import ugettext as _
from getpaid.models import Order
from utils import get_backend_choices

class PaymentMethodForm(forms.Form):
    """
    Displays all available payments backends as choice list.
    """

    def __init__(self, currency, *args, **kwargs):
        super(PaymentMethodForm, self).__init__(*args, **kwargs)
        self.fields['backend'] = ChoiceField(choices=get_backend_choices(currency), label=_("Payment method"))

    order = ModelChoiceField(widget=HiddenInput, queryset=Order.objects.all())


