from django.core.urlresolvers import reverse
from django.utils.translation import ugettext_lazy as _
from getpaid.backends import PaymentProcessorBase


class PaymentProcessor(PaymentProcessorBase):
    BACKEND = 'getpaid.backends.dummy'
    BACKEND_NAME = _('Dummy backend')
    BACKEND_ACCEPTED_CURRENCY = (u'PLN', u'EUR', u'USD')

    def get_gateway_url(self, request):
        return (
            reverse('getpaid:dummy:authorization',
                    kwargs={'pk': self.payment.pk}),
            "GET",
            {}
        )
