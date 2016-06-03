from django.core.urlresolvers import reverse
from django.utils.translation import ugettext_lazy as _
from getpaid.backends import PaymentProcessorBase


class PaymentProcessor(PaymentProcessorBase):
    BACKEND = 'getpaid.backends.paymill'
    BACKEND_NAME = _('Paymill')
    BACKEND_ACCEPTED_CURRENCY = (u'EUR', u'CZK', u'DKK', u'HUF', u'ISK',
                                 u'ILS', u'LVL', u'CHF', u'NOK', u'PLN',
                                 u'SEK', u'TRY', u'GBP', u'USD', )

    def get_gateway_url(self, request):
        return reverse('getpaid:paymill:authorization', kwargs={'pk' : self.payment.pk}), "GET", {}
