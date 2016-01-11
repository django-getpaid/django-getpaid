# coding: utf8

from decimal import Decimal

from django.apps import apps
from django.test import TestCase
from django.utils.six.moves.urllib.parse import urlparse, parse_qs, \
    parse_qsl, urlencode
from django.utils import six
import mock

import getpaid
from getpaid.backends import przelewy24
from getpaid_test_project.orders.models import Order


if six.PY3:
    unicode = str


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
        Payment = apps.get_model('getpaid', 'Payment')
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
        Payment = apps.get_model('getpaid', 'Payment')
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
        Payment = apps.get_model('getpaid', 'Payment')
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
