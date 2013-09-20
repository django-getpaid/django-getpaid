from django import forms


class PaymillForm(forms.Form):
    token = forms.CharField(widget=forms.HiddenInput())
