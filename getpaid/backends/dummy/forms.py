from django.forms import forms
from django.forms.fields import ChoiceField
from django.utils.translation import ugettext as _


class DummyQuestionForm(forms.Form):
    """
    This dummy form asks for payment authorization.
    """
    authorize_payment = ChoiceField(label=_("authorization"), choices=((1, _('yes')), (0, _('no'))))
