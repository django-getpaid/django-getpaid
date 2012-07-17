import hashlib
import logging
import urllib
from django.template.base import Template
from django.template.context import Context
from django.utils.translation import ugettext_lazy as _
import time
from getpaid.backends import PaymentProcessorBase
from celery import task


logger = logging.getLogger('getpaid.backends.payu')

@task()
def get_payment_status_task(payment_id):
    from getpaid.models import Payment
    try:
        payment = Payment.objects.get(pk=int(payment_id))
    except Payment.DoesNotExist:
        logger.error('Payment does not exist pk=%d' % payment_id)
        return
    processor = PaymentProcessor(payment)
    processor.get_payment_status()




class PaymentProcessor(PaymentProcessorBase):
    BACKEND = 'getpaid.backends.payu'
    BACKEND_NAME = _('PayU')
    BACKEND_ACCEPTED_CURRENCY = ('PLN', )

    _GATEWAY_URL = 'https://www.platnosci.pl/paygw/'
    _REQUEST_SIG_FIELDS = ('pos_id', 'pay_type', 'session_id', 'pos_auth_key',
        'amount', 'desc', 'desc2', 'trsDesc', 'order_id', 'first_name', 'last_name',
        'payback_login', 'street', 'street_hn', 'street_an', 'city', 'post_code',
        'country', 'email', 'phone', 'language', 'client_ip', 'ts' )
    _ONLINE_SIG_FIELDS = ('pos_id', 'session_id', 'ts',)

    @staticmethod
    def compute_sig(params, fields, key):
        text = ''
        for field in fields:
            text += unicode(params.get(field, '')).encode('utf-8')
        text += key
        return hashlib.md5(text).hexdigest()

    @staticmethod
    def online(pos_id, session_id, ts, sig):
        params = {'pos_id' : pos_id, 'session_id': session_id, 'ts': ts, 'sig': sig}


        key2 = PaymentProcessor.get_backend_setting('key2')
        if sig != PaymentProcessor.compute_sig(params, PaymentProcessor._ONLINE_SIG_FIELDS, key2):
            logger.warning('OnlineView got message with wrong sig, %s' % str(params))
            return 'SIG ERR'

        try:
            params['pos_id'] = int(params['pos_id'])
        except ValueError:
            return 'POS_ID ERR'
        if params['pos_id'] != int(PaymentProcessor.get_backend_setting('pos_id')):
            return 'POS_ID ERR'




        try:
            payment_id , session = session_id.split(':')
        except ValueError:
            logger.warning('OnlineView got message with wrong session_id, %s' % str(params))
            return 'SESSION_ID ERR'

        print "REFRESH PAYMENT", payment_id
        get_payment_status_task.delay(payment_id)
        return 'OK'

    def get_gateway_url(self, request):
        """
        Routes a payment to Gateway, should return URL for redirection.

        """
        params = {}
        params['pos_id'] = PaymentProcessor.get_backend_setting('pos_id')
        params['pos_auth_key'] = PaymentProcessor.get_backend_setting('pos_auth_key')
        params['desc'] = PaymentProcessor.get_backend_setting('description', '')
        if not params['desc']:
            params['desc'] = unicode(self.payment.order)
        else:
            params['desc'] = Template(params['desc']).render(Context({"payment": self.payment, "order": self.payment.order}))

        key1 = PaymentProcessor.get_backend_setting('key1')

        signing = PaymentProcessor.get_backend_setting('signing', True)
        testing = PaymentProcessor.get_backend_setting('testing', False)

        if testing:
            # Switch to testing mode, where payment method is set to "test payment"->"t"
            # Warning: testing mode need to be enabled also in payu.pl system for this POS
            params['pay_type'] = 't'

        # Here we put payment.pk as we can get order through payment model
        params['order_id'] = self.payment.pk

        #FIXME
#        params['first_name'] = u"Jan"
#        params['last_name'] = u"Kowalski"
#        params['email'] = u"cypreess@gmail.com"

        # amount is number of Grosz, not PLN
        params['amount'] = int(self.payment.amount * 100)

        params['session_id'] = "%d:%s" % (self.payment.pk, str(time.time()))

        #Warning: please make sure that this header actually has client IP
        #         rather then web server proxy IP in your WSGI environment
        params['client_ip'] = request.META['REMOTE_ADDR']

        params['client_ip'] = '87.239.219.102' #FIXME
        print request.META['REMOTE_ADDR']

        if signing:
            params['ts'] = time.time()
            params['sig'] = PaymentProcessor.compute_sig(params, self._REQUEST_SIG_FIELDS, key1)

        for key in params.keys():
            params[key] = unicode(params[key]).encode('utf-8')

        gateway_url = self._GATEWAY_URL + 'UTF/NewPayment?' + urllib.urlencode(params)
        return gateway_url

    def get_payment_status(self):
        print "PROCESSING PAYMENT", self.payment