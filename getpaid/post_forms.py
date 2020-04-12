from django import forms


class PaymentHiddenInputsPostForm(forms.Form):
    def __init__(self, items, *args, **kwargs):
        super().__init__(*args, **kwargs)

        for key in items:
            self.fields[key] = forms.CharField(
                initial=items[key], widget=forms.HiddenInput
            )
