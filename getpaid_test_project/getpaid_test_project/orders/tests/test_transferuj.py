# coding: utf8

from decimal import Decimal

from django.db.models.loading import get_model
from django.test import TestCase
from django.utils.six.moves.urllib.parse import urlparse, parse_qs, \
    parse_qsl, urlencode
from django.utils import six
import mock

import getpaid
from getpaid.backends import transferuj
from getpaid_test_project.orders.models import Order


if six.PY3:
    unicode = str

class TransferujBackendTestCase(TestCase):
    def test_online_not_allowed_ip(self):
        self.assertEqual('IP ERR',
                         transferuj.PaymentProcessor.online('0.0.0.0', None, None, None, None, None,
                                                                             None, None, None, None, None, None))

        #Tests allowing IP given in settings
        with self.settings(GETPAID_BACKENDS_SETTINGS={
            'getpaid.backends.transferuj': {'allowed_ip': ('1.1.1.1', '1.2.3.4'), 'key': ''},
        }):
            self.assertEqual('IP ERR',
                             transferuj.PaymentProcessor.online('0.0.0.0', None, None, None, None,
                                                                                 None, None, None, None, None, None,
                                                                                 None))
            self.assertNotEqual('IP ERR',
                                transferuj.PaymentProcessor.online('1.1.1.1', None, None, None, None,
                                                                                    None, None, None, None, None, None,
                                                                                    None))
            self.assertNotEqual('IP ERR',
                                transferuj.PaymentProcessor.online('1.2.3.4', None, None, None, None,
                                                                                    None, None, None, None, None, None,
                                                                                    None))

        #Tests allowing all IP
        with self.settings(GETPAID_BACKENDS_SETTINGS={
            'getpaid.backends.transferuj': {'allowed_ip': [], 'key': ''},
        }):
            self.assertNotEqual('IP ERR',
                                transferuj.PaymentProcessor.online('0.0.0.0', None, None, None, None,
                                                                                    None, None, None, None, None, None,
                                                                                    None))
            self.assertNotEqual('IP ERR',
                                transferuj.PaymentProcessor.online('1.1.1.1', None, None, None, None,
                                                                                    None, None, None, None, None, None,
                                                                                    None))
            self.assertNotEqual('IP ERR',
                                transferuj.PaymentProcessor.online('1.2.3.4', None, None, None, None,
                                                                                    None, None, None, None, None, None,
                                                                                    None))

    def test_online_wrong_sig(self):
        self.assertEqual('SIG ERR',
                         transferuj.PaymentProcessor.online('195.149.229.109', '1234', '1', '', '1',
                                                                             '123.45', None, None, None, None, None,
                                                                             'xxx'))
        self.assertNotEqual('SIG ERR',
                            transferuj.PaymentProcessor.online('195.149.229.109', '1234', '1', '', '1',
                                                                                '123.45', None, None, None, None, None,
                                                                                '21b028c2dbdcb9ca272d1cc67ed0574e'))

    def test_online_wrong_id(self):
        self.assertEqual('ID ERR',
                         transferuj.PaymentProcessor.online('195.149.229.109', '1111', '1', '', '1',
                                                                             '123.45', None, None, None, None, None,
                                                                             '15bb75707d4374bc6e578c0cbf5a7fc7'))
        self.assertNotEqual('ID ERR',
                            transferuj.PaymentProcessor.online('195.149.229.109', '1234', '1', '', '1',
                                                                                '123.45', None, None, None, None, None,
                                                                                'f5f8276fbaa98a6e05b1056ab7c3a589'))

    def test_online_crc_error(self):
        self.assertEqual('CRC ERR',
                         transferuj.PaymentProcessor.online('195.149.229.109', '1234', '1', '',
                                                                             '99999', '123.45', None, None, None, None,
                                                                             None, 'f5f8276fbaa98a6e05b1056ab7c3a589'))
        self.assertEqual('CRC ERR',
                         transferuj.PaymentProcessor.online('195.149.229.109', '1234', '1', '',
                                                                             'GRRGRRG', '123.45', None, None, None,
                                                                             None, None,
                                                                             '6a9e045010c27dfed24774b0afa37d0b'))

    def test_online_payment_ok(self):
        Payment = get_model('getpaid', 'Payment')
        order = Order(name='Test EUR order', total='123.45', currency='PLN')
        order.save()
        payment = Payment(order=order, amount=order.total, currency=order.currency, backend='getpaid.backends.payu')
        payment.save(force_insert=True)
        self.assertEqual('TRUE', transferuj.PaymentProcessor.online('195.149.229.109', '1234', '1', '',
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
        self.assertEqual('TRUE', transferuj.PaymentProcessor.online('195.149.229.109', '1234', '1', '',
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
        self.assertEqual('TRUE', transferuj.PaymentProcessor.online('195.149.229.109', '1234', '1', '',
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
        self.assertEqual('TRUE', transferuj.PaymentProcessor.online('195.149.229.109', '1234', '1', '',
                                                                                     payment.pk, '123.45', '23.45', '',
                                                                                     False, 0, '',
                                                                                     '21b028c2dbdcb9ca272d1cc67ed0574e'))
        payment = Payment.objects.get(pk=payment.pk)
        self.assertEqual(payment.status, 'failed')
