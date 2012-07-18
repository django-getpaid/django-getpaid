"""
This file demonstrates writing tests using the unittest module. These will pass
when you run "manage.py test".

Replace this with more appropriate tests for your application.
"""
from decimal import Decimal
from django.core.urlresolvers import reverse
from django.db.models.loading import get_model

from django.test import TestCase
from django.test.client import Client
import mock
from getpaid.backends.payu import PaymentProcessor
from getpaid_test_project.orders.models import Order


class OrderTest(TestCase):
    def setUp(self):
        self.client = Client()

    def test_successful_create_payment_dummy_eur(self):
        """
        Tests if payment is successfully created
        """
        order = Order(name='Test EUR order', total=100, currency='EUR')
        order.save()
        response = self.client.post(reverse('getpaid-new-payment', kwargs={'currency' : 'EUR'}),
                    {'order': order.pk,
                     'backend': 'getpaid.backends.dummy'}
        )
        self.assertEqual(response.status_code, 302)
        Payment = get_model('getpaid', 'Payment')
        payment = Payment.objects.get(order=order.pk)
        self.assertEqual(payment.backend, 'getpaid.backends.dummy')
        self.assertEqual(payment.amount, order.total)
        self.assertEqual(payment.currency, order.currency)
        self.assertEqual(payment.status, 'in_progress')
        self.assertEqual(payment.paid_on, None)
        self.assertEqual(payment.amount_paid, 0)

    def test_successful_create_payment_payu_pln(self):
        """
        Tests if payment is successfully created
        """
        order = Order(name='Test PLN order', total=100, currency='PLN')
        order.save()
        response = self.client.post(reverse('getpaid-new-payment', kwargs={'currency' : 'PLN'}),
                {'order': order.pk,
                 'backend': 'getpaid.backends.payu'}
        )
        self.assertEqual(response.status_code, 302)
        Payment = get_model('getpaid', 'Payment')
        payment = Payment.objects.get(order=order.pk)
        self.assertEqual(payment.backend, 'getpaid.backends.payu')
        self.assertEqual(payment.amount, order.total)
        self.assertEqual(payment.currency, order.currency)
        self.assertEqual(payment.status, 'in_progress')
        self.assertEqual(payment.paid_on, None)
        self.assertEqual(payment.amount_paid, 0)


    def test_failure_create_payment_eur(self):
        """
        Tests if payment fails when wrong currency for backend.
        PayU accepts only PLN currency payments.
        """
        order = Order(name='Test EUR order', total=100, currency='EUR')
        order.save()
        response = self.client.post(reverse('getpaid-new-payment', kwargs={'currency' : 'EUR'}),
                    {'order': order.pk,
                     'backend': 'getpaid.backends.payu'}
        )
        self.assertEqual(response.status_code, 404)


def fake_payment_get_response_success(request):
    class fake_response:
        def read(self):
            return """<?xml version="1.0" encoding="UTF-8"?>
    <response>
    <status>OK</status>
    <trans>
    <id>234748067</id>
    <pos_id>123456789</pos_id>
    <session_id>99:1342616247.41</session_id>
    <order_id>99</order_id>
    <amount>12345</amount>
    <status>99</status>
    <pay_type>t</pay_type>
    <pay_gw_name>pt</pay_gw_name>
    <desc>Test 2</desc>
    <desc2></desc2>
    <create>2012-07-18 14:57:28</create>
    <init></init>
    <sent></sent>
    <recv></recv>
    <cancel>2012-07-18 14:57:30</cancel>
    <auth_fraud>0</auth_fraud>
    <ts>1342616255805</ts>
    <sig>4d4df5557b89a4e2d8c48436b1dd3fef</sig>	</trans>
</response>"""
    return fake_response()


def fake_payment_get_response_failure(request):
    class fake_response:
        def read(self):
            return """<?xml version="1.0" encoding="UTF-8"?>
    <response>
    <status>OK</status>
    <trans>
    <id>234748067</id>
    <pos_id>123456789</pos_id>
    <session_id>98:1342616247.41</session_id>
    <order_id>98</order_id>
    <amount>12345</amount>
    <status>2</status>
    <pay_type>t</pay_type>
    <pay_gw_name>pt</pay_gw_name>
    <desc>Test 2</desc>
    <desc2></desc2>
    <create>2012-07-18 14:57:28</create>
    <init></init>
    <sent></sent>
    <recv></recv>
    <cancel>2012-07-18 14:57:30</cancel>
    <auth_fraud>0</auth_fraud>
    <ts>1342616255805</ts>
    <sig>ee77e9515599e3fd2b3721dff50111dd</sig>	</trans>
</response>"""
    return fake_response()

class PayUBackendTest(TestCase):
    def setUp(self):
        self.client = Client()

    def test_online_malformed(self):
        response = self.client.post(reverse('getpaid-payu-online'), {})
        self.assertEqual(response.content, 'MALFORMED')

    def test_online_sig_err(self):
        response = self.client.post(reverse('getpaid-payu-online'), {
            'pos_id' : 'wrong',
            'session_id': '10:11111',
            'ts' : '1111',
            'sig' : 'wrong sig',
        })
        self.assertEqual(response.content, 'SIG ERR')

    def test_online_wrong_pos_id_err(self):
        response = self.client.post(reverse('getpaid-payu-online'), {
            'pos_id' : '12345',
            'session_id': '10:11111',
            'ts' : '1111',
            'sig' : '0d6129738c0aee9d4eb56f2a1db75ab4',
            })
        self.assertEqual(response.content, 'POS_ID ERR')

    def test_online_wrong_session_id_err(self):
        response = self.client.post(reverse('getpaid-payu-online'), {
            'pos_id' : '123456789',
            'session_id': '111111',
            'ts' : '1111',
            'sig' : 'fcf3db081d5085b45fe86ed0c6a9aa5e',
            })
        self.assertEqual(response.content, 'SESSION_ID ERR')

    def test_online_ok(self):
        response = self.client.post(reverse('getpaid-payu-online'), {
            'pos_id' : '123456789',
            'session_id': '1:11111',
            'ts' : '1111',
            'sig' : '2a78322c06522613cbd7447983570188',
            })
        self.assertEqual(response.content, 'OK')

    @mock.patch("urllib2.urlopen", fake_payment_get_response_success)
    def test_payment_get_paid(self):
        Payment = get_model('getpaid', 'Payment')
        order = Order(name='Test EUR order', total='123.45', currency='PLN')
        order.save()
        payment = Payment(pk=99, order=order, amount=order.total, currency=order.currency, backend='getpaid.backends.payu')
        payment.save(force_insert=True)
        payment = Payment.objects.get(pk=99) # this line is because django bug https://code.djangoproject.com/ticket/5903
        processor = PaymentProcessor(payment)
        processor.get_payment_status('99:1342616247.41')
        self.assertEqual(payment.status, 'paid')
        self.assertNotEqual(payment.paid_on, None)
        self.assertNotEqual(payment.amount_paid, Decimal('0'))

    @mock.patch("urllib2.urlopen", fake_payment_get_response_failure)
    def test_payment_get_failed(self):
        Payment = get_model('getpaid', 'Payment')
        order = Order(name='Test EUR order', total='123.45', currency='PLN')
        order.save()
        payment = Payment(pk=98, order=order, amount=order.total, currency=order.currency, backend='getpaid.backends.payu')
        payment.save(force_insert=True)
        payment = Payment.objects.get(pk=98) # this line is because django bug https://code.djangoproject.com/ticket/5903
        processor = PaymentProcessor(payment)
        processor.get_payment_status('98:1342616247.41')
        self.assertEqual(payment.status, 'failed')
        self.assertEqual(payment.paid_on, None)
        self.assertEqual(payment.amount_paid, Decimal('0'))
