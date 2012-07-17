"""
This file demonstrates writing tests using the unittest module. These will pass
when you run "manage.py test".

Replace this with more appropriate tests for your application.
"""
from django.core.urlresolvers import reverse

from django.test import TestCase
from django.test.client import Client
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
        from getpaid.models import Payment
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
        from getpaid.models import Payment
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