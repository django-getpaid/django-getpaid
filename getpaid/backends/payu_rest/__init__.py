# coding: utf-8
# Based on version 2.1 specs from http://developers.payu.com/pl/restapi.html
from __future__ import unicode_literals
import simplejson as json
import pendulum
from decimal import Decimal
import hashlib
import logging
import requests
from collections import OrderedDict

from django.urls import reverse
from django.utils import six
from six.moves.urllib.parse import urlencode
from django.core.exceptions import ImproperlyConfigured
from django.utils.translation import ugettext_lazy as _

from getpaid import signals
from getpaid import utils as getpaid_utils
from getpaid.backends import PaymentProcessorBase

logger = logging.getLogger('getpaid.backends.payu_rest')


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
    BACKEND = 'getpaid.backends.payu_rest'
    BACKEND_NAME = _('PayU REST API')
    BACKEND_ACCEPTED_CURRENCY = (
        "BGN", "CHF", "CZK", "DKK", "EUR", "GBP", "HRK", "HUF",
        "NOK", "PLN", "RON", "RUB", "SEK", "UAH", "USD",
    )
    BACKEND_LOGO_URL = 'getpaid/backends/payu_rest/payu_logo.png'

    # _GATEWAY_URL = 'https://secure.payu.com/'
    _GATEWAY_URL = 'https://secure.snd.payu.com/'
    _ACCEPTED_LANGS = (
        "pl", "en", "de", "cs", "bg", "el", "es", "et", "fi", "fr", "hr",
        "hu", "it", "lt", "lv", "pt", "ro", "ru", "sk", "sl", "sv", "uk",
    )
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
    def prepare_sig_data(params):
        ordered_params = OrderedDict(sorted(params.items(), key=lambda t: t[0]))
        return urlencode(ordered_params)

    @staticmethod
    def compute_sig(payload, key, algorithm='sha256'):
        algorithm = algorithm.lower().replace('-', '')
        hashfunc = getattr(hashlib, algorithm, None)
        assert hashfunc is not None
        if hashfunc is None:
            raise ImproperlyConfigured('Hashing algorithm not supported: {}'.format(algorithm))
        prepared_text = "{}{}".format(payload, key)
        return six.text_type(hashfunc(prepared_text.encode('utf-8')).hexdigest())

    @staticmethod
    def parse_payu_sig(sig):
        return {key.strip(): value.strip() for key, value in (
            item.split('=') for item in sig.split(';'))}

    @classmethod
    def online(cls, payload, ip, req_sig):
        """
        Receive and analyze request from payment service with information on payment status change.
        """

        from getpaid.models import Payment

        params = json.loads(payload)
        order_data = params.get('order', {})
        pos_id = order_data.get('merchantPosId')
        payment_id = order_data.get('extOrderId')

        key2 = cls.get_backend_setting('key2')

        if pos_id != cls.get_backend_setting('pos_id'):
            logger.warning('Received message for different pos: {}'.format(pos_id))
            return 'ERROR'

        req_sig_dict = cls.parse_payu_sig(req_sig)
        sig = cls.compute_sig(payload, key2, algorithm=req_sig_dict.get('algorithm', 'md5'))

        if sig != req_sig_dict['signature']:
            logger.warning('Received message with malformed signature. Payload: {}'.format(payload))
            return 'ERROR'

        try:
            payment = Payment.objects.get(id=payment_id)
        except Payment.DoesNotExist:
            logger.warning('Received message for nonexistent payment: {}.\nPayload: {}'.format(payment_id, payload))
            return 'ERROR'
        status = order_data['status']
        if payment.status != 'paid':
            if status == 'COMPLETED':
                payment.external_id = order_data['orderId']
                payment.amount = Decimal(order_data['totalAmount']) / Decimal(100)
                payment.amount_paid = payment.amount
                payment.currenct = order_data['currencyCode']
                payment.paid_on = pendulum.parse(params['localReceiptDateTime']).in_tz('utc')
                payment.description = order_data['description']
                payment.change_status('paid')

            elif status == 'PENDING':
                payment.change_status('in_progress')
            elif status in ['CANCELED', 'REJECTED']:
                payment.change_status('cancelled')
        return 'OK'

    def get_gateway_url(self, request):
        """
        Tricky process that requires to get auth key, send order via POST and
        then present final URL for redirection to finalize payment.
        """

        grant_type = self.get_backend_setting('grant_type', 'client_credentials')
        if grant_type == 'client_credentials':
            client_id = self.get_backend_setting('client_id')
            client_secret = self.get_backend_setting('client_secret')
            url = "{gateway_url}pl/standard/user/oauth/authorize?" \
                  "grant_type={grant_type}&client_id={client_id}&client_secret={client_secret}".format(
                gateway_url=self._GATEWAY_URL,
                grant_type=grant_type, client_id=client_id, client_secret=client_secret)
        elif grant_type == 'trusted_merchant':
            raise ImproperlyConfigured('grant_type not yet supported')
        else:
            raise ImproperlyConfigured('grant_type should be one of: "trusted_merchant", "client_credentials"')

        response = requests.get(url)
        assert response.status_code == 200

        response_data = response.json()
        access_token = response_data['access_token']
        token_type = response_data['token_type']

        headers = {"Authorization": "{token_type} {access_token}".format(
            token_type=token_type.title(), access_token=access_token)}

        pos_id = self.get_backend_setting('pos_id', None)

        user_data = {
            'email': None,
            'lang': None,
        }

        signals.user_data_query.send(
            sender=None, order=self.payment.order, user_data=user_data)

        if not user_data['email']:
            raise ImproperlyConfigured

        buyer_info = dict(  # dane kupującego
            email=user_data['email'],
        )

        if user_data['lang'] \
            and user_data['lang'].lower() in self._ACCEPTED_LANGS:
            buyer_info['language'] = user_data['lang'].lower()
        elif self.get_backend_setting('lang', False) and \
            self.get_backend_setting('lang').lower() in self._ACCEPTED_LANGS:
            buyer_info['language'] = six.text_type(self.get_backend_setting('lang').lower())

        customer_id = user_data.get('id', None)
        if customer_id:
            buyer_info['extCustomerId'] = customer_id

        customer_first_name = user_data.get('first_name', None)
        if customer_first_name:
            buyer_info['firstName'] = customer_first_name

        customer_last_name = user_data.get('last_name', None)
        if customer_last_name:
            buyer_info['last_Namme'] = customer_last_name

        customer_phone = user_data.get('phone', None)
        if customer_phone:
            buyer_info['phone'] = customer_phone

        current_site = getpaid_utils.get_domain(request)
        use_ssl = self.get_backend_setting('ssl_return', True)

        notify_url = "http{}://{}{}".format(
            's' if use_ssl else '',
            current_site,
            reverse('getpaid:payu_rest:confirm')
        )

        params = dict(
            customerIp=getpaid_utils.get_ip_address(request),
            merchantPosId=pos_id,
            description=self.get_order_description(self.payment, self.payment.order),
            currencyCode=self.payment.currency.upper(),
            totalAmount=str(int(self.payment.amount * 100)),
            buyer=buyer_info,
            products=[dict(
                name='Payment #{} from {}'.format(self.payment.pk, current_site),
                unitPrice=str(int(self.payment.amount * 100)),
                quantity="1",
                ## optional:
                # virtual=True,
                # listingDate='',
            )],

            ## optional:
            notifyUrl=notify_url,
            extOrderId=str(self.payment.pk),
            # validityTime='',
            # additionalDescription='',
            continueUrl='http://127.0.0.1:8000/',
            # payMethods=None,
        )

        order_url = "{gateway_url}api/v2_1/orders".format(gateway_url=self._GATEWAY_URL)

        order_register = requests.post(order_url, json=params, headers=headers, allow_redirects=False)
        order_register_data = order_register.json()
        status = order_register_data.get('status', {}).get('statusCode', '')
        if status != 'SUCCESS':
            logger.error('Houston, we have a problem with this payment trajectory: {}'.format(status))
            return reverse('getpaid:failure-fallback', kwargs=dict(pk=self.payment.pk)), 'GET', {}
        final_url = order_register_data.get('redirectUri')

        return final_url, 'GET', {}

    def get_payment_status(self, *args, **kwargs):
        # FIXME - might be needed in other flow
        pass
