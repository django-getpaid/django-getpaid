from decimal import Decimal

from django.core.exceptions import ValidationError
from django.forms.models import ModelForm

from .models import Order


class OrderForm(ModelForm):
    class Meta:
        model = Order
        exclude = ('status',)

    def clean_name(self):
        value = self.cleaned_data.get('name', '').strip()
        if not value:
            raise ValidationError('Order name is required.')
        return value

    def clean_total(self):
        if self.cleaned_data['total'] <= Decimal(0):
            raise ValidationError('Provide some reasonable item price')
        return self.cleaned_data['total']
