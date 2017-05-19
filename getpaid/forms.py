from django.core.exceptions import ValidationError
from django.forms import forms
from django.forms.fields import ChoiceField, CharField
from django.forms.models import ModelChoiceField
from django.forms.widgets import HiddenInput, RadioSelect
from django.utils.translation import ugettext as _

from getpaid.models import Order
from .utils import get_backend_choices


class PaymentMethodForm(forms.Form):
    """
    Displays all available payments backends as choice list.
    """

    def __init__(self, currency, *args, **kwargs):
        super(PaymentMethodForm, self).__init__(*args, **kwargs)
        backends = get_backend_choices(currency)
        self.fields['backend'] = ChoiceField(
            choices=backends,
            initial=backends[0][0] if len(backends) else '',
            label=_("Payment method"),
            widget=RadioSelect,
        )

    order = ModelChoiceField(widget=HiddenInput, queryset=Order.objects.all())

    def clean_order(self):
        if hasattr(self.cleaned_data['order'], 'is_ready_for_payment'):
            if not self.cleaned_data['order'].is_ready_for_payment():
                raise ValidationError(_('Order cannot be paid'))
        return self.cleaned_data['order']


class PaymentHiddenInputsPostForm(forms.Form):
    def __init__(self, items, *args, **kwargs):
        super(PaymentHiddenInputsPostForm, self).__init__(*args, **kwargs)

        for key in items:
            self.fields[key] = CharField(initial=items[key], widget=HiddenInput)
