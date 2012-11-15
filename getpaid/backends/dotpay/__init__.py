import datetime
from decimal import Decimal
import hashlib
import logging
import urllib
import urllib2
from xml.dom.minidom import parseString, Node
from django.contrib.sites.models import Site
from django.core.urlresolvers import reverse
from django.template.base import Template
from django.template.context import Context
from django.utils.timezone import utc
from django.utils.translation import ugettext_lazy as _
import time
from getpaid.backends import PaymentProcessorBase
from getpaid.backends.payu.tasks import get_payment_status_task
from getpaid.signals import user_data_query

logger = logging.getLogger('getpaid.backends.dotpay')


class DotpayTransactionStatus:
    pass

class PaymentProcessor(PaymentProcessorBase):
    BACKEND = 'getpaid.backends.dotpay'
    BACKEND_NAME = _('Dotpay')
    BACKEND_ACCEPTED_CURRENCY = ('PLN', 'EUR', 'USD', 'GBP', 'JPY', 'CZK', 'SEK' )

    _GATEWAY_URL = 'https://ssl.dotpay.eu/'
#
#    _REQUEST_SIG_FIELDS = ('pos_id', 'pay_type', 'session_id', 'pos_auth_key',
#                           'amount', 'desc', 'desc2', 'trsDesc', 'order_id', 'first_name', 'last_name',
#                           'payback_login', 'street', 'street_hn', 'street_an', 'city', 'post_code',
#                           'country', 'email', 'phone', 'language', 'client_ip', 'ts' )
#    _ONLINE_SIG_FIELDS = ('pos_id', 'session_id', 'ts',)
#    _GET_SIG_FIELDS =  ('pos_id', 'session_id', 'ts',)
#    _GET_RESPONSE_SIG_FIELDS =  ('pos_id', 'session_id', 'order_id', 'status', 'amount', 'desc', 'ts',)

#    @staticmethod
#    def compute_sig(params, fields, key):
#        text = ''
#        for field in fields:
#            text += unicode(params.get(field, '')).encode('utf-8')
#        text += key
#        return hashlib.md5(text).hexdigest()

#    @staticmethod
#    def online(pos_id, session_id, ts, sig):
#        params = {'pos_id' : pos_id, 'session_id': session_id, 'ts': ts, 'sig': sig}
#
#
#        key2 = PaymentProcessor.get_backend_setting('key2')
#        if sig != PaymentProcessor.compute_sig(params, PaymentProcessor._ONLINE_SIG_FIELDS, key2):
#            logger.warning('Got message with wrong sig, %s' % str(params))
#            return 'SIG ERR'
#
#        try:
#            params['pos_id'] = int(params['pos_id'])
#        except ValueError:
#            return 'POS_ID ERR'
#        if params['pos_id'] != int(PaymentProcessor.get_backend_setting('pos_id')):
#            return 'POS_ID ERR'
#
#        try:
#            payment_id , session = session_id.split(':')
#        except ValueError:
#            logger.warning('Got message with wrong session_id, %s' % str(params))
#            return 'SESSION_ID ERR'
#
#        get_payment_status_task.delay(payment_id, session_id)
#        return 'OK'

    def get_URLC(self):
        urlc = reverse('getpaid-dotpay-online')
        current_site = Site.objects.get_current()
        if PaymentProcessor.get_backend_setting('force_ssl', False):
            return 'https://%s%s' % (current_site.domain, urlc)
        else:
            return 'http://%s%s' % (current_site.domain, urlc)

    def get_URL(self, pk):
        current_site = Site.objects.get_current()
        url = reverse('getpaid-dotpay-return', kwargs={'pk' : pk})
        if PaymentProcessor.get_backend_setting('force_ssl', False):
            return 'https://%s%s' % (current_site.domain, url)
        else:
            return 'http://%s%s' % (current_site.domain, url)



    def get_gateway_url(self, request):
        """
        Routes a payment to Gateway, should return URL for redirection.

        """
        params = {
            'id': PaymentProcessor.get_backend_setting('id'),
            'description' : self.get_order_description(self.payment, self.payment.order),
            'amount' : str(self.payment.amount),
            'currency' : self.payment.currency,
            'type' : 0, # show "return" button after finished payment
            'control' : str(self.payment.pk),
            'URL': self.get_URL(self.payment.pk),
            'URLC': self.get_URLC(),
        }

        user_data = {
            'email' : None,
            'lang' : None,
        }
        #FIXME: TEst me
        user_data_query.send(self.payment.order, user_data)

        if PaymentProcessor.get_backend_setting('lang', False):
            params['lang'] = PaymentProcessor.get_backend_setting('lang')
        if PaymentProcessor.get_backend_setting('onlinetransfer', False):
            params['onlinetransfer'] = 1
        if PaymentProcessor.get_backend_setting('p_email', False):
            params['p_email'] = PaymentProcessor.get_backend_setting('p_email')
        if PaymentProcessor.get_backend_setting('p_info', False):
            params['p_info'] = PaymentProcessor.get_backend_setting('p_info')
        if PaymentProcessor.get_backend_setting('tax', False):
            params['tax'] = 1


        gateway_url = self._GATEWAY_URL + '?' + urllib.urlencode(params)
        return gateway_url

#    def get_payment_status(self, session_id):
#        params = {'pos_id': PaymentProcessor.get_backend_setting('pos_id'), 'session_id': session_id, 'ts': time.time()}
#        key1 = PaymentProcessor.get_backend_setting('key1')
#        key2 = PaymentProcessor.get_backend_setting('key2')
#
#        params['sig'] = PaymentProcessor.compute_sig(params, self._GET_SIG_FIELDS, key1)
#
#        for key in params.keys():
#            params[key] = unicode(params[key]).encode('utf-8')
#
#        data = urllib.urlencode(params)
#        url = self._GATEWAY_URL + 'UTF/Payment/get/xml'
#        request = urllib2.Request(url, data)
#        response = urllib2.urlopen(request)
#        xml_response = response.read()
#        xml_dom = parseString(xml_response)
#        tag_response = xml_dom.getElementsByTagName('trans')[0]
#        response_params={}
#        for tag in tag_response.childNodes:
#            if tag.nodeType == Node.ELEMENT_NODE:
#                response_params[tag.nodeName] = reduce(lambda x,y: x + y.nodeValue, tag.childNodes, u"")
#        if PaymentProcessor.compute_sig(response_params, self._GET_RESPONSE_SIG_FIELDS, key2) == response_params['sig']:
#
#            if not (int(response_params['pos_id']) == params['pos_id'] or int(response_params['order_id']) == self.payment.pk):
#                logger.error('Wrong pos_id and/or payment for Payment/get response data %s' % str(response_params))
#                return
#
#            status = int(response_params['status'])
#            if status == PayUTransactionStatus.FINISHED:
#                self.payment.amount_paid = Decimal(response_params['amount']) / Decimal('100')
#                self.payment.paid_on = datetime.datetime.utcnow().replace(tzinfo=utc)
#                if Decimal(response_params['amount']) / Decimal('100') >= self.payment.amount:
#                    self.payment.change_status('paid')
#                else:
#                    self.payment.change_status('partially_paid')
#            elif status in (    PayUTransactionStatus.CANCELED,
#                                PayUTransactionStatus.ERROR,
#                                PayUTransactionStatus.REJECTED,
#                                PayUTransactionStatus.REJECTED_AFTER_CANCEL):
#                self.payment.change_status('failed')
#
#
#        else:
#            logger.error('Wrong signature for Payment/get response data %s' % str(response_params))
