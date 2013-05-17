from django.core.urlresolvers import reverse
from django.utils.translation import ugettext_lazy as _
from getpaid.backends import PaymentProcessorBase

class PaymentProcessor(PaymentProcessorBase):
    BACKEND = 'getpaid.backends.paymill'
    BACKEND_NAME = _('Paymill')
    BACKEND_ACCEPTED_CURRENCY = ('EUR', 'CZK', 'DKK', 'HUF', 'ISK', 'ILS', 'LVL',
        'CHF', 'NOK', 'PLN', 'SEK', 'TRY', 'GBP', )

    def get_gateway_url(self, request):
        return reverse('getpaid-paymill-authorization', kwargs={'pk' : self.payment.pk}), "GET", {}