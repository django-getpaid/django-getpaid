# http://developers.payu.com/pl/classic_api.html
# THIS METHOD IS DEPRECATED BY PAYU!
# THIS PLUGIN IS DEPRECATED AND WILL NOT BE UPDATED!
# Please use 'payu_rest'

import time
from decimal import Decimal
import hashlib
import logging

import six
from six.moves.urllib.request import Request, urlopen
from six.moves.urllib.parse import urlencode
from django.core.exceptions import ImproperlyConfigured
from django.utils.translation import ugettext_lazy as _
from deprecated import deprecated

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


@deprecated(version='1.8', reason="This plugin is outdated.")
class PaymentProcessor(PaymentProcessorBase):
    BACKEND = u'getpaid.backends.payu'
    BACKEND_NAME = _(u'PayU')
    BACKEND_ACCEPTED_CURRENCY = (u'PLN',)
    BACKEND_LOGO_URL = u'getpaid/backends/payu/payu_logo.png'

    _GATEWAY_URL = u'https://secure.payu.com/paygw/'
    _ACCEPTED_LANGS = (u'pl', u'en')
    _REQUEST_SIG_FIELDS = (
        u'pos_id', u'pay_type', u'session_id',
        u'pos_auth_key', u'amount', u'desc', u'desc2', u'trsDesc', u'order_id',
        u'first_name', u'last_name', u'payback_login', u'street', u'street_hn',
        u'street_an', u'city', u'post_code', u'country', u'email', u'phone',
        u'language', u'client_ip', u'ts'
    )
    _ONLINE_SIG_FIELDS = (u'pos_id', u'session_id', u'ts',)
    _GET_SIG_FIELDS = (u'pos_id', u'session_id', u'ts',)
    _GET_RESPONSE_SIG_FIELDS = (
        u'trans_pos_id', u'trans_session_id', u'trans_order_id',
        u'trans_status', u'trans_amount', u'trans_desc', u'trans_ts',)
    _GET_ACCEPT_SIG_FIELDS = (u'trans_pos_id', u'trans_session_id', u'trans_ts',)

    @staticmethod
    def compute_sig(params, fields, key):
        text = u''
        for field in fields:
            param_value = params.get(field, '')
            text += six.text_type(param_value)

        text += key
        text_encoded = text.encode('utf-8')
        return six.text_type(hashlib.md5(text_encoded).hexdigest())

    @staticmethod
    def online(pos_id, session_id, ts, sig):
        params = {
            u'pos_id': pos_id,
            u'session_id': session_id,
            u'ts': ts,
            u'sig': sig
        }

        key2 = six.text_type(PaymentProcessor.get_backend_setting('key2'))
        if sig != PaymentProcessor.compute_sig(params, PaymentProcessor._ONLINE_SIG_FIELDS, key2):
            logger.warning('Got message with wrong sig, %s' % str(params))
            return u'SIG ERR'

        try:
            params['pos_id'] = int(params['pos_id'])
        except ValueError:
            return u'POS_ID ERR'
        if params['pos_id'] != int(PaymentProcessor.get_backend_setting('pos_id')):
            return u'POS_ID ERR'

        try:
            payment_id, session = session_id.split(':')
        except ValueError:
            logger.warning(
                'Got message with wrong session_id, %s' % str(params))
            return u'SESSION_ID ERR'

        get_payment_status_task.delay(payment_id, session_id)
        return u'OK'

    def get_gateway_url(self, request):
        """
        Routes a payment to Gateway, should return URL for redirection.

        """
        params = {
            u'pos_id': PaymentProcessor.get_backend_setting('pos_id'),
            u'pos_auth_key': PaymentProcessor.get_backend_setting('pos_auth_key'),
            u'desc': self.get_order_description(self.payment, self.payment.order),
        }

        user_data = {
            u'email': None,
            u'lang': None,
        }

        signals.user_data_query.send(
            sender=None, order=self.payment.order, user_data=user_data)
        if user_data['email']:
            params['email'] = user_data['email']

        if user_data['lang'] \
                and user_data['lang'].lower() in PaymentProcessor._ACCEPTED_LANGS:
            params['language'] = user_data['lang'].lower()
        elif PaymentProcessor.get_backend_setting('lang', False) and \
                PaymentProcessor.get_backend_setting('lang').lower() in PaymentProcessor._ACCEPTED_LANGS:
            params['language'] = six.text_type(PaymentProcessor.get_backend_setting('lang').lower())

        key1 = six.text_type(PaymentProcessor.get_backend_setting('key1'))

        signing = PaymentProcessor.get_backend_setting('signing', True)
        testing = PaymentProcessor.get_backend_setting('testing', False)

        if testing:
            # Switch to testing mode, where payment method is set to "test payment"->"t"
            # Warning: testing mode need to be enabled also in payu.pl system
            # for this POS
            params['pay_type'] = u't'

        # Here we put payment.pk as we can get order through payment model
        params['order_id'] = self.payment.pk

        # amount is number of Grosz, not PLN
        params['amount'] = int(self.payment.amount * 100)

        params['session_id'] = u"%d:%s" % (self.payment.pk, time.time())

        # Warning: please make sure that this header actually has client IP
        #         rather then web server proxy IP in your WSGI environment
        params['client_ip'] = request.META['REMOTE_ADDR']

        if signing:
            params['ts'] = six.text_type(time.time())
            params['sig'] = PaymentProcessor.compute_sig(
                params, self._REQUEST_SIG_FIELDS, key1)

        if PaymentProcessor.get_backend_setting('method', 'get').lower() == 'post':
            logger.info(u'New payment using POST: %s' % params)
            return self._GATEWAY_URL + 'UTF/NewPayment', 'POST', params
        elif PaymentProcessor.get_backend_setting('method', 'get').lower() == 'get':
            logger.info(u'New payment using GET: %s' % params)
            for key in params.keys():
                params[key] = six.text_type(params[key]).encode('utf-8')
            return self._GATEWAY_URL + 'UTF/NewPayment?' + urlencode(params), 'GET', {}
        else:
            logger.error(u'New payment raises error - bad HTTP method')
            raise ImproperlyConfigured(
                'PayU payment backend accepts only GET or POST')

    def get_payment_status(self, session_id):
        params = {
            u'pos_id': PaymentProcessor.get_backend_setting('pos_id'),
            u'session_id': session_id,
            u'ts': time.time()
        }
        key1 = PaymentProcessor.get_backend_setting('key1')
        key2 = PaymentProcessor.get_backend_setting('key2')

        params['sig'] = PaymentProcessor.compute_sig(
            params, self._GET_SIG_FIELDS, key1)

        for key in params.keys():
            params[key] = six.text_type(params[key]).encode('utf-8')

        data = six.text_type(urlencode(params)).encode('utf-8')
        url = self._GATEWAY_URL + 'UTF/Payment/get/txt'
        request = Request(url, data)
        response = urlopen(request)
        response_data = response.read().decode('utf-8')
        response_params = PaymentProcessor._parse_text_response(response_data)

        if not response_params['status'] == u'OK':
            logger.warning(u'Payment status error: %s' % response_params)
            return

        if PaymentProcessor.compute_sig(response_params, self._GET_RESPONSE_SIG_FIELDS,
                                        key2) == response_params['trans_sig']:
            if not (int(response_params['trans_pos_id']) == int(params['pos_id']) or
                    int(response_params['trans_order_id']) == self.payment.pk):
                logger.error(u'Payment status wrong pos_id and/or order id: %s' % response_params)
                return

            logger.info(u'Fetching payment status: %s' % response_params)

            self.payment.external_id = response_params['trans_id']

            status = int(response_params['trans_status'])
            if status in (PayUTransactionStatus.AWAITING, PayUTransactionStatus.FINISHED):

                if self.payment.on_success(Decimal(response_params['trans_amount']) / Decimal('100')):
                    # fully paid
                    if status == PayUTransactionStatus.AWAITING:
                        accept_payment.delay(self.payment.id, session_id)

            elif status in (
                    PayUTransactionStatus.CANCELED,
                    PayUTransactionStatus.ERROR,
                    PayUTransactionStatus.REJECTED,
                    PayUTransactionStatus.REJECTED_AFTER_CANCEL):
                self.payment.on_failure()

        else:
            logger.error(u'Payment status wrong response signature: %s' % response_params)

    def accept_payment(self, session_id):
        params = {
            'pos_id': PaymentProcessor.get_backend_setting('pos_id'),
            'session_id': session_id,
            'ts': time.time()
        }
        key1 = PaymentProcessor.get_backend_setting('key1')
        key2 = PaymentProcessor.get_backend_setting('key2')
        params['sig'] = PaymentProcessor.compute_sig(
            params, self._GET_SIG_FIELDS, key1)
        for key in params.keys():
            params[key] = six.text_type(params[key]).encode('utf-8')
        data = six.text_type(urlencode(params)).encode('utf-8')
        url = self._GATEWAY_URL + 'UTF/Payment/confirm/txt'
        request = Request(url, data)
        response = urlopen(request)
        response_data = response.read().decode('utf-8')
        response_params = PaymentProcessor._parse_text_response(response_data)
        if response_params['status'] == 'OK':
            if PaymentProcessor.compute_sig(
                    response_params,
                    self._GET_ACCEPT_SIG_FIELDS, key2) != response_params['trans_sig']:
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
            map(lambda kv: (kv[0].rstrip(), kv[1].lstrip()),
                filter(
                    lambda l: len(l) == 2,
                    map(lambda l: l.split(':', 1),
                        text.splitlines()))
                )
        )
