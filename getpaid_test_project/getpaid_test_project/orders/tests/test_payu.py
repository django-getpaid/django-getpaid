# coding: utf8

from decimal import Decimal

from django.core.urlresolvers import reverse
from django.apps import apps
from django.test import TestCase
from django.test.client import Client
from django.utils.six.moves.urllib.parse import urlparse, parse_qs, \
    parse_qsl, urlencode
from django.utils import six
import mock

import getpaid
import getpaid.backends.payu
from getpaid_test_project.orders.models import Order


if six.PY3:
    unicode = str


def fake_payment_get_response_success(request):
    class fake_response:
        def read(self):
            return b"""
status:OK
trans_id:234748067
trans_pos_id:123456789
trans_session_id:99:1342616247.41
trans_order_id:99
trans_amount:12345
trans_status:99
trans_pay_type:t
trans_pay_gw_name:pt
trans_desc:Test 2
trans_desc2:
trans_create:2012-07-18 14:57:28
trans_init:
trans_sent:
trans_recv:
trans_cancel:20trans_12-07-18 14:57:30
trans_auth_fraud:0
trans_ts:1342616255805
trans_sig:4d4df5557b89a4e2d8c48436b1dd3fef
"""

    return fake_response()


def fake_payment_get_response_failure(request):
    class fake_response:
        def info(self):
            message = http.client.HTTPMessage()
            message.headers = (
                ('Content-type', 'text/plain; charset=ISO-8859-1'),
            )
            return message
        def read(self):
            return b"""
status:OK
trans_id:234748067
trans_pos_id:123456789
trans_session_id:98:1342616247.41
trans_order_id:98
trans_amount:12345
trans_status:2
trans_pay_type:t
trans_pay_gw_name:pt
trans_desc:Test 2
trans_desc2:
trans_create:2012-07-18 14:57:28
trans_init:
trans_sent:
trans_recv:
trans_cancel:2012-07-18 14:57:30
trans_auth_fraud:0
trans_ts:1342616255805
trans_sig:ee77e9515599e3fd2b3721dff50111dd
"""

    return fake_response()


class PayUBackendTestCase(TestCase):
    maxDiff = True

    def setUp(self):
        self.client = Client()


    def test_parse_text_result(self):
        t1 = u'''status:OK

trans_id:349659572
trans_pos_id:105664
trans_session_id:48:1379695300.48
trans_ts:1379695309225
trans_sig:e4e981bfa780fa78fb077ca1f9295f2a

        '''
        self.assertEqual(getpaid.backends.payu.PaymentProcessor._parse_text_response(t1),
                         {
                             'status': 'OK',
                             'trans_id': '349659572',
                             'trans_pos_id': '105664',
                             'trans_session_id': '48:1379695300.48',
                             'trans_ts': '1379695309225',
                             'trans_sig': 'e4e981bfa780fa78fb077ca1f9295f2a',
                         }
        )

    def test_online_malformed(self):
        response = self.client.post(reverse('getpaid-payu-online'), {})
        self.assertEqual(response.content, b'MALFORMED')

    def test_online_sig_err(self):
        response = self.client.post(reverse('getpaid-payu-online'), {
            'pos_id': 'wrong',
            'session_id': '10:11111',
            'ts': '1111',
            'sig': 'wrong sig',
        })
        self.assertEqual(response.content, b'SIG ERR')

    def test_online_wrong_pos_id_err(self):
        response = self.client.post(reverse('getpaid-payu-online'), {
            'pos_id': '12345',
            'session_id': '10:11111',
            'ts': '1111',
            'sig': '0d6129738c0aee9d4eb56f2a1db75ab4',
        })
        self.assertEqual(response.content, b'POS_ID ERR')

    def test_online_wrong_session_id_err(self):
        response = self.client.post(reverse('getpaid-payu-online'), {
            'pos_id': '123456789',
            'session_id': '111111',
            'ts': '1111',
            'sig': 'fcf3db081d5085b45fe86ed0c6a9aa5e',
        })
        self.assertEqual(response.content, b'SESSION_ID ERR')

    def test_online_ok(self):
        response = self.client.post(reverse('getpaid-payu-online'), {
            'pos_id': '123456789',
            'session_id': '1:11111',
            'ts': '1111',
            'sig': '2a78322c06522613cbd7447983570188',
        })
        self.assertEqual(response.content, b'OK')

    @mock.patch("getpaid.backends.payu.Request", autospec=True)
    @mock.patch("getpaid.backends.payu.urlopen", fake_payment_get_response_success)
    def test_payment_get_paid(self, mock_Request):
        Payment = apps.get_model('getpaid', 'Payment')
        order = Order(name='Test EUR order', total='123.45', currency='PLN')
        order.save()
        payment = Payment(pk=99, order=order, amount=order.total, currency=order.currency,
                          backend='getpaid.backends.payu')
        payment.save(force_insert=True)
        payment = Payment.objects.get(
            pk=99)  # this line is because django bug https://code.djangoproject.com/ticket/5903
        processor = getpaid.backends.payu.PaymentProcessor(payment)
        processor.get_payment_status(u'99:1342616247.41')
        self.assertEqual(payment.status, u'paid')
        self.assertNotEqual(payment.paid_on, None)
        self.assertNotEqual(payment.amount_paid, Decimal('0'))

        url = 'https://www.platnosci.pl/paygw/UTF/Payment/get/txt'
        callargs = mock_Request.call_args_list
        self.assertEqual(url, callargs[0][0][0])
        if six.PY3:
            self.assertIsInstance(callargs[0][0][1], bytes)
            self.assertTrue(b'pos_id=123456789' in callargs[0][0][1])
            self.assertTrue(b'session_id=99%3A1342616247.41' in callargs[0][0][1])
        else:
            self.assertIsInstance(callargs[0][0][1], str)
            self.assertTrue('pos_id=123456789' in callargs[0][0][1])
            self.assertTrue('session_id=99%3A1342616247.41' in callargs[0][0][1])

    @mock.patch("getpaid.backends.payu.urlopen", fake_payment_get_response_failure)
    def test_payment_get_failed(self):
        Payment = apps.get_model('getpaid', 'Payment')
        order = Order(name='Test EUR order', total='123.45', currency='PLN')
        order.save()
        payment = Payment(pk=98, order=order, amount=order.total, currency=order.currency,
                          backend='getpaid.backends.payu')
        payment.save(force_insert=True)
        payment = Payment.objects.get(
            pk=98)  # this line is because django bug https://code.djangoproject.com/ticket/5903
        processor = getpaid.backends.payu.PaymentProcessor(payment)
        processor.get_payment_status(u'98:1342616247.41')
        self.assertEqual(payment.status, u'failed')
        self.assertEqual(payment.paid_on, None)
        self.assertEqual(payment.amount_paid, Decimal('0'))
