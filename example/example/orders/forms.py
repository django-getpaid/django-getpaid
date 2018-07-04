from decimal import Decimal
from django.core.exceptions import ValidationError
from django.forms.models import ModelForm
from .models import Order


class OrderForm(ModelForm):
    class Meta:
        model = Order
        exclude = ('status', )

    def clean_total(self):
        if self.cleaned_data['total'] <= Decimal('0'):
            raise ValidationError('Provide some reasonable item price')
        return self.cleaned_data['total']
