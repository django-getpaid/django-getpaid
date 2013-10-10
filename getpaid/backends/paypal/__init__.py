# -*- coding: utf-8 -*-
from decimal import Decimal
import logging
import datetime
from django.core.urlresolvers import reverse
from django.db.models import get_model
from django.utils.timezone import utc
import requests
import time
from django.utils.translation import ugettext_lazy as _
from getpaid.signals import user_data_query
from getpaid.backends import PaymentProcessorBase
import urllib2
import urllib
from xml.dom.minidom import parseString


logger = logging.getLogger('getpaid.backends.paypal')

# see: https://paypal.uol.com.br/v2/guia-de-integracao/api-de-notificacoes.html#v2-item-api-de-notificacoes-status-da-transacao
class paypalTransactionStatus:
    IN_PROGRESS = 1     # payment transaction started and waiting be paid
    IN_ANALISE = 2
    PAID    = 3
    AVAILABLE = 4
    IN_DISPUTE = 5
    REFUNDED = 6
    CANCELED = 7


class PaymentProcessor(PaymentProcessorBase):
    BACKEND = 'getpaid.backends.paypal'
    BACKEND_NAME = _('paypal')
    BACKEND_ACCEPTED_CURRENCY = ('BRL', )
    BACKEND_LOGO_URL = 'getpaid/backends/paypal/avista_estatico_550_70.gif'

    _SEND_INSTRUCTION_PAGE = '/checkout.php?'
    _CHECKOUT_INSTRUCTION_PAGE = "checkout/?"
    _TRANSACTION_INSTRUCTION_PAGE = "checkout/payment.html?code="
    _ITEM_DATA_REQUIRED_FIELDS = ('id', 'description', 'quantity', 'value')

    _USER_DATA_TO_paypal = {
        'name': 'Nome',  # Nome completo do cliente.
        'address': 'Logradouro',  # Logradouro do cliente (ex: Rua, Av, etc.)
        'address_number': 'Numero',  # Nº do imóvel do cliente (ex: 12)
        'address_complement': 'Complemento',  # Complemento (ex: Sala 109 ou Casa 1)
        'address_zip_code': 'CEP',  # O CEP de 8 dígitos do cliente. Somente números (ex: 22345678)
        'address_quarter': 'Bairro',  # Bairro do cliente
        'address_city': 'Cidade',  # Cidade do cliente (ex: São Paulo)
        'address_state': 'Estado',  # Estado do cliente (SP) no formato duas letras
        'phone': 'TelefoneFixo',  # Telefone fixo do cliente
        'cliente_email': 'Email',  # E-mail do cliente
    }

    _ACOUNT_DATA = {
        "email": "",
        "token":""
    }

    _PRODUCT_DATA = {
        "currency": "BRL",
        "itemId1":"",
        "itemDescription1":"",
        "itemQuantity1":"",
        "itemAmount1":"",
        "reference":"",
    }


    def get_gateway_url(self, request):
        """  """
        # To active the paypal sandbox, will be need run the paypal server
        # folder: paypal_testserver_v0.21
        import uuid
        is_dev = PaymentProcessor.get_backend_setting('testing', False)
        if is_dev:
            gateway_url2 = gateway_url = "http://127.0.0.1/paypal/"
            self._TRANSACTION_INSTRUCTION_PAGE = ""
            self._CHECKOUT_INSTRUCTION_PAGE = "checkout.php/?"
        else:
            gateway_url = "https://ws.paypal.uol.com.br/v2/"
            gateway_url2 = "https://paypal.uol.com.br/v2/"


        order = self.payment.order

        token = PaymentProcessor.get_backend_setting('token')
        email = PaymentProcessor.get_backend_setting('email')
        self._ACOUNT_DATA["token"] = token
        self._ACOUNT_DATA["email"] = email

        reference = uuid.uuid4().hex

        self._PRODUCT_DATA.update(itemId1=self.payment.id,
                                  itemDescription1= order.plan, 
                                  currency=self.payment.currency,
                                  itemAmount1=self.payment.amount,
                                  reference=reference,)

        full_data = dict(self._ACOUNT_DATA, **self._PRODUCT_DATA)

        params = urllib.urlencode(full_data)

        
        payment_full_url = "%s%s%s" % (gateway_url, self._CHECKOUT_INSTRUCTION_PAGE , params)
        request.encoding = 'ISO-8859-1'

        dados = {}

        logger.info(payment_full_url)
        response = requests.post(payment_full_url).text
        # print response
        
        code = ""
        if not is_dev:
            logger.warning("xml response from paypal: "+str(response))
            dom = parseString(response)
            print response
            checkout = dom.getElementsByTagName("checkout")
            if checkout:
                childNodes = checkout[0].childNodes
                code = childNodes[0].firstChild.nodeValue
                date = childNodes[1].firstChild.nodeValue

        self.payment.external_id = reference
        self.payment.description = code
        self.payment.save();

        return "%s%s" % (gateway_url2, self._TRANSACTION_INSTRUCTION_PAGE+code), 'GET', {}
        # return retorno

    @staticmethod
    def process_notification(params):
        _TRANSACTION_CONSULT_URL = "https://ws.paypal.uol.com.br/v2/transactions/notifications/%s?email=%s&token=%s"

        is_dev = PaymentProcessor.get_backend_setting('testing', False)
        if is_dev:
            _TRANSACTION_CONSULT_URL = "http://127.0.0.1/paypal/notifications.php?notificationCode=%s&email=%s&token=%s"

        Payment = get_model('getpaid', 'Payment')
        
        token = PaymentProcessor.get_backend_setting('token')
        email = PaymentProcessor.get_backend_setting('email')

        url_consult = _TRANSACTION_CONSULT_URL % (params["notificationCode"], email, token)
        resp = requests.get(url_consult)
        
        logger.info("paypal notification: " + resp.text)

        dom = parseString(resp.text)
        transactionNode = dom.getElementsByTagName("transaction")
        code = dom.getElementsByTagName("code")[0].firstChild.nodeValue
        status_code = int(dom.getElementsByTagName("status")[0].firstChild.nodeValue)
        
        reference = ""
        reference_node = dom.getElementsByTagName("reference")
        if reference_node:
            reference = reference_node[0].firstChild.nodeValue
        
        try:
            payment = Payment.objects.get(external_id__exact=reference)
        except Payment.DoesNotExist:
            logger.error('Payment does not exist with external_id=%s' % reference)
            return

        if status_code in (paypalTransactionStatus.AVAILABLE, paypalTransactionStatus.PAID):
            logger.info("Updating payment" + str(payment.id))
            amount = dom.getElementsByTagName("grossAmount")[0].firstChild.nodeValue
            payment.amount_paid = Decimal(amount)
            payment.paid_on = datetime.datetime.utcnow().replace(tzinfo=utc)
            payment.change_status('paid')

        elif status_code in (paypalTransactionStatus.CANCELED,
                             paypalTransactionStatus.REFUNDED,
                             paypalTransactionStatus.IN_DISPUTE):
            payment.change_status('failed')


    @staticmethod
    def _get_view_full_url(request, view_name, args=None):
        url = reverse(view_name, args=args)
        return 'http://%s%s' % (request.get_host(), url)
