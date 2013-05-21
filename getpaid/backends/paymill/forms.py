from django import forms
from django.utils.translation import ugettext as _


class PaymillForm(forms.Form):
    token = forms.CharField(widget=forms.HiddenInput())
