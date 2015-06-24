import logging
import hashlib
from collections import OrderedDict
from decimal import Decimal, ROUND_UP

from django.conf import settings
from django.core.urlresolvers import reverse
from django.utils.translation import ugettext_lazy as _
from django.contrib.sites.models import Site
from django.db.models.loading import get_model
from django.core.exceptions import ImproperlyConfigured
from getpaid.backends import PaymentProcessorBase
from django.utils.six.moves.urllib.parse import urlparse, urlunparse,\
    parse_qsl, urlencode

from django.utils import six
if six.PY3:
    unicode = str

logger = logging.getLogger(__name__)


class PaymentProcessor(PaymentProcessorBase):
    BACKEND = 'getpaid.backends.epaydk'
    BACKEND_NAME = _('Epay.dk backend')
    BACKEND_ACCEPTED_CURRENCY = (u'DKK', )
    BACKEND_LOGO_URL = u'https://d25dqh6gpkyuw6.cloudfront.net/company/226' +\
        '/logo/301.jpg?21-06-2015-16'
    BACKEND_GATEWAY_BASE_URL = u'https://ssl.ditonlinebetalingssystem.dk' +\
        '/integration/ewindow/Default.aspx'

    def _format_amount(self, amount):
        amount_dec = Decimal(amount).quantize(Decimal('1.00'),
                                              rounding=ROUND_UP)
        with_decimal = u"{0:.2f}".format(amount_dec)
        return u''.join(with_decimal.split('.'))

    @staticmethod
    def amount_to_python(amount_str):
        return Decimal(int(amount_str) / Decimal("100.0"))

    @staticmethod
    def compute_hash(params):
        """
        The hash you send to (and receive from) ePay must be the value of all
        parameters in the order they are sent + the MD5 key.

        @param params: OrderedDict with values as python unicode objects.

        @see http://tech.epay.dk/en/hash-md5-check
        """
        assert isinstance(params, OrderedDict)
        secret = unicode(PaymentProcessor.get_backend_setting('secret', ''))
        if not secret:
            raise ImproperlyConfigured("epay.dk requires `secret` md5 hash"
                                       " setting")

        values = u''
        for key, val in params.items():
            assert isinstance(val, six.text_type),\
                "param {} is not unicode it is {}".format(key, type(val))
            if key == u'hash':
                continue
            values += val
        values_secret = (values + secret).encode('utf8')
        sig_hash = hashlib.md5(values_secret).hexdigest()
        return sig_hash

    @staticmethod
    def is_received_request_valid(params):
        """
        The hash received from ePay is the value of all GET parameters
        received except the parameter hash + the MD5 key.

        @param params: OrderedDict with values as python unicode objects.

        @see http://tech.epay.dk/en/hash-md5-check
        """
        sig_hash = PaymentProcessor.compute_hash(params)
        if 'hash' in params:
            if params['hash'] == sig_hash:
                return True
        return False

    def get_gateway_url(self, request):
        """
        @see http://tech.epay.dk/en/payment-window-parameters
        @see http://tech.epay.dk/en/payment-window-how-to-get-started

        `accepturl` - payment accepted for processing.
        `cancelurl` - user closed window before the payment is completed.
        `callbackurl` - is called instantly from the ePay server when
                        the payment is completed.
                        For security reasons `callbackurl` is removed from
                        the request params, please use epay admin interface
                        to configure it.
        """
        merchantnumber = unicode(
            self.get_backend_setting('merchantnumber', ''))
        if not merchantnumber:
            raise ImproperlyConfigured("epay.dk requires merchantnumber")
        orderid = unicode(self.payment.order.id)  # a-Z 0-9. Max. 9 characters.
        print(self.payment.amount)
        print(self._format_amount(self.payment.amount))
        params = OrderedDict([
            (u'merchantnumber', merchantnumber),
            (u'orderid', orderid),
           (u'currency', self.payment.currency),
            (u'amount', self._format_amount(self.payment.amount)),
            (u'windowstate', u'3'),  # 3 = Full screen
            (u'submit', u'Go to payment'),
            (u'mobile', u'1'),  # 1 = autodetect
            # (u'callbackurl', reverse('getpaid-epaydk-online')),
        ])

        accepturl_name = getattr(settings, 'GETPAID_SUCCESS_URL_NAME', '')
        if accepturl_name:
            params['accepturl'] = reverse(accepturl_name)

        cancelurl_name = getattr(settings, 'GETPAID_FAILURE_URL_NAME', '')
        if cancelurl_name:
            params['cancelurl'] = reverse(cancelurl_name)

        params['hash'] = PaymentProcessor.compute_hash(params)

        url = u"{}?{}".format(self.BACKEND_GATEWAY_BASE_URL, urlencode(params))
        return url

    def get_logo_url(self):
        return self.BACKEND_LOGO_URL

    @staticmethod
    def online(params):
        Payment = get_model('getpaid', 'Payment')
        payment = Payment.objects.get(id=params['orderid'])
        current_site = Site.objects.get_current()
        use_ssl = PaymentProcessor.get_backend_setting('ssl_return', False)
        return u'OK'

    def payment_success(self):
        pass

    def payment_failure(self):
        pass
