from django import forms


class PaymentHiddenInputsPostForm(forms.Form):
    def __init__(self, fields, *args, **kwargs):
        super().__init__(*args, **kwargs)

        for key in fields:
            self.fields[key] = forms.CharField(
                initial=fields[key], widget=forms.HiddenInput
            )
