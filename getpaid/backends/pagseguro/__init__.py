# -*- coding: utf-8 -*-
from decimal import Decimal
import logging
import datetime
import uuid
import requests
import time
from django.core.urlresolvers import reverse
from django.db.models import get_model
from django.utils.timezone import utc
from django.utils.translation import ugettext_lazy as _
from getpaid.signals import user_data_query
from getpaid.backends import PaymentProcessorBase
from xml.dom.minidom import parseString
from six.moves.urllib.parse import urlencode



logger = logging.getLogger('getpaid.backends.pagseguro')

# see: https://pagseguro.uol.com.br/v2/guia-de-integracao/api-de-notificacoes.html#v2-item-api-de-notificacoes-status-da-transacao
class PagseguroTransactionStatus:
    IN_PROGRESS = 1     # payment transaction started and waiting be paid
    IN_ANALISE = 2
    PAID    = 3
    AVAILABLE = 4
    IN_DISPUTE = 5
    REFUNDED = 6
    CANCELED = 7


class PaymentProcessor(PaymentProcessorBase):
    """

    Backend Settings:

    gateway_url_start_transac: url to init the transatcion with
    pagseguro payment service. This url is used only to send client
    data such phone, name, email, product...

    gateway_url_payment: url to redirect the client to pay the bill.
    """

    BACKEND = 'getpaid.backends.pagseguro'
    BACKEND_NAME = _('PagSeguro')
    BACKEND_ACCEPTED_CURRENCY = ('BRL', )
    BACKEND_LOGO_URL = 'getpaid/backends/pagseguro/pag-seguro-logo.png'

    _GATEWAY_URL_START_TRANSAC = "https://ws.pagseguro.uol.com.br/v2/checkout/?"
    _GATEWAY_URL_PAYMENT = "https://pagseguro.uol.com.br/v2/checkout/payment.html?code="
    _TRANSACTION_CONSULT_URL = "https://ws.pagseguro.uol.com.br/v2/transactions/notifications/"

    _DEV_GATEWAY_URL_START_TRANSAC = "https://ws.sandbox.pagseguro.uol.com.br/v2/checkout/?"
    _DEV_GATEWAY_URL_PAYMENT = "https://sandbox.pagseguro.uol.com.br/v2/checkout/payment.html?code="
    _DEV_TRANSACTION_CONSULT_URL = "https://ws.sandbox.pagseguro.uol.com.br/v2/transactions/notifications/"

    _USER_DATA_TO_PAGSEGURO = {
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
        "itemQuantity1":"1",
        "itemAmount1":"",
        "reference":"",
    }


    def get_gateway_url(self, request):
        """  """
        payp = PaymentProcessor
        gateway_url = payp.get_backend_setting('gateway_url_start_transac',
                                            self._GATEWAY_URL_START_TRANSAC)
        gateway_url2 = payp.get_backend_setting('gateway_url_payment', 
                                                self._GATEWAY_URL_PAYMENT)
        
        is_dev = payp.get_backend_setting('testing', False)
        if is_dev:
            gateway_url = payp.get_backend_setting('dev_gateway_url_start_transac',
                                            self._DEV_GATEWAY_URL_START_TRANSAC)
            gateway_url2 = payp.get_backend_setting('dev_gateway_url_payment', 
                                                self._DEV_GATEWAY_URL_PAYMENT)

        order = self.payment.order

        token = PaymentProcessor.get_backend_setting('token')
        email = PaymentProcessor.get_backend_setting('email')
        self._ACOUNT_DATA["token"] = token
        self._ACOUNT_DATA["email"] = email

        reference = uuid.uuid4().hex

        product_description = self.get_order_description(self.payment, self.payment.order)
        redirectURL = PaymentProcessor._get_view_full_url(request, 'getpaid-pagseguro-success', args=(self.payment.id,))
        
        self._PRODUCT_DATA.update(itemId1=self.payment.id,
                                  itemDescription1= product_description.encode("latin1", "ignore"), 
                                  currency=self.payment.currency,
                                  itemAmount1=self.payment.amount,
                                  reference=reference,
                                  redirectURL=redirectURL,
                                  )

        full_data = dict(self._ACOUNT_DATA, **self._PRODUCT_DATA)
        params = urlencode(full_data)

        payment_full_url = "%s%s" % (gateway_url, params)
        request.encoding = 'ISO-8859-1'
        
        logger.info(payment_full_url)

        headers = {"Content-type": "application/x-www-form-urlencoded"}
        response = requests.post(payment_full_url, headers=headers).text

        code = ""
        logger.info("xml response from pagseguro: " + str(response.encode("utf-8")))
        dom = parseString(response)
        
        checkout = dom.getElementsByTagName("checkout")
        if checkout:
            childNodes = checkout[0].childNodes
            code = childNodes[0].firstChild.nodeValue
            date = childNodes[1].firstChild.nodeValue

        self.payment.external_id = reference
        self.payment.description = code
        self.payment.save();
        
        return "%s%s" % (gateway_url2, code), 'GET', {}

    @staticmethod
    def process_notification(params):

        payp = PaymentProcessor
        tmp_transaction_url = payp.get_backend_setting('transaction_url',
                                            payp._TRANSACTION_CONSULT_URL)
        
        is_dev = payp.get_backend_setting('testing', False)
        if is_dev:
            tmp_transaction_url = payp.get_backend_setting('dev_transaction_url',
                                            payp._DEV_TRANSACTION_CONSULT_URL)

        transaction_url = tmp_transaction_url + "%s?email=%s&token=%s"

        Payment = get_model('getpaid', 'Payment')
        
        token = payp.get_backend_setting('token')
        email = payp.get_backend_setting('email')

        url_consult = transaction_url % (params["notificationCode"], email, token)
        resp = requests.get(url_consult)
        logger.info("pagseguro notification: " + resp.text)

        dom = parseString(resp.text.encode('utf-8'))
        transactionNode = dom.getElementsByTagName("transaction")
        code = dom.getElementsByTagName("code")[0].firstChild.nodeValue
        if dom.getElementsByTagName("status"):
            status_code = int(dom.getElementsByTagName("status")[0].firstChild.nodeValue)
        
        reference = ""
        reference_node = dom.getElementsByTagName("reference")
        if reference_node:
            reference = reference_node[0].firstChild.nodeValue
        
        try:
            payment = Payment.objects.get(external_id__exact=reference)
        except Payment.DoesNotExist:
            logger.error('Payment does not exist with external_id=%s' % reference)
            raise Payment.DoesNotExist
        
        if status_code in (PagseguroTransactionStatus.AVAILABLE, PagseguroTransactionStatus.PAID):
            logger.info("Updating payment" + str(payment.id))
            amount = dom.getElementsByTagName("grossAmount")[0].firstChild.nodeValue
            payment.amount_paid = Decimal(amount)
            payment.paid_on = datetime.datetime.utcnow().replace(tzinfo=utc)
            payment.change_status('paid')

        elif status_code in (PagseguroTransactionStatus.CANCELED,
                             PagseguroTransactionStatus.REFUNDED,
                             PagseguroTransactionStatus.IN_DISPUTE):
            payment.change_status('failed')
        
        return "OK"

    @staticmethod
    def _get_view_full_url(request, view_name, args=None):
        url = reverse(view_name, args=args)
        return 'http://%s%s' % (request.get_host(), url)
