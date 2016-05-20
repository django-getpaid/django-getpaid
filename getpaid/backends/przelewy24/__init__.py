# Author: Krzysztof Dorosz <cypreess@gmail.com>
#
# Disclaimer:
# Writing and open sourcing this backend was kindly funded by Issue Stand
# http://issuestand.com/
#

from decimal import Decimal
import hashlib
import logging
import time
import datetime
from django.utils import six
from six.moves.urllib.request import Request, urlopen
from six.moves.urllib.parse import urlencode

from django.core.exceptions import ImproperlyConfigured
from django.core.urlresolvers import reverse
from django.utils.translation import ugettext_lazy as _
from pytz import utc

from getpaid import signals
from getpaid.backends import PaymentProcessorBase
from getpaid.backends.przelewy24.tasks import get_payment_status_task
from getpaid.utils import get_domain

logger = logging.getLogger('getpaid.backends.przelewy24')


class PaymentProcessor(PaymentProcessorBase):
    BACKEND = u'getpaid.backends.przelewy24'
    BACKEND_NAME = _(u'Przelewy24')
    BACKEND_ACCEPTED_CURRENCY = (u'PLN', )
    BACKEND_LOGO_URL = u'getpaid/backends/przelewy24/przelewy24_logo.png'

    _GATEWAY_URL = u'https://secure.przelewy24.pl/index.php'
    _SANDBOX_GATEWAY_URL = u'https://sandbox.przelewy24.pl/index.php'

    _GATEWAY_CONFIRM_URL = u'https://secure.przelewy24.pl/transakcja.php'
    _SANDBOX_GATEWAY_CONFIRM_URL = u'https://sandbox.przelewy24.pl/transakcja.php'

    _ACCEPTED_LANGS = (u'pl', u'en', u'es', u'de', u'it')
    _REQUEST_SIG_FIELDS = (u'p24_session_id', u'p24_id_sprzedawcy', u'p24_kwota', u'crc')
    _SUCCESS_RETURN_SIG_FIELDS = (u'p24_session_id', u'p24_order_id', u'p24_kwota', u'crc')
    _STATUS_SIG_FIELDS = (u'p24_session_id', u'p24_order_id', u'p24_kwota', u'crc')

    @staticmethod
    def compute_sig(params, fields, crc):
        params = params.copy()
        params.update({'crc': crc})
        text = u"|".join(map(lambda field: six.text_type(params.get(field, '')), fields))
        return six.text_type(hashlib.md5(text.encode('utf-8')).hexdigest())

    @staticmethod
    def on_payment_status_change(p24_session_id, p24_order_id, p24_kwota, p24_order_id_full, p24_crc):
        params = {
            'p24_session_id': p24_session_id,
            'p24_order_id': p24_order_id,
            'p24_kwota': p24_kwota,
            'p24_order_id_full': p24_order_id_full,
            'p24_crc': p24_crc,
        }
        crc = PaymentProcessor.get_backend_setting('crc')
        if p24_crc != PaymentProcessor.compute_sig(params, PaymentProcessor._SUCCESS_RETURN_SIG_FIELDS,
                                                   crc):
            logger.warning('Success return call has wrong crc %s' % str(params))
            return False

        payment_id = p24_session_id.split(':')[0]
        get_payment_status_task.delay(payment_id, p24_session_id, p24_order_id, p24_kwota)
        return True

    def get_payment_status(self, p24_session_id, p24_order_id, p24_kwota):
        params = {
            'p24_session_id': p24_session_id,
            'p24_order_id': p24_order_id,
            'p24_id_sprzedawcy': PaymentProcessor.get_backend_setting('id'),
            'p24_kwota': p24_kwota,
        }
        crc = PaymentProcessor.get_backend_setting('crc')
        params['p24_crc'] = PaymentProcessor.compute_sig(params, self._STATUS_SIG_FIELDS, crc)

        for key in params.keys():
            params[key] = six.text_type(params[key]).encode('utf-8')

        data = urlencode(params).encode('utf-8')

        url = self._GATEWAY_CONFIRM_URL
        if PaymentProcessor.get_backend_setting('sandbox', False):
            url = self._SANDBOX_GATEWAY_CONFIRM_URL

        self.payment.external_id = p24_order_id

        request = Request(url, data)
        try:
            response = urlopen(request).read().decode('utf8')
        except Exception:
            logger.exception('Error while getting payment status change %s data=%s' % (url, str(params)))
            return

        response_list = list(filter(lambda ll: ll, map(lambda li: li.strip(), response.splitlines())))

        if len(response_list) >= 2 and response_list[0] == 'RESULT' and response_list[1] == 'TRUE':
            logger.info('Payment accepted %s' % str(params))
            self.payment.amount_paid = Decimal(p24_kwota) / Decimal('100')
            self.payment.paid_on = datetime.datetime.utcnow().replace(tzinfo=utc)
            if self.payment.amount_paid >= self.payment.amount:
                self.payment.change_status('paid')
            else:
                self.payment.change_status('partially_paid')
        else:
            logger.warning('Payment rejected for data=%s: "%s"' % (str(params), response))
            self.payment.change_status('failed')

    def get_gateway_url(self, request):
        """
        Routes a payment to Gateway, should return URL for redirection.

        """
        params = {
            'p24_id_sprzedawcy': PaymentProcessor.get_backend_setting('id'),
            'p24_opis': self.get_order_description(self.payment, self.payment.order),
            'p24_session_id': "%s:%s:%s" % (self.payment.pk, self.BACKEND, time.time()),
            'p24_kwota': int(self.payment.amount * 100),
            'p24_email': None,

        }

        user_data = {
            'email': None,
            'lang': None,
            'p24_klient': None,
            'p24_adres': None,
            'p24_kod': None,
            'p24_miasto': None,
            'p24_kraj': None,
        }
        signals.user_data_query.send(sender=None, order=self.payment.order, user_data=user_data)

        for key in ('p24_klient', 'p24_adres', 'p24_kod', 'p24_miasto', 'p24_kraj'):
            if user_data[key] is not None:
                params[key] = user_data[key]

        if user_data['email']:
            params['p24_email'] = user_data['email']

        if user_data['lang'] and user_data['lang'].lower() in PaymentProcessor._ACCEPTED_LANGS:
            params['p24_language'] = user_data['lang'].lower()
        elif PaymentProcessor.get_backend_setting('lang', False) and PaymentProcessor.get_backend_setting(
                'lang').lower() in PaymentProcessor._ACCEPTED_LANGS:
            params['p24_language'] = PaymentProcessor.get_backend_setting('lang').lower()

        params['p24_crc'] = self.compute_sig(params, self._REQUEST_SIG_FIELDS,
                                             PaymentProcessor.get_backend_setting('crc'))

        current_site = get_domain()
        use_ssl = PaymentProcessor.get_backend_setting('ssl_return', False)

        params['p24_return_url_ok'] = ('https://' if use_ssl else 'http://') + current_site + reverse(
            'getpaid:przelewy24:success', kwargs={'pk': self.payment.pk})
        params['p24_return_url_error'] = ('https://' if use_ssl else 'http://') + current_site + reverse(
            'getpaid:przelewy24:failure', kwargs={'pk': self.payment.pk})

        if params['p24_email'] is None:
            raise ImproperlyConfigured(
                '%s requires filling `email` field for payment (you need to handle `user_data_query` signal)' % self.BACKEND)

        return self._SANDBOX_GATEWAY_URL if PaymentProcessor.get_backend_setting('sandbox',
                                                                                 False) else self._GATEWAY_URL, 'POST', params
