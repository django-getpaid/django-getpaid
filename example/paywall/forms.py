from django import forms
from django.utils.translation import gettext as _


class QuestionForm(forms.Form):
    """
    This dummy form asks for payment authorization.
    """

    authorize_payment = forms.ChoiceField(
        label=_("authorization"), choices=((1, _("yes")), (0, _("no")))
    )

    callback = forms.CharField(widget=forms.HiddenInput, required=False)
    success_url = forms.CharField(widget=forms.HiddenInput, required=False)
    failure_url = forms.CharField(widget=forms.HiddenInput, required=False)
