from django import forms
from django.utils.translation import ugettext as _


class DummyQuestionForm(forms.Form):
    """
    This dummy form asks for payment authorization.
    """

    authorize_payment = forms.ChoiceField(
        label=_("authorization"), choices=((1, _("yes")), (0, _("no")))
    )

    callback = forms.CharField(widget=forms.HiddenInput)
    success_url = forms.CharField(widget=forms.HiddenInput)
    failure_url = forms.CharField(widget=forms.HiddenInput)
