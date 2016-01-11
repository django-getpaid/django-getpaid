"""
This file demonstrates writing tests using the unittest module. These will pass
when you run "manage.py test".

Replace this with more appropriate tests for your application.
"""
from django.core.urlresolvers import reverse
from django.apps import apps
from django.forms import ValidationError
from django.test import TestCase
from django.test.client import Client

from getpaid import signals
from getpaid_test_project.orders.models import Order


class OrderTest(TestCase):
    def setUp(self):
        self.client = Client()

    def test_order_view(self):
        order = Order(name='Test EUR order', total=100, currency='EUR')
        order.save()
        resp = self.client.get(order.get_absolute_url())
        self.assertEqual(200, resp.status_code)
        self.assertTemplateUsed(resp, 'orders/order_detail.html')

    def test_successful_create_payment_dummy_eur(self):
        """
        Tests if payment is successfully created
        """
        order = Order(name='Test EUR order', total=100, currency='EUR')
        order.save()
        url = reverse('getpaid-new-payment', kwargs={'currency': 'EUR'})
        data = {'order': order.pk, 'backend': 'getpaid.backends.dummy'}
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, 302)
        Payment = apps.get_model('getpaid', 'Payment')
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
        response = self.client.post(reverse('getpaid-new-payment', kwargs={'currency': 'PLN'}),
                                    {'order': order.pk,
                                     'backend': 'getpaid.backends.payu'}
        )
        self.assertEqual(response.status_code, 302)
        Payment = apps.get_model('getpaid', 'Payment')
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
        response = self.client.post(reverse('getpaid-new-payment',
                                            kwargs={'currency': 'EUR'}),
                                    {'order': order.pk,
                                     'backend': 'getpaid.backends.payu'})
        self.assertEqual(response.status_code, 403)

    def test_failure_order_additional_validation(self):
        """
        Tests if HTTP304 when order additional validation signal raises
        ValidationError exception.
        """
        def custom_validation_listener(sender=None, request=None, order=None,
                                       backend=None, **kwargs):
            raise ValidationError("BOOM!")
        suid = 'test-order_additional_validation'
        signals.order_additional_validation.connect(custom_validation_listener,
                                                    dispatch_uid=suid)

        order = Order(name='Test order custom validation',
                      total=100,
                      currency='PLN')
        order.save()
        try:
            url = reverse('getpaid-new-payment', kwargs={'currency': 'PLN'})
            data = {'order': order.pk, 'backend': 'getpaid.backends.payu'}
            response = self.client.post(url, data)
            self.assertEqual(response.status_code, 403)
        finally:
            signals.order_additional_validation.disconnect(dispatch_uid=suid)
