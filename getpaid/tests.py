# coding: utf8
"""
This file demonstrates writing tests using the unittest module. These will pass
when you run "manage.py test".

Replace this with more appropriate tests for your application.
"""

from decimal import Decimal
from collections import OrderedDict

from django.core.urlresolvers import reverse
from django.db.models.loading import get_model
from django.test import TestCase
from django.test.client import Client
from django.test.utils import override_settings
from django.utils.six.moves.urllib.parse import urlparse, parse_qs, \
    parse_qsl, urlencode
from django.http import HttpRequest
from django.shortcuts import redirect
from django.utils import six
from django.contrib.sites.models import Site
import mock
from getpaid.backends import przelewy24
import getpaid.backends.payu
import getpaid.backends.transferuj

from getpaid_test_project.orders.models import Order


if six.PY3:
    unicode = str

class TransferujBackendTestCase(TestCase):
    def test_online_not_allowed_ip(self):
        self.assertEqual('IP ERR',
                         getpaid.backends.transferuj.PaymentProcessor.online('0.0.0.0', None, None, None, None, None,
                                                                             None, None, None, None, None, None))

        #Tests allowing IP given in settings
        with self.settings(GETPAID_BACKENDS_SETTINGS={
            'getpaid.backends.transferuj': {'allowed_ip': ('1.1.1.1', '1.2.3.4'), 'key': ''},
        }):
            self.assertEqual('IP ERR',
                             getpaid.backends.transferuj.PaymentProcessor.online('0.0.0.0', None, None, None, None,
                                                                                 None, None, None, None, None, None,
                                                                                 None))
            self.assertNotEqual('IP ERR',
                                getpaid.backends.transferuj.PaymentProcessor.online('1.1.1.1', None, None, None, None,
                                                                                    None, None, None, None, None, None,
                                                                                    None))
            self.assertNotEqual('IP ERR',
                                getpaid.backends.transferuj.PaymentProcessor.online('1.2.3.4', None, None, None, None,
                                                                                    None, None, None, None, None, None,
                                                                                    None))

        #Tests allowing all IP
        with self.settings(GETPAID_BACKENDS_SETTINGS={
            'getpaid.backends.transferuj': {'allowed_ip': [], 'key': ''},
        }):
            self.assertNotEqual('IP ERR',
                                getpaid.backends.transferuj.PaymentProcessor.online('0.0.0.0', None, None, None, None,
                                                                                    None, None, None, None, None, None,
                                                                                    None))
            self.assertNotEqual('IP ERR',
                                getpaid.backends.transferuj.PaymentProcessor.online('1.1.1.1', None, None, None, None,
                                                                                    None, None, None, None, None, None,
                                                                                    None))
            self.assertNotEqual('IP ERR',
                                getpaid.backends.transferuj.PaymentProcessor.online('1.2.3.4', None, None, None, None,
                                                                                    None, None, None, None, None, None,
                                                                                    None))

    def test_online_wrong_sig(self):
        self.assertEqual('SIG ERR',
                         getpaid.backends.transferuj.PaymentProcessor.online('195.149.229.109', '1234', '1', '', '1',
                                                                             '123.45', None, None, None, None, None,
                                                                             'xxx'))
        self.assertNotEqual('SIG ERR',
                            getpaid.backends.transferuj.PaymentProcessor.online('195.149.229.109', '1234', '1', '', '1',
                                                                                '123.45', None, None, None, None, None,
                                                                                '21b028c2dbdcb9ca272d1cc67ed0574e'))

    def test_online_wrong_id(self):
        self.assertEqual('ID ERR',
                         getpaid.backends.transferuj.PaymentProcessor.online('195.149.229.109', '1111', '1', '', '1',
                                                                             '123.45', None, None, None, None, None,
                                                                             '15bb75707d4374bc6e578c0cbf5a7fc7'))
        self.assertNotEqual('ID ERR',
                            getpaid.backends.transferuj.PaymentProcessor.online('195.149.229.109', '1234', '1', '', '1',
                                                                                '123.45', None, None, None, None, None,
                                                                                'f5f8276fbaa98a6e05b1056ab7c3a589'))

    def test_online_crc_error(self):
        self.assertEqual('CRC ERR',
                         getpaid.backends.transferuj.PaymentProcessor.online('195.149.229.109', '1234', '1', '',
                                                                             '99999', '123.45', None, None, None, None,
                                                                             None, 'f5f8276fbaa98a6e05b1056ab7c3a589'))
        self.assertEqual('CRC ERR',
                         getpaid.backends.transferuj.PaymentProcessor.online('195.149.229.109', '1234', '1', '',
                                                                             'GRRGRRG', '123.45', None, None, None,
                                                                             None, None,
                                                                             '6a9e045010c27dfed24774b0afa37d0b'))

    def test_online_payment_ok(self):
        Payment = get_model('getpaid', 'Payment')
        order = Order(name='Test EUR order', total='123.45', currency='PLN')
        order.save()
        payment = Payment(order=order, amount=order.total, currency=order.currency, backend='getpaid.backends.payu')
        payment.save(force_insert=True)
        self.assertEqual('TRUE', getpaid.backends.transferuj.PaymentProcessor.online('195.149.229.109', '1234', '1', '',
                                                                                     payment.pk, '123.45', '123.45', '',
                                                                                     'TRUE', 0, '',
                                                                                     '21b028c2dbdcb9ca272d1cc67ed0574e'))
        payment = Payment.objects.get(pk=payment.pk)
        self.assertEqual(payment.status, 'paid')
        self.assertNotEqual(payment.paid_on, None)
        self.assertEqual(payment.amount_paid, Decimal('123.45'))

    def test_online_payment_ok_over(self):
        Payment = get_model('getpaid', 'Payment')
        order = Order(name='Test EUR order', total='123.45', currency='PLN')
        order.save()
        payment = Payment(order=order, amount=order.total, currency=order.currency, backend='getpaid.backends.payu')
        payment.save(force_insert=True)
        self.assertEqual('TRUE', getpaid.backends.transferuj.PaymentProcessor.online('195.149.229.109', '1234', '1', '',
                                                                                     payment.pk, '123.45', '223.45', '',
                                                                                     'TRUE', 0, '',
                                                                                     '21b028c2dbdcb9ca272d1cc67ed0574e'))
        payment = Payment.objects.get(pk=payment.pk)
        self.assertEqual(payment.status, 'paid')
        self.assertNotEqual(payment.paid_on, None)
        self.assertEqual(payment.amount_paid, Decimal('223.45'))

    def test_online_payment_partial(self):
        Payment = get_model('getpaid', 'Payment')
        order = Order(name='Test EUR order', total='123.45', currency='PLN')
        order.save()
        payment = Payment(order=order, amount=order.total, currency=order.currency, backend='getpaid.backends.payu')
        payment.save(force_insert=True)
        self.assertEqual('TRUE', getpaid.backends.transferuj.PaymentProcessor.online('195.149.229.109', '1234', '1', '',
                                                                                     payment.pk, '123.45', '23.45', '',
                                                                                     'TRUE', 0, '',
                                                                                     '21b028c2dbdcb9ca272d1cc67ed0574e'))
        payment = Payment.objects.get(pk=payment.pk)
        self.assertEqual(payment.status, 'partially_paid')
        self.assertNotEqual(payment.paid_on, None)
        self.assertEqual(payment.amount_paid, Decimal('23.45'))

    def test_online_payment_failure(self):
        Payment = get_model('getpaid', 'Payment')
        order = Order(name='Test EUR order', total='123.45', currency='PLN')
        order.save()
        payment = Payment(order=order, amount=order.total, currency=order.currency, backend='getpaid.backends.payu')
        payment.save(force_insert=True)
        self.assertEqual('TRUE', getpaid.backends.transferuj.PaymentProcessor.online('195.149.229.109', '1234', '1', '',
                                                                                     payment.pk, '123.45', '23.45', '',
                                                                                     False, 0, '',
                                                                                     '21b028c2dbdcb9ca272d1cc67ed0574e'))
        payment = Payment.objects.get(pk=payment.pk)
        self.assertEqual(payment.status, 'failed')


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

    @mock.patch("getpaid.backends.payu.urlopen", fake_payment_get_response_success)
    def test_payment_get_paid(self):
        Payment = get_model('getpaid', 'Payment')
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

    @mock.patch("getpaid.backends.payu.urlopen", fake_payment_get_response_failure)
    def test_payment_get_failed(self):
        Payment = get_model('getpaid', 'Payment')
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


def fake_przelewy24_payment_get_response_success(request):
    class fake_response:
        def read(self):
            return b"""RESULT
TRUE"""

    return fake_response()


def fake_przelewy24_payment_get_response_failed(request):
    class fake_response:
        def read(self):
            # Błąd wywołania (3) - błąd CRC
            return b"""RESULT
ERR
123
Some error description"""

    return fake_response()


class Przelewy24PaymentProcessorTestCase(TestCase):
    def test_sig(self):
        # Test based on p24 documentation
        sig = przelewy24.PaymentProcessor.compute_sig(
            {
                u'key1': u'9999',
                u'key2': u'2500',
                u'key3': u'ccc',
                u'key4': u'abcdefghijk',
                u'crc': u'a123b456c789d012',

            },
            (u'key4', u'key1', u'key2', u'crc'),
            u'a123b456c789d012'
        )
        self.assertEqual(sig, 'e2c43dec9578633c518e1f514d3b434b')

    @mock.patch("getpaid.backends.przelewy24.urlopen", fake_przelewy24_payment_get_response_success)
    def test_get_payment_status_success(self):
        Payment = get_model('getpaid', 'Payment')
        order = Order(name='Test PLN order', total='123.45', currency='PLN')
        order.save()
        payment = Payment(pk=191, order=order, amount=order.total, currency=order.currency,
                          backend='getpaid.backends.przelewy24')
        payment.save(force_insert=True)
        payment = Payment.objects.get(pk=191)
        processor = getpaid.backends.przelewy24.PaymentProcessor(payment)
        processor.get_payment_status(p24_session_id=u'191:xxx:xxx',
                                     p24_order_id=u'191:external', p24_kwota=u'12345')
        self.assertEqual(payment.status, 'paid')
        self.assertEqual(payment.external_id, '191:external')
        self.assertNotEqual(payment.paid_on, None)
        self.assertEqual(payment.amount_paid, Decimal('123.45'))

    @mock.patch("getpaid.backends.przelewy24.urlopen",
                fake_przelewy24_payment_get_response_success)
    def test_get_payment_status_success_partial(self):
        Payment = get_model('getpaid', 'Payment')
        order = Order(name='Test PLN order', total='123.45', currency='PLN')
        order.save()

        payment = Payment(pk=192, order=order, amount=order.total, currency=order.currency,
                          backend='getpaid.backends.przelewy24')
        payment.save(force_insert=True)
        payment = Payment.objects.get(pk=192)
        processor = getpaid.backends.przelewy24.PaymentProcessor(payment)
        processor.get_payment_status(p24_session_id=u'192:xxx:xxx',
                                     p24_order_id=u'192:external',
                                     p24_kwota=u'12245')
        self.assertEqual(payment.status, u'partially_paid')
        self.assertEqual(payment.external_id, u'192:external')
        self.assertNotEqual(payment.paid_on, None)
        self.assertEqual(payment.amount_paid, Decimal('122.45'))

    @mock.patch("getpaid.backends.przelewy24.urlopen", fake_przelewy24_payment_get_response_failed)
    def test_get_payment_status_failed(self):
        Payment = get_model('getpaid', 'Payment')
        order = Order(name='Test PLN order', total='123.45', currency='PLN')
        order.save()

        payment = Payment(pk=192, order=order, amount=order.total, currency=order.currency,
                          backend='getpaid.backends.przelewy24')
        payment.save(force_insert=True)
        payment = Payment.objects.get(pk=192)
        processor = getpaid.backends.przelewy24.PaymentProcessor(payment)
        processor.get_payment_status(p24_session_id=u'192:xxx:xxx',
                                     p24_order_id=u'192:external',
                                     p24_kwota=u'12245')
        self.assertEqual(payment.status, u'failed')
        self.assertEqual(payment.paid_on, None)
        self.assertEqual(payment.amount_paid, Decimal('0.0'))


class EpaydkBackendTestCase(TestCase):
    maxDiff = None

    def setUp(self):
        self.client = Client()
        Payment = get_model('getpaid', 'Payment')
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

        domain = Site.objects.get_current().domain
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
        Payment = get_model('getpaid', 'Payment')
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
        Payment = get_model('getpaid', 'Payment')
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
        Payment = get_model('getpaid', 'Payment')
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
        Payment = get_model('getpaid', 'Payment')
        actual = Payment.objects.get(id=self.test_payment.id)
        self.assertEqual(actual.status, 'cancelled')
