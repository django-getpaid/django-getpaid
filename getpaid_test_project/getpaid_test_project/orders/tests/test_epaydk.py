# coding: utf8

from collections import OrderedDict

from django.core.urlresolvers import reverse
from django.apps import apps
from django.test import TestCase
from django.test.client import Client
from django.test.utils import override_settings
from django.utils.six.moves.urllib.parse import urlparse, parse_qs, \
    parse_qsl, urlencode
from django.http import HttpRequest
from django.utils import six
import mock

import getpaid
from getpaid_test_project.orders.models import Order


if six.PY3:
    unicode = str


class EpaydkBackendTestCase(TestCase):
    maxDiff = None

    def setUp(self):
        self.client = Client()
        Payment = apps.get_model('getpaid', 'Payment')
        order = Order(name='Test DKK order', total='123.45', currency='DKK')
        order.save()

        payment = Payment(order=order,
                          amount=order.total,
                          currency=order.currency,
                          backend='getpaid.backends.epaydk')
        payment.save()
        self.test_payment = Payment.objects.get(pk=payment.id)

    def test_format_ammount(self):
        payproc = getpaid.backends.epaydk.PaymentProcessor(self.test_payment)
        self.assertEqual(payproc.format_amount(123), "12300")
        self.assertEqual(payproc.format_amount("123.0"), "12300")
        self.assertEqual(payproc.format_amount(123.321), "12333")

    def test_get_gateway_url(self):
        payproc = getpaid.backends.epaydk.PaymentProcessor(self.test_payment)
        fake_req = mock.MagicMock(spec=HttpRequest)
        fake_req.scheme = 'https'
        fake_req.COOKIES = {}
        fake_req.META = {}
        actual = payproc.get_gateway_url(fake_req)
        self.assertEqual(actual[1], "GET")
        self.assertEqual(actual[2], {})

        actual = list(urlparse(actual[0]))
        self.assertEqual(actual[0], 'https')
        self.assertEqual(actual[1], 'ssl.ditonlinebetalingssystem.dk')
        self.assertEqual(actual[2], '/integration/ewindow/Default.aspx')
        self.assertEqual(actual[3], '')

        domain = getpaid.utils.get_domain()
        accepturl = u'https://'+ domain +'/getpaid.backends.epaydk/success/'
        callbackurl = u'https://'+ domain +'/getpaid.backends.epaydk/online/'
        cancelurl = u'https://'+ domain +'/getpaid.backends.epaydk/failure/'
        expected = [
            (u'merchantnumber', u'xxxxxxxx'),
            (u'orderid', u'1'),
            (u'currency', u'208'),
            (u'amount', u'12345'),
            (u'windowstate', u'3'),
            (u'mobile', u'1'),
            (u'timeout', u'3'),
            (u'instantcallback', u'0'),
            (u'language', u'2'),
            (u'accepturl', accepturl),
            (u'callbackurl', callbackurl),
            (u'cancelurl', cancelurl),
        ]
        md5hash = payproc.compute_hash(OrderedDict(expected))
        expected.append(('hash', md5hash))
        self.assertListEqual(expected, parse_qsl(actual[4]))
        self.assertEqual(actual[5], '')

    def test_online_invalid(self):
        response = self.client.get(reverse('getpaid-epaydk-online'))
        self.assertEqual(response.content, b'400 Bad Request')
        self.assertEqual(response.status_code, 400)

    @override_settings(GETPAID_SUCCESS_URL_NAME=None)
    def test_accept_ok(self):
        self.test_payment.status = 'in_progress'
        self.test_payment.save()

        payproc = getpaid.backends.epaydk.PaymentProcessor(self.test_payment)
        params = [
            (u'txnid', u'48384464'),
            (u'orderid', unicode(self.test_payment.id)),
            (u'amount', payproc.format_amount(self.test_payment.amount)),
            (u'currency', u'208'),
            (u'date', u'20150716'),
            (u'time', u'1638'),
            (u'txnfee', u'0'),
            (u'paymenttype', u'1'),
            (u'cardno', u'444444XXXXXX4000'),
        ]
        md5hash = payproc.compute_hash(OrderedDict(params))
        params.append(('hash', md5hash))
        query = urlencode(params)
        url = reverse('getpaid-epaydk-success') + '?' + query
        response = self.client.get(url, data=params)
        expected_url = reverse('getpaid-success-fallback',
                               kwargs=dict(pk=self.test_payment.pk))
        self.assertRedirects(response, expected_url, 302, 302)
        Payment = apps.get_model('getpaid', 'Payment')
        actual = Payment.objects.get(id=self.test_payment.id)
        self.assertEqual(actual.status, 'accepted_for_proc')

    def test_online_ok(self):
        self.test_payment.status = 'accepted_for_proc'
        self.test_payment.save()
        payproc = getpaid.backends.epaydk.PaymentProcessor(self.test_payment)
        params = [
            (u'txnid', u'48384464'),
            (u'orderid', unicode(self.test_payment.id)),
            (u'amount', payproc.format_amount(self.test_payment.amount)),
            (u'currency', u'208'),
            (u'date', u'20150716'),
            (u'time', u'1638'),
            (u'txnfee', u'0'),
            (u'paymenttype', u'1'),
            (u'cardno', u'444444XXXXXX4000'),
        ]
        md5hash = payproc.compute_hash(OrderedDict(params))
        params.append(('hash', md5hash))
        query = urlencode(params)
        url = reverse('getpaid-epaydk-online') + '?' + query
        response = self.client.get(url, data=params)
        self.assertEqual(response.content, b'OK')
        self.assertEqual(response.status_code, 200)
        Payment = apps.get_model('getpaid', 'Payment')
        actual = Payment.objects.get(id=self.test_payment.id)
        self.assertEqual(actual.status, 'paid')

    def test_online_wrong_hash(self):
        payproc = getpaid.backends.epaydk.PaymentProcessor(self.test_payment)
        params = [
            (u'txnid', u'48384464'),
            (u'orderid', unicode(self.test_payment.id)),
            (u'amount', payproc.format_amount(self.test_payment.amount)),
            (u'currency', u'208'),
            (u'date', u'20150716'),
            (u'time', u'1638'),
            (u'txnfee', u'0'),
            (u'paymenttype', u'1'),
            (u'cardno', u'444444XXXXXX4000'),
        ]
        params.append(('hash', '1234567'))
        query = urlencode(params)
        url = reverse('getpaid-epaydk-online') + '?' + query
        response = self.client.get(url, data=params)
        self.assertEqual(response.content, b'400 Bad Request')
        self.assertEqual(response.status_code, 400)
        Payment = apps.get_model('getpaid', 'Payment')
        actual = Payment.objects.get(id=self.test_payment.id)
        self.assertEqual(actual.status, 'new')

    def test_online_post(self):
        data = {'test': 'data'}
        response = self.client.post(reverse('getpaid-epaydk-online'),
                                    data=data)
        self.assertEqual(response.content, b'')
        self.assertEqual(response.status_code, 405)

    def test_cancelled(self):
        query = '?orderid=%s&error=-5543' % self.test_payment.id
        url = reverse('getpaid-epaydk-failure') + query
        response = self.client.get(url)
        expected = reverse('getpaid-failure-fallback',
                           kwargs=dict(pk=self.test_payment.pk))
        self.assertRedirects(response, expected, 302, 302)
        Payment = apps.get_model('getpaid', 'Payment')
        actual = Payment.objects.get(id=self.test_payment.id)
        self.assertEqual(actual.status, 'cancelled')
