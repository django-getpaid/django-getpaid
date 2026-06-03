import swapper
from django import forms
from django.conf import settings
from django.utils.translation import gettext_lazy as _

from getpaid.validators import run_getpaid_validators

Order = swapper.load_model('getpaid', 'Order')


class PaymentMethodForm(forms.ModelForm):
    """
    Usable example.
    Displays all available payments backends as choice list.
    """

    order = forms.ModelChoiceField(
        widget=forms.HiddenInput, queryset=Order.objects.all()
    )

    class Meta:
        model = swapper.load_model('getpaid', 'Payment')
        fields = [
            'order',
            'amount_required',
            'description',
            'currency',
            'backend',
        ]
        widgets = {
            'amount_required': forms.HiddenInput,
            'description': forms.HiddenInput,
            'currency': forms.HiddenInput,
        }

    def __init__(self, *args, **kwargs):
        from .registry import registry

        super().__init__(*args, **kwargs)
        order = self.initial.get('order')
        currency = getattr(order, 'currency', None) or self.data.get('currency')
        if order is not None:
            self.initial['amount_required'] = order.get_total_amount()
            self.initial['description'] = order.get_description()
        backends = registry.get_choices(currency)
        params = dict(
            choices=backends,
            initial=backends[0][0] if len(backends) == 1 else '',
            label=_('Payment backend'),
            widget=forms.RadioSelect,
        )
        hide_lonely = getattr(settings, 'GETPAID', {}).get(
            'HIDE_LONELY_PLUGIN', False
        )
        if hide_lonely and len(backends) == 1:
            params['initial'] = backends[0][0]
            params['widget'] = forms.HiddenInput

        self.fields['backend'] = forms.ChoiceField(**params)

    def clean_order(self):
        if hasattr(self.cleaned_data['order'], 'is_ready_for_payment'):
            if not self.cleaned_data['order'].is_ready_for_payment():
                raise forms.ValidationError(
                    _('Order is not ready for payment.')
                )
        return self.cleaned_data['order']

    def clean_amount_required(self):
        """Always compute amount_required from the order — never trust
        initial or submitted data."""
        order = self.initial.get('order') or self.cleaned_data.get('order')
        if order is not None:
            return order.get_total_amount()
        return self.cleaned_data.get('amount_required')

    def clean_description(self):
        """Always compute description from the order — never trust
        initial or submitted data."""
        order = self.initial.get('order') or self.cleaned_data.get('order')
        if order is not None:
            return order.get_description()
        return self.cleaned_data.get('description', '')

    def clean_currency(self):
        """Always compute currency from the order — never trust
        initial or submitted data."""
        order = self.initial.get('order') or self.cleaned_data.get('order')
        if order is not None:
            return order.get_currency()
        return self.cleaned_data.get('currency')

    def _apply_order_defaults(self, cleaned_data):
        order = cleaned_data.get('order')
        if order is None:
            return cleaned_data

        cleaned_data['amount_required'] = order.get_total_amount()
        cleaned_data['description'] = order.get_description()
        cleaned_data['currency'] = order.get_currency()
        return cleaned_data

    def clean(self):
        cleaned_data = super().clean()
        cleaned_data = self._apply_order_defaults(cleaned_data)
        return run_getpaid_validators(cleaned_data)

    def save(self, commit=True):
        """Always persist server-computed values from the order,
        regardless of what the form received."""
        instance = super().save(commit=False)
        order = self.cleaned_data.get('order') or self.initial.get('order')
        if order is not None:
            instance.amount_required = order.get_total_amount()
            instance.description = order.get_description()
            instance.currency = order.get_currency()
        if commit:
            instance.save()
        return instance
