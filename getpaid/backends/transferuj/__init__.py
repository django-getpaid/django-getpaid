# THIS PLUGIN IS DEPRECATED!

# new docs: https://docs.tpay.com/

from decimal import Decimal
import hashlib
import logging
from six.moves.urllib.parse import urlencode
from deprecated import deprecated
from django.utils.six import text_type
from django.core.exceptions import ImproperlyConfigured
from django.urls import reverse
from django.apps import apps
from django.utils.timezone import now
from django.utils.translation import ugettext_lazy as _
from getpaid import signals
from getpaid.backends import PaymentProcessorBase
from getpaid.utils import get_domain, build_absolute_uri

logger = logging.getLogger('getpaid.backends.transferuj')


@deprecated(version='1.8', reason="This plugin is outdated.")
class PaymentProcessor(PaymentProcessorBase):
    BACKEND = u'getpaid.backends.transferuj'
    BACKEND_NAME = _(u'Transferuj.pl')
    BACKEND_ACCEPTED_CURRENCY = (u'PLN',)
    BACKEND_LOGO_URL = u'getpaid/backends/transferuj/transferuj_logo.png'

    _GATEWAY_URL = u'https://secure.transferuj.pl'
    _REQUEST_SIG_FIELDS = (u'id', u'kwota', u'crc',)
    _ALLOWED_IP = (
        u'195.149.229.109',
        u'148.251.96.163',
        u'178.32.201.77',
        u'46.248.167.59',
        u'46.29.19.106',
    )

    _ONLINE_SIG_FIELDS = (u'id', u'tr_id', u'tr_amount', u'tr_crc',)
    _ACCEPTED_LANGS = (u'pl', u'en', u'de')

    @staticmethod
    def compute_sig(params, fields, key):
        text = u''
        for field in fields:
            text += text_type(params.get(field, ''))
        text += key
        text_encoded = text.encode('utf-8')
        return text_type(hashlib.md5(text_encoded).hexdigest())

    @staticmethod
    def online(ip, id, tr_id, tr_date, tr_crc, tr_amount, tr_paid, tr_desc,
               tr_status, tr_error, tr_email, md5sum):

        allowed_ip = PaymentProcessor.get_backend_setting('allowed_ip',
                                                          PaymentProcessor._ALLOWED_IP)

        if len(allowed_ip) != 0 and ip not in allowed_ip:
            logger.warning('Got message from not allowed IP %s' % ip)
            return u'IP ERR'

        params = {'id': id, 'tr_id': tr_id, 'tr_amount': tr_amount, 'tr_crc': tr_crc}
        key = PaymentProcessor.get_backend_setting('key')

        if md5sum != PaymentProcessor.compute_sig(params, PaymentProcessor._ONLINE_SIG_FIELDS, key):
            logger.warning('Got message with wrong sig, %s' % str(params))
            return u'SIG ERR'

        if int(id) != int(PaymentProcessor.get_backend_setting('id')):
            logger.warning('Got message with wrong id, %s' % str(params))
            return u'ID ERR'

        Payment = apps.get_model('getpaid', 'Payment')
        try:
            payment = Payment.objects.select_related('order').get(pk=int(tr_crc))
        except (Payment.DoesNotExist, ValueError):
            logger.error('Got message with CRC set to non existing Payment, %s' % str(params))
            return u'CRC ERR'

        logger.info(
            'Incoming payment: id=%s, tr_id=%s, tr_date=%s, tr_crc=%s, tr_amount=%s, '
            'tr_paid=%s, tr_desc=%s, tr_status=%s, tr_error=%s, tr_email=%s' % (
                id, tr_id, tr_date, tr_crc, tr_amount, tr_paid, tr_desc, tr_status, tr_error, tr_email))

        payment.external_id = tr_id
        payment.description = tr_email

        if tr_status == u'TRUE':
            # Due to Transferuj documentation, we need to check if amount is correct
            payment.amount_paid = Decimal(tr_paid)
            payment.paid_on = now()
            if payment.amount <= Decimal(tr_paid):
                # Amount is correct or it is overpaid
                payment.change_status('paid')
            else:
                payment.change_status('partially_paid')
        elif payment.status != 'paid':
            payment.change_status('failed')

        return u'TRUE'  # FIXME: should return "OK" for consistency

    def get_gateway_url(self, request):
        "Routes a payment to Gateway, should return URL for redirection."
        params = {
            'id': self.get_backend_setting('id'),
            'opis': self.get_order_description(self.payment,
                                               self.payment.order),
            # Here we put payment.pk as we can get order through payment model
            'crc': self.payment.pk,
            # amount is  in format XXX.YY PLN
            'kwota': text_type(self.payment.amount),
        }

        self._build_user_data(params)
        self._build_md5sum(params)
        self._build_urls(params, request)

        method = self.get_backend_setting('method', 'get').lower()
        if method not in ('post', 'get'):
            raise ImproperlyConfigured(
                'Transferuj.pl payment backend accepts only GET or POST'
            )

        if method == 'post':
            return (self._GATEWAY_URL, 'POST', params)

        params = {k: text_type(v).encode('utf-8') for k, v in params.items()}
        return (
            "{}?{}".format(self._GATEWAY_URL, urlencode(params)),
            "GET",
            {}
        )

    def _build_user_data(self, params):
        user_data = {
            'email': None,
            'lang': None,
        }
        signals.user_data_query.send(sender=None,
                                     order=self.payment.order,
                                     user_data=user_data)

        for lang in (user_data['lang'], self.get_backend_setting('lang', '')):
            if lang and lang.lower() in self._ACCEPTED_LANGS:
                params['jezyk'] = lang.lower()
                break
        if user_data['email']:
            params['email'] = user_data['email']

        return params

    def _build_md5sum(self, params):
        if not self.get_backend_setting('signing', True):
            return params

        params['md5sum'] = self.compute_sig(
            params, self._REQUEST_SIG_FIELDS,
            self.get_backend_setting('key'))

        return params

    def _build_urls(self, params, request):
        domain = get_domain(request)
        current_scheme = request.scheme

        # Backward compatibility:
        # If `force_ssl_online` was set to:
        # - True: scheme was set to HTTPS
        # - None: scheme was set to HTTP
        # Now default one is 'auto' to setup scheme that whole Django app is
        # running on.
        force_ssl_online = self.get_backend_setting('force_ssl_online', 'auto')
        force_ssl_return = self.get_backend_setting('force_ssl_return', 'auto')

        if force_ssl_online is not 'auto':
            online_scheme = 'https' if force_ssl_online else 'http'
        else:
            online_scheme = current_scheme
        if force_ssl_return is not 'auto':
            return_scheme = 'https' if force_ssl_return else 'http'
        else:
            return_scheme = current_scheme

        params['wyn_url'] = build_absolute_uri(
            view_name='getpaid:transferuj:online',
            scheme=online_scheme,
            domain=domain,
        )
        params['pow_url'] = build_absolute_uri(
            view_name='getpaid:transferuj:success',
            scheme=return_scheme,
            domain=domain,
            reverse_kwargs={'pk': self.payment.pk}
        )
        params['pow_url_blad'] = build_absolute_uri(
            view_name='getpaid:transferuj:failure',
            scheme=return_scheme,
            domain=domain,
            reverse_kwargs={'pk': self.payment.pk}
        )

        return params
