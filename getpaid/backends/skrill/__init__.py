import datetime
from decimal import Decimal
from django.contrib.sites.models import Site
from django.core.urlresolvers import reverse
import hashlib
import logging
import urllib
import urllib2
from xml.dom.minidom import parseString, Node
from django.core.exceptions import ImproperlyConfigured
from django.template.base import Template
from django.template.context import Context
from django.utils.timezone import utc
from django.utils.translation import ugettext_lazy as _
import time
from getpaid import signals
from getpaid.backends import PaymentProcessorBase

logger = logging.getLogger('getpaid.backends.skrill')


class SkrillUTransactionStatus:
    PENDING = 0
    PROCESSED = 2
    CANCELED = -1
    FAILED = -2
    CHARGEBACK = -3

class PaymentProcessor(PaymentProcessorBase):
    BACKEND = 'getpaid.backends.skrill'
    BACKEND_NAME = _('Skrill')
    BACKEND_ACCEPTED_CURRENCY = ('PLN','USD','EUR', 'GPB' )
    BACKEND_LOGO_URL = 'getpaid/backends/skrill/skrill_logo.png'

    _GATEWAY_URL = 'https://www.moneybookers.com/app/payment.pl'
    _ACCEPTED_LANGS = ('pl', 'en')

    _ONLINE_SIG_FIELDS = ('merchant_id', 'transaction_id', 'secret_word_hash', 'mb_amount', 'mb_currency', 'status')


    @staticmethod
    def compute_sig(params, fields, key):
        text = ''
        m = hashlib.md5(key)
        params.update({'secret_word_hash': m.hexdigest().upper()})

        for field in fields:
            text += params.get(field, '')
        return hashlib.md5(text).hexdigest().upper()

    @staticmethod
    def online(merchant_id, transaction_id, mb_amount, amount, mb_currency, currency, status, sig, mb_transaction_id, pay_from_email):

        currency_suffix = PaymentProcessor.get_currency_suffix(currency)

        params = {'merchant_id' : merchant_id, 'transaction_id': transaction_id, 'mb_amount': mb_amount, 'amount':amount, 'mb_currency':mb_currency, 'currency':currency, 'status':status, 'sig':sig}

        key2 = PaymentProcessor.get_backend_setting('secret_word%s' % currency_suffix)
        sig_check = PaymentProcessor.compute_sig(params, PaymentProcessor._ONLINE_SIG_FIELDS, key2)
        if sig != sig_check:
            logger.warning('Got message with wrong sig, %s, expected sig %s' % (str(params), sig_check))
            return 'SIG ERR'

        try:
            params['merchant_id'] = int(params['merchant_id'])
        except ValueError:
            return 'MERCHANT_ID ERR'
        if params['merchant_id'] != int(PaymentProcessor.get_backend_setting('merchant_id%s' % currency_suffix)):
            return 'MERCHANT_ID ERR'

        from getpaid.models import Payment
        try:
            payment = Payment.objects.get(pk=int(params['transaction_id']))
        except (ValueError, Payment.DoesNotExist):
            logger.error('Got message for non existing Payment, %s' % str(params))
            return 'PAYMENT ERR'

        if  params['currency'] != payment.currency.upper():
            logger.error('Got message with wrong currency, %s' % str(params))
            return 'CURRENCY ERR'

        try:
            status = int(status)
        except ValueError:
            return 'STATUS ERR'

        payment.external_id = mb_transaction_id
        payment.description = pay_from_email

        if status == SkrillUTransactionStatus.PROCESSED:
            payment.amount_paid = Decimal(amount)
            payment.paid_on = datetime.datetime.utcnow().replace(tzinfo=utc)
            if Decimal(amount) >= payment.amount:
                logger.debug('SKRILL: status PAID')
                payment.change_status('paid')
            else:
                payment.change_status('partially_paid')
        elif status in (    SkrillUTransactionStatus.CANCELED,
                            SkrillUTransactionStatus.FAILED,
                            SkrillUTransactionStatus.CHARGEBACK):
            logger.debug('SKRILL: status FAILED')
            payment.change_status('failed')
        else:
            logger.error('SKRILL: unknown status %d' % status)

        return 'OK'

    @staticmethod
    def get_currency_suffix(currency):
    #check for test configuration
        testing = PaymentProcessor.get_backend_setting('testing', False)
        multi_acc = PaymentProcessor.get_backend_setting('multi', False)
        if testing:
            currency_suffix = '_test'
        elif multi_acc:
            currency_suffix = '_%s' % currency.lower() if currency else ""
        else:
            currency_suffix = ""
        logger.debug('currency suffix: %s' % currency_suffix)
        return currency_suffix

    def get_return_url(self, type, pk=None):
        kwargs = {'pk' : pk} if pk else {}
        url = reverse('getpaid-skrill-%s' % type, kwargs=kwargs)
        current_site = Site.objects.get_current()
        if PaymentProcessor.get_backend_setting('force_ssl', False):
            return 'https://%s%s' % (current_site.domain, url)
        else:
            return 'http://%s%s' % (current_site.domain, url)


    def get_gateway_url(self, request):
        """
        Routes a payment to Gateway, should return URL for redirection.

        """
        currency_suffix = PaymentProcessor.get_currency_suffix(self.payment.currency)

        user_data = {
            'email': None,
            'lang': None,
            'first_name': None,
            'last_name': None,
            }

        signals.user_data_query.send(sender=None, order=self.payment.order, user_data=user_data)
        params = {
            #test
            'pay_to_email': PaymentProcessor.get_backend_setting('merchant_email%s' % currency_suffix),
            #spoofed user data
            'title': 'Mr',
            'firstname': user_data.get('first_name', ''),
            'lastname': user_data.get('last_name', ''),
            'address': 'Payerstreet',
            'city': 'London',
            'phone_number': '0207123456',
            'postal_code': 'EC45MQ',
            'country': 'GBR',
        }

        if user_data['email']:
            params['pay_from_email'] = user_data['email']

        if user_data['lang'] and user_data['lang'].lower() in PaymentProcessor._ACCEPTED_LANGS:
            params['language'] = user_data['lang'].lower()
        elif PaymentProcessor.get_backend_setting('lang', False) and\
                PaymentProcessor.get_backend_setting('lang').lower() in PaymentProcessor._ACCEPTED_LANGS:
            params['language'] = PaymentProcessor.get_backend_setting('lang').lower()

        #DOB
        #date_of_birth


        # Here we put payment.pk as we can get order through payment model
        params['transaction_id'] = self.payment.pk
        # total amount
        params['amount'] = self.payment.amount
        #currency
        params['currency'] = self.payment.currency.upper()
        #sescription
        params['amount_description'] = self.get_order_description(self.payment, self.payment.order)
        #payment methods
        params['payment_methods'] = PaymentProcessor.get_backend_setting('payment_methods')
        #fast checkout
        params['payment_type'] = 'WLT'
        #hide login screen
        params['hide_login'] = 1
        # custom session_id
        #params['session_id'] = "%d:%s" % (self.payment.pk, str(time.time()))

        #urls
        #params['logo_url'] = PaymentProcessor.get_backend_setting('logo_url);
        params['return_url'] = self.get_return_url('success', self.payment.pk)
        params['return_url_target'] ='_top'
        params['cancel_url'] = self.get_return_url('failure', self.payment.pk)
        params['cancel_url_target'] ='_top'
        params['status_url'] = self.get_return_url('online')
        logger.debug('sending payment to skrill: %s' % str(params))
        return self._GATEWAY_URL, 'POST', params