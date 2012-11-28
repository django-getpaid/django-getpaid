# -*- coding: utf-8 -*-
from decimal import Decimal
import logging
from pyexpat import ExpatError
import urllib
import urllib2
from xml.dom.minidom import parseString, Node
import datetime
from django.core.exceptions import ImproperlyConfigured
from django.db.models import get_model
from django.utils.timezone import utc
from getpaid.signals import user_data_query
from getpaid.backends import PaymentProcessorBase
from getpaid.backends.pagseguro.signals import shopping_cart_items_query

logger = logging.getLogger('getpaid.backends.pagseguro')


class PagSeguroTransactionStatus:
    PENDING = 1
    VERIFYING = 2
    PAID = 3
    AVAILABLE = 4
    IN_DISPUTE = 5
    REFUNDED = 6
    CANCELED = 7

class PaymentProcessor(PaymentProcessorBase):
    BACKEND = 'getpaid.backends.pagseguro'
    BACKEND_NAME = 'PagSeguro'
    BACKEND_ACCEPTED_CURRENCY = ('BRL', )

    _GATEWAY_URL = 'https://pagseguro.uol.com.br/checkout/checkout.jhtml'
    _NOTIFICATION_URL = 'https://ws.pagseguro.uol.com.br/v2/transactions/notifications/'
    _ITEM_DATA_REQUIRED_FIELDS = ('id', 'description', 'quantity', 'value')

    _ITEM_DATA_TO_PAGSEGURO = {
        'id': "item_id_%i",
        'description': "item_descr_%i",
        'quantity': "item_quant_%i",
        'value': "item_valor_%i",
        'shipping': "item_frete_%i",
        'weight': "item_peso_%i",
    }

    _USER_DATA_TO_PAGSEGURO = {
        'name': 'cliente_nome', # Nome completo do cliente.
        'address_zip_code': 'cliente_cep', # O CEP de 8 dígitos do cliente. Somente números (ex: 22345678)
        'address': 'cliente_end', # Logradouro do cliente (ex: Rua, Av, etc.)
        'address_number': 'cliente_num', # Nº do imóvel do cliente (ex: 12)
        'address_complement': 'cliente_compl', # Complemento (ex: Sala 109 ou Casa 1)
        'address_quarter': 'cliente_bairro', # Bairro do cliente
        'address_city': 'cliente_cidade', # Cidade do cliente (ex: São Paulo)
        'address_state': 'cliente_uf', # Estado do cliente (SP) no formato duas letras
        'phone_area_code': 'cliente_ddd', # DDD do Telefone do cliente (ex: 11) no formato 2 números
        'phone': 'cliente_tel', # Telefone fixo do cliente
        'email': 'cliente_email', # E-mail do cliente
    }

    def _validate_item(self, item):
        # checks if all required fields are present
        for field in self._ITEM_DATA_REQUIRED_FIELDS:
            if field not in item:
                raise ImproperlyConfigured("Item does not have the required field '%s'." % field)

    def get_url_params(self):
        url_params = {}
        url_params.update(self.merchant_info)

        # add shopping cart items
        for i, item in enumerate(self.cart_items):
            self._validate_item(item)
            for field in self._ITEM_DATA_TO_PAGSEGURO:
                if field in item: url_params[self._ITEM_DATA_TO_PAGSEGURO[field] % (i+1)] = item[field]

        # add customer, all fields are optional
        for field in self._USER_DATA_TO_PAGSEGURO:
            if field in self.customer_info: url_params[self._USER_DATA_TO_PAGSEGURO[field]] = self.customer_info[field]

        return url_params

    def get_gateway_url(self, request):
        self.customer_info = {}
        self.cart_items = []
        self.merchant_info = {
            'email_cobranca': PaymentProcessor.get_backend_setting('email'),
            'tipo' : 'CP',
            'moeda': self.payment.currency,
            'encoding': 'UTF-8',

            'ref_transacao': self.payment.id,
            }

        # collect shopping cart items
        self.cart_items = []
        shopping_cart_items_query.send(sender=None, order=self.payment.order, shopping_cart_items=self.cart_items)

        # collect customer data
        self.customer_info = {}
        user_data_query.send(sender=None, order=self.payment.order, user_data=self.customer_info)

        return self._GATEWAY_URL, 'POST', self.get_url_params()

    @staticmethod
    def process_notification(notification_code, notification_type):
        params = urllib.urlencode({'email': PaymentProcessor.get_backend_setting('email'),
                                 'token': PaymentProcessor.get_backend_setting('token')})
        url = PaymentProcessor._NOTIFICATION_URL
        request = urllib2.Request("%s%s/?%s" % (url, notification_code, params))
        response = urllib2.urlopen(request)
        xml_response = response.read()

        try:
            xml_dom = parseString(xml_response)
        except ExpatError:
            logger.error('Failed reading xml %s' % xml_response)

        status = int(xml_dom.getElementsByTagName('status')[0].firstChild.nodeValue)
        gross_amount_paid = xml_dom.getElementsByTagName('grossAmount')[0].firstChild.nodeValue

        try:
            reference = xml_dom.getElementsByTagName('reference')[0].firstChild.nodeValue
        except IndexError:
            logger.error('Reference parameter not found')
            return

        Payment = get_model('getpaid', 'Payment')
        try:
            payment = Payment.objects.get(pk=int(reference))
        except Payment.DoesNotExist:
            logger.error('Payment does not exist pk=%d' % reference)
            return

        if status == PagSeguroTransactionStatus.PAID:
            payment.amount_paid = Decimal(gross_amount_paid)
            payment.paid_on = datetime.datetime.utcnow().replace(tzinfo=utc)
            payment.change_status('paid')
        elif status in (PagSeguroTransactionStatus.CANCELED,
                        PagSeguroTransactionStatus.REFUNDED):
            payment.change_status('failed')