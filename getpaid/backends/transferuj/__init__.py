from decimal import Decimal
import hashlib
import logging
import urllib
import datetime
from django.contrib.sites.models import Site
from django.core.urlresolvers import reverse
from django.db.models.loading import get_model
from django.template.base import Template
from django.template.context import Context
from django.utils.timezone import utc
from django.utils.translation import ugettext_lazy as _
from getpaid.backends import PaymentProcessorBase

logger = logging.getLogger('getpaid.backends.transferuj')

Payment = get_model('getpaid', 'Payment')

class PaymentProcessor(PaymentProcessorBase):
    BACKEND = 'getpaid.backends.transferuj'
    BACKEND_NAME = _('Transferuj.pl')
    BACKEND_ACCEPTED_CURRENCY = ('PLN', )
    _GATEWAY_URL = 'https://secure.transferuj.pl'
    _REQUEST_SIG_FIELDS = ('id', 'kwota', 'crc',)
    _ALLOWED_IP = ('195.149.229.109', )

    _ONLINE_SIG_FIELDS = ('id', 'tr_id', 'tr_amount', 'tr_crc', )

    @staticmethod
    def compute_sig(params, fields, key):
        text = ''
        for field in fields:
            text += unicode(params.get(field, '')).encode('utf-8')
        text += key
        return hashlib.md5(text).hexdigest()

    @staticmethod
    def online(ip, id, tr_id, tr_date, tr_crc, tr_amount, tr_paid, tr_desc, tr_status, tr_error, tr_email, md5sum):

        allowed_ip = PaymentProcessor.get_backend_setting('allowed_ip', PaymentProcessor._ALLOWED_IP)

        if len(allowed_ip) != 0 and ip not in allowed_ip:
            logger.warning('Got message from not allowed IP %s' % str(allowed_ip))
            return 'IP ERR'

        params = {'id' : id, 'tr_id': tr_id, 'tr_amount': tr_amount, 'tr_crc': tr_crc}
        key = PaymentProcessor.get_backend_setting('key')

        if md5sum != PaymentProcessor.compute_sig(params, PaymentProcessor._ONLINE_SIG_FIELDS, key):
            logger.warning('Got message with wrong sig, %s' % str(params))
            return 'SIG ERR'

        if int(id) != int(PaymentProcessor.get_backend_setting('id')):
            logger.warning('Got message with wrong id, %s' % str(params))
            return 'ID ERR'

        try:
            payment = Payment.objects.select_related('order').get(pk=int(tr_crc))
        except (Payment.DoesNotExist, ValueError):
            logger.error('Got message with CRC set to non existing Payment, %s' % str(params))
            return 'CRC ERR'

        logger.info('Incoming payment: id=%s, tr_id=%s, tr_date=%s, tr_crc=%s, tr_amount=%s, tr_paid=%s, tr_desc=%s, tr_status=%s, tr_error=%s, tr_email=%s' % (id, tr_id, tr_date, tr_crc, tr_amount, tr_paid, tr_desc, tr_status, tr_error, tr_email))

        if tr_status == 'TRUE':
            # Due to Transferuj documentation, we need to check if amount is correct
            payment.amount_paid = Decimal(tr_paid)
            payment.paid_on = datetime.datetime.utcnow().replace(tzinfo=utc)
            if payment.amount <= Decimal(tr_paid):
                # Amount is correct or it is overpaid
                payment.change_status('paid')
            else :
                payment.change_status('partially_paid')
        elif payment.status != 'paid':
            payment.change_status('failed')


        return 'TRUE'

    def get_gateway_url(self, request):
        """
        Routes a payment to Gateway, should return URL for redirection.

        """
        params = {'id': PaymentProcessor.get_backend_setting('id'),
                  'opis': PaymentProcessor.get_backend_setting('description', '')}
        if not params['opis']:
            params['opis'] = unicode(self.payment.order)
        else:
            params['opis'] = Template(params['opis']).render(Context({"payment": self.payment, "order": self.payment.order}))

        key = PaymentProcessor.get_backend_setting('key')

        signing = PaymentProcessor.get_backend_setting('signing', True)

        # Here we put payment.pk as we can get order through payment model
        params['crc'] = self.payment.pk

        # amount is  in format XXX.YY PLN
        params['kwota'] = str(self.payment.amount)

        if signing:
            params['md5sum'] = PaymentProcessor.compute_sig(params, self._REQUEST_SIG_FIELDS, key)

        for key in params.keys():
            params[key] = unicode(params[key]).encode('utf-8')

        current_site = Site.objects.get_current()

        if PaymentProcessor.get_backend_setting('force_ssl_online', False):
            params['wyn_url'] = 'https://' + current_site.domain + reverse('getpaid-transferuj-online')
        else:
            params['wyn_url'] = 'http://' + current_site.domain + reverse('getpaid-transferuj-online')

        if PaymentProcessor.get_backend_setting('force_ssl_return', False):
            params['pow_url'] = 'https://' + current_site.domain + reverse('getpaid-transferuj-success', kwargs={'pk': self.payment.pk})
            params['pow_url_blad'] = 'https://' + current_site.domain + reverse('getpaid-transferuj-failure', kwargs={'pk': self.payment.pk})
        else:
            params['pow_url'] = 'http://' + current_site.domain + reverse('getpaid-transferuj-success', kwargs={'pk': self.payment.pk})
            params['pow_url_blad'] = 'http://' + current_site.domain + reverse('getpaid-transferuj-failure', kwargs={'pk': self.payment.pk})

        gateway_url = self._GATEWAY_URL + '?' + urllib.urlencode(params)
        return gateway_url

