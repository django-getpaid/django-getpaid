import datetime
from decimal import Decimal
import hashlib
import logging
from django.utils import six
from six.moves.urllib.parse import urlencode
from django.core.exceptions import ImproperlyConfigured
from django.core.urlresolvers import reverse
from django.utils.timezone import utc
from django.utils.translation import ugettext_lazy as _
from getpaid import signals
from getpaid.backends import PaymentProcessorBase
from getpaid.utils import get_domain

logger = logging.getLogger('getpaid.backends.dotpay')


class DotpayTransactionStatus:
    STARTED = 1
    FINISHED = 2
    REJECTED = 3
    REFUNDED = 4
    RECLAMATION = 5


class PaymentProcessor(PaymentProcessorBase):
    BACKEND = 'getpaid.backends.dotpay'
    BACKEND_NAME = _('Dotpay')
    BACKEND_ACCEPTED_CURRENCY = ('PLN', 'EUR', 'USD', 'GBP', 'JPY', 'CZK', 'SEK')
    BACKEND_LOGO_URL = 'getpaid/backends/dotpay/dotpay_logo.png'

    _ALLOWED_IP = ('195.150.9.37',)
    _ACCEPTED_LANGS = ('pl', 'en', 'de', 'it', 'fr', 'es', 'cz', 'ru', 'bg')
    _GATEWAY_URL = 'https://ssl.dotpay.eu/'
    _ONLINE_SIG_FIELDS = ('id', 'control', 't_id', 'amount', 'email', 'service', 'code', 'username', 'password', 't_status')

    @staticmethod
    def compute_sig(params, fields, PIN):
        text = PIN + ":" + (u":".join(map(lambda field: params.get(field, ''), fields)))
        return hashlib.md5(text.encode('utf8')).hexdigest()

    @staticmethod
    def online(params, ip):

        allowed_ip = PaymentProcessor.get_backend_setting('allowed_ip', PaymentProcessor._ALLOWED_IP)

        if len(allowed_ip) != 0 and ip not in allowed_ip:
            logger.warning('Got message from not allowed IP %s' % str(allowed_ip))
            return 'IP ERR'

        PIN = PaymentProcessor.get_backend_setting('PIN', '')

        if params['md5'] != PaymentProcessor.compute_sig(params, PaymentProcessor._ONLINE_SIG_FIELDS, PIN):
            logger.warning('Got message with wrong sig, %s' % str(params))
            return u'SIG ERR'

        try:
            params['id'] = int(params['id'])
        except ValueError:
            return u'ID ERR'
        if params['id'] != int(PaymentProcessor.get_backend_setting('id')):
            return u'ID ERR'

        from getpaid.models import Payment
        try:
            payment = Payment.objects.get(pk=int(params['control']))
        except (ValueError, Payment.DoesNotExist):
            logger.error('Got message for non existing Payment, %s' % str(params))
            return u'PAYMENT ERR'

        amount, currency = params.get('orginal_amount', params['amount'] + ' PLN').split(' ')

        if currency != payment.currency.upper():
            logger.error('Got message with wrong currency, %s' % str(params))
            return u'CURRENCY ERR'

        payment.external_id = params.get('t_id', '')
        payment.description = params.get('email', '')

        if int(params['t_status']) == DotpayTransactionStatus.FINISHED:
            payment.amount_paid = Decimal(amount)
            payment.paid_on = datetime.datetime.utcnow().replace(tzinfo=utc)
            if payment.amount <= Decimal(amount):
                # Amount is correct or it is overpaid
                payment.change_status('paid')
            else:
                payment.change_status('partially_paid')
        elif int(params['t_status']) in [DotpayTransactionStatus.REJECTED, DotpayTransactionStatus.RECLAMATION, DotpayTransactionStatus.REFUNDED]:
            payment.change_status('failed')

        return u'OK'

    def get_URLC(self):
        urlc = reverse('getpaid:dotpay:online')
        if PaymentProcessor.get_backend_setting('force_ssl', False):
            return u'https://%s%s' % (get_domain(), urlc)
        else:
            return u'http://%s%s' % (get_domain(), urlc)

    def get_URL(self, pk):
        url = reverse('getpaid:dotpay:return', kwargs={'pk': pk})
        if PaymentProcessor.get_backend_setting('force_ssl', False):
            return u'https://%s%s' % (get_domain(), url)
        else:
            return u'http://%s%s' % (get_domain(), url)

    def get_gateway_url(self, request):
        """
        Routes a payment to Gateway, should return URL for redirection.
        """
        params = {
            'id': PaymentProcessor.get_backend_setting('id'),
            'description': self.get_order_description(self.payment, self.payment.order),
            'amount': self.payment.amount,
            'currency': self.payment.currency,
            'type': 0,  # show "return" button after finished payment
            'control': self.payment.pk,
            'URL': self.get_URL(self.payment.pk),
            'URLC': self.get_URLC(),
        }

        user_data = {
            'email': None,
            'lang': None,
        }
        signals.user_data_query.send(sender=None, order=self.payment.order, user_data=user_data)

        if user_data['email']:
            params['email'] = user_data['email']

        if user_data['lang'] and user_data['lang'].lower() in PaymentProcessor._ACCEPTED_LANGS:
            params['lang'] = user_data['lang'].lower()
        elif PaymentProcessor.get_backend_setting('lang', False) and \
                PaymentProcessor.get_backend_setting('lang').lower() in PaymentProcessor._ACCEPTED_LANGS:
            params['lang'] = PaymentProcessor.get_backend_setting('lang').lower()

        if PaymentProcessor.get_backend_setting('onlinetransfer', False):
            params['onlinetransfer'] = 1
        if PaymentProcessor.get_backend_setting('p_email', False):
            params['p_email'] = PaymentProcessor.get_backend_setting('p_email')
        if PaymentProcessor.get_backend_setting('p_info', False):
            params['p_info'] = PaymentProcessor.get_backend_setting('p_info')
        if PaymentProcessor.get_backend_setting('tax', False):
            params['tax'] = 1

        gateway_url = PaymentProcessor.get_backend_setting('gateway_url', self._GATEWAY_URL)

        if PaymentProcessor.get_backend_setting('method', 'get').lower() == 'post':
            return gateway_url, 'POST', params
        elif PaymentProcessor.get_backend_setting('method', 'get').lower() == 'get':
            for key in params.keys():
                params[key] = six.text_type(params[key]).encode('utf-8')
            return gateway_url + '?' + urlencode(params), "GET", {}
        else:
            raise ImproperlyConfigured('Dotpay payment backend accepts only GET or POST')
