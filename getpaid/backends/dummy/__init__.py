from django.core.urlresolvers import reverse
from django.utils.translation import ugettext_lazy as _
BACKEND_NAME = _('Dummy backend')

def processor(payment):
    """
    Routes a payment to Gateway, should return URL for redirection
    """
    return reverse('getpaid-dummy-authorization', kwargs={'pk' : payment.pk})