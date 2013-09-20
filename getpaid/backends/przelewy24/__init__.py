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
import urllib
import urllib2
import datetime

from django.contrib.sites.models import Site
from django.core.exceptions import ImproperlyConfigured
from django.core.urlresolvers import reverse
from django.utils.translation import ugettext_lazy as _
from pytz import utc

from getpaid import signals
from getpaid.backends import PaymentProcessorBase
from getpaid.backends.przelewy24.tasks import get_payment_status_task

logger = logging.getLogger('getpaid.backends.przelewy24')


class PaymentProcessor(PaymentProcessorBase):
    BACKEND = 'getpaid.backends.przelewy24'
    BACKEND_NAME = _('Przelewy24')
    BACKEND_ACCEPTED_CURRENCY = ('PLN', )
    BACKEND_LOGO_URL = 'getpaid/backends/przelewy24/przelewy24_logo.png'

    _GATEWAY_URL = 'https://secure.przelewy24.pl/index.php'
    _SANDBOX_GATEWAY_URL = 'https://sandbox.przelewy24.pl/index.php'

    _GATEWAY_CONFIRM_URL = 'https://secure.przelewy24.pl/transakcja.php'
    _SANDBOX_GATEWAY_CONFIRM_URL = 'https://sandbox.przelewy24.pl/transakcja.php'

    _ACCEPTED_LANGS = ('pl', 'en', 'es', 'de', 'it')
    _REQUEST_SIG_FIELDS = ('p24_session_id', 'p24_id_sprzedawcy', 'p24_kwota', 'crc')
    _SUCCESS_RETURN_SIG_FIELDS = ('p24_session_id', 'p24_order_id', 'p24_kwota', 'crc')
    _STATUS_SIG_FIELDS = ('p24_session_id', 'p24_order_id', 'p24_kwota', 'crc')

    @staticmethod
    def compute_sig(params, fields, crc):
        params = params.copy()
        params.update({'crc': crc})
        text = "|".join(map(lambda field: unicode(params.get(field, '')).encode('utf-8'), fields))
        return hashlib.md5(text).hexdigest()

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
            params[key] = unicode(params[key]).encode('utf-8')

        data = urllib.urlencode(params)
        url = self._SANDBOX_GATEWAY_CONFIRM_URL if PaymentProcessor.get_backend_setting('sandbox',
                                                                                        False) else self._GATEWAY_CONFIRM_URL

        self.payment.external_id = params['p24_order_id']

        request = urllib2.Request(url, data)
        try:
            response = urllib2.urlopen(request).read()
        except Exception:
            logger.exception('Error while getting payment status change %s data=%s' % (url, str(params)))
            return

        response_list = filter(lambda ll: ll, map(lambda l: l.strip(), response.splitlines()))

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
        }
        signals.user_data_query.send(sender=None, order=self.payment.order, user_data=user_data)
        if user_data['email']:
            params['p24_email'] = user_data['email']

        if user_data['lang'] and user_data['lang'].lower() in PaymentProcessor._ACCEPTED_LANGS:
            params['p24_language'] = user_data['lang'].lower()
        elif PaymentProcessor.get_backend_setting('lang', False) and PaymentProcessor.get_backend_setting(
                'lang').lower() in PaymentProcessor._ACCEPTED_LANGS:
            params['p24_language'] = PaymentProcessor.get_backend_setting('lang').lower()

        params['p24_crc'] = self.compute_sig(params, self._REQUEST_SIG_FIELDS,
                                             PaymentProcessor.get_backend_setting('crc'))

        current_site = Site.objects.get_current()
        use_ssl = PaymentProcessor.get_backend_setting('ssl_return', False)

        params['p24_return_url_ok'] = ('https://' if use_ssl else 'http://') + current_site.domain + reverse(
            'getpaid-przelewy24-success', kwargs={'pk': self.payment.pk})
        params['p24_return_url_error'] = ('https://' if use_ssl else 'http://') + current_site.domain + reverse(
            'getpaid-przelewy24-failure', kwargs={'pk': self.payment.pk})

        if params['p24_email'] is None:
            raise ImproperlyConfigured(
                '%s requires filling `email` field for payment (you need to handle `user_data_query` signal)' % self.BACKEND)

        return self._SANDBOX_GATEWAY_URL if PaymentProcessor.get_backend_setting('sandbox',
                                                                                 False) else self._GATEWAY_URL, 'POST', params
