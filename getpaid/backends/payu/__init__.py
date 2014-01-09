from decimal import Decimal
import hashlib
import logging
import urllib
import urllib2
from django.core.exceptions import ImproperlyConfigured
from django.utils.translation import ugettext_lazy as _
import time
from getpaid import signals
from getpaid.backends import PaymentProcessorBase
from getpaid.backends.payu.tasks import get_payment_status_task, accept_payment

logger = logging.getLogger('getpaid.backends.payu')


class PayUTransactionStatus:
    NEW = 1
    CANCELED = 2
    REJECTED = 3
    STARTED = 4
    AWAITING = 5
    REJECTED_AFTER_CANCEL = 7
    FINISHED = 99
    ERROR = 888


class PaymentProcessor(PaymentProcessorBase):
    BACKEND = 'getpaid.backends.payu'
    BACKEND_NAME = _('PayU')
    BACKEND_ACCEPTED_CURRENCY = ('PLN', )
    BACKEND_LOGO_URL = 'getpaid/backends/payu/payu_logo.png'

    _GATEWAY_URL = 'https://www.platnosci.pl/paygw/'
    _ACCEPTED_LANGS = ('pl', 'en')
    _REQUEST_SIG_FIELDS = ('pos_id', 'pay_type', 'session_id', 'pos_auth_key',
                           'amount', 'desc', 'desc2', 'trsDesc', 'order_id', 'first_name', 'last_name',
                           'payback_login', 'street', 'street_hn', 'street_an', 'city', 'post_code',
                           'country', 'email', 'phone', 'language', 'client_ip', 'ts' )
    _ONLINE_SIG_FIELDS = ('pos_id', 'session_id', 'ts',)
    _GET_SIG_FIELDS = ('pos_id', 'session_id', 'ts',)
    _GET_RESPONSE_SIG_FIELDS = (
        'trans_pos_id', 'trans_session_id', 'trans_order_id', 'trans_status', 'trans_amount', 'trans_desc', 'trans_ts',)
    _GET_ACCEPT_SIG_FIELDS = ('trans_pos_id', 'trans_session_id', 'trans_ts',)

    @staticmethod
    def compute_sig(params, fields, key):
        text = ''
        for field in fields:
            text += unicode(params.get(field, '')).encode('utf-8')
        text += key
        return hashlib.md5(text).hexdigest()

    @staticmethod
    def online(pos_id, session_id, ts, sig):
        params = {'pos_id': pos_id, 'session_id': session_id, 'ts': ts, 'sig': sig}

        key2 = PaymentProcessor.get_backend_setting('key2')
        if sig != PaymentProcessor.compute_sig(params, PaymentProcessor._ONLINE_SIG_FIELDS, key2):
            logger.warning('Got message with wrong sig, %s' % str(params))
            return 'SIG ERR'

        try:
            params['pos_id'] = int(params['pos_id'])
        except ValueError:
            return 'POS_ID ERR'
        if params['pos_id'] != int(PaymentProcessor.get_backend_setting('pos_id')):
            return 'POS_ID ERR'

        try:
            payment_id, session = session_id.split(':')
        except ValueError:
            logger.warning('Got message with wrong session_id, %s' % str(params))
            return 'SESSION_ID ERR'

        get_payment_status_task.delay(payment_id, session_id)
        return 'OK'

    def get_gateway_url(self, request):
        """
        Routes a payment to Gateway, should return URL for redirection.

        """
        params = {
            'pos_id': PaymentProcessor.get_backend_setting('pos_id'),
            'pos_auth_key': PaymentProcessor.get_backend_setting('pos_auth_key'),
            'desc': self.get_order_description(self.payment, self.payment.order),
        }

        user_data = {
            'email': None,
            'lang': None,
        }

        signals.user_data_query.send(sender=None, order=self.payment.order, user_data=user_data)
        if user_data['email']:
            params['email'] = user_data['email']

        if user_data['lang'] and user_data['lang'].lower() in PaymentProcessor._ACCEPTED_LANGS:
            params['language'] = user_data['lang'].lower()
        elif PaymentProcessor.get_backend_setting('lang', False) and \
                        PaymentProcessor.get_backend_setting('lang').lower() in PaymentProcessor._ACCEPTED_LANGS:
            params['language'] = PaymentProcessor.get_backend_setting('lang').lower()

        key1 = PaymentProcessor.get_backend_setting('key1')

        signing = PaymentProcessor.get_backend_setting('signing', True)
        testing = PaymentProcessor.get_backend_setting('testing', False)

        if testing:
            # Switch to testing mode, where payment method is set to "test payment"->"t"
            # Warning: testing mode need to be enabled also in payu.pl system for this POS
            params['pay_type'] = 't'

        # Here we put payment.pk as we can get order through payment model
        params['order_id'] = self.payment.pk

        # amount is number of Grosz, not PLN
        params['amount'] = int(self.payment.amount * 100)

        params['session_id'] = "%d:%s" % (self.payment.pk, str(time.time()))

        #Warning: please make sure that this header actually has client IP
        #         rather then web server proxy IP in your WSGI environment
        params['client_ip'] = request.META['REMOTE_ADDR']

        if signing:
            params['ts'] = time.time()
            params['sig'] = PaymentProcessor.compute_sig(params, self._REQUEST_SIG_FIELDS, key1)

        if PaymentProcessor.get_backend_setting('method', 'get').lower() == 'post':
            logger.info(u'New payment using POST: %s' % params)
            return self._GATEWAY_URL + 'UTF/NewPayment', 'POST', params
        elif PaymentProcessor.get_backend_setting('method', 'get').lower() == 'get':
            logger.info(u'New payment using GET: %s' % params)
            for key in params.keys():
                params[key] = unicode(params[key]).encode('utf-8')
            return self._GATEWAY_URL + 'UTF/NewPayment?' + urllib.urlencode(params), 'GET', {}
        else:
            logger.error(u'New payment raises error - bad HTTP method')
            raise ImproperlyConfigured('PayU payment backend accepts only GET or POST')

    def get_payment_status(self, session_id):
        params = {'pos_id': PaymentProcessor.get_backend_setting('pos_id'), 'session_id': session_id, 'ts': time.time()}
        key1 = PaymentProcessor.get_backend_setting('key1')
        key2 = PaymentProcessor.get_backend_setting('key2')

        params['sig'] = PaymentProcessor.compute_sig(params, self._GET_SIG_FIELDS, key1)

        for key in params.keys():
            params[key] = unicode(params[key]).encode('utf-8')

        data = urllib.urlencode(params)
        url = self._GATEWAY_URL + 'UTF/Payment/get/txt'
        request = urllib2.Request(url, data)
        response = urllib2.urlopen(request)
        response_params = PaymentProcessor._parse_text_response(response.read().decode('utf-8'))

        if not response_params['status'] == 'OK':
            logger.warning(u'Payment status error: %s' % response_params)
            return

        if PaymentProcessor.compute_sig(response_params, self._GET_RESPONSE_SIG_FIELDS, key2) == response_params[
            'trans_sig']:
            if not (int(response_params['trans_pos_id']) == int(params['pos_id']) or int(
                    response_params['trans_order_id']) == self.payment.pk):
                logger.error(u'Payment status wrong pos_id and/or order id: %s' % response_params)
                return

            logger.info(u'Fetching payment status: %s' % response_params)

            self.payment.external_id = response_params['trans_id']

            status = int(response_params['trans_status'])
            if status in (PayUTransactionStatus.AWAITING, PayUTransactionStatus.FINISHED):

                if self.payment.on_success(Decimal(response_params['trans_amount']) / Decimal('100')):
                    #fully paid
                    if status == PayUTransactionStatus.AWAITING:
                        accept_payment.delay(self.payment.id, session_id)

            elif status in (PayUTransactionStatus.CANCELED,
                            PayUTransactionStatus.ERROR,
                            PayUTransactionStatus.REJECTED,
                            PayUTransactionStatus.REJECTED_AFTER_CANCEL):
                self.payment.on_failure()

        else:
            logger.error(u'Payment status wrong response signature: %s' % response_params)

    def accept_payment(self, session_id):
        params = {'pos_id': PaymentProcessor.get_backend_setting('pos_id'), 'session_id': session_id, 'ts': time.time()}
        key1 = PaymentProcessor.get_backend_setting('key1')
        key2 = PaymentProcessor.get_backend_setting('key2')
        params['sig'] = PaymentProcessor.compute_sig(params, self._GET_SIG_FIELDS, key1)
        for key in params.keys():
            params[key] = unicode(params[key]).encode('utf-8')
        data = urllib.urlencode(params)
        url = self._GATEWAY_URL + 'UTF/Payment/confirm/txt'
        request = urllib2.Request(url, data)
        response = urllib2.urlopen(request)
        response_params = PaymentProcessor._parse_text_response(response.read().decode('utf-8'))
        if response_params['status'] == 'OK':
            if PaymentProcessor.compute_sig(response_params, self._GET_ACCEPT_SIG_FIELDS, key2) != response_params[
                'trans_sig']:
                logger.error(u'Wrong signature for Payment/confirm response: %s' % response_params)
                return
            if int(response_params['trans_pos_id']) != int(params['pos_id']):
                logger.error(u'Wrong pos_id for Payment/confirm response: %s' % response_params)
                return

            logger.info(u'Payment accepted: %s' % response_params)
        else:
            logger.warning(u'Payment not accepted, error: %s' % response_params)


    @staticmethod
    def _parse_text_response(text):
        """
        Parses inputs like:
        variable : some value
        variable2 : 123.44
        into dict
        """
        return dict(
            map(lambda (k, v): (k.rstrip(), v.lstrip()),
                filter(
                    lambda l: len(l) == 2,
                    map(lambda l: l.split(':', 1),
                        text.splitlines())
                )
            )
        )