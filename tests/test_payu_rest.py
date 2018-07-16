# coding: utf-8
# flake8: noqa
from django.apps import apps
from django.test import TestCase
from django.test.client import Client
from django.urls import reverse
import mock

from orders.models import Order


class PayURestTestCase(TestCase):
    def setUp(self):
        self.client = Client()

    def test_payu_payment_succesful_flow(self):
        Payment = apps.get_model('getpaid', 'Payment')
        order = Order(name='Test PLN order', total='199.99', currency='PLN')
        order.save()
        payment = Payment(pk=22, order=order, amount=order.total, currency=order.currency,
                          backend='getpaid.backends.payu_rest')
        payment.save(force_insert=True)
        confirm_url = reverse('getpaid:payu_rest:confirm')

        # Fake PayU pings on confirmation URL
        # PENDING
        data_1 = b"""{"order":{"orderId":"5C4BHGP6BN180712GUEST000P01","extOrderId":"22","orderCreateDate":"2018-07-12T14:45:07.801+02:00","notifyUrl":"http://getpaid.requestcatcher.com/","customerIp":"127.0.0.1","merchantPosId":"123456","description":"Test Payment","currencyCode":"PLN","totalAmount":"19999","status":"PENDING","products":[{"name":"Order #123456 from example.com","unitPrice":"19999","quantity":"1"}]},"localReceiptDateTime":"2018-07-12T14:51:21.582+02:00","properties":[{"name":"PAYMENT_ID","value":"73543257"}]}"""
        with mock.patch("getpaid.backends.payu_rest.views.get_request_body", return_value=data_1):
            self.client.post(confirm_url,
                             data={},
                             **{
                                 "HTTP_OPENPAYU_SIGNATURE": "sender=checkout;signature=727eac9f18396ba980c69bec7fbb23a4;algorithm=MD5;content=DOCUMENT"
                             })
            payment.refresh_from_db()
            assert payment.status == 'in_progress'

        # CONFIRMED
        data_2 = b"""{"order":{"orderId":"5C4BHGP6BN180712GUEST000P01","extOrderId":"22","orderCreateDate":"2018-07-12T14:45:07.801+02:00","notifyUrl":"http://getpaid.requestcatcher.com/","customerIp":"127.0.0.1","merchantPosId":"123456","description":"Test Payment","currencyCode":"PLN","totalAmount":"19999","buyer":{"customerId":"guest","email":"test@test.com"},"payMethod":{"amount":"19999","type":"PBL"},"status":"COMPLETED","products":[{"name":"Order #123456 from example.com","unitPrice":"19999","quantity":"1"}]},"localReceiptDateTime":"2018-07-12T14:51:21.582+02:00","properties":[{"name":"PAYMENT_ID","value":"73543257"}]}"""
        with mock.patch("getpaid.backends.payu_rest.views.get_request_body", return_value=data_2):
            self.client.post(confirm_url,
                             data={},
                             **{
                                 "HTTP_OPENPAYU_SIGNATURE": "sender=checkout;signature=8b23abfed2ca7cdd657a6360d70b4193;algorithm=MD5;content=DOCUMENT"
                             })
            payment.refresh_from_db()
            assert payment.status == 'paid'

        # OUT OF ORDER REQUEST
        with mock.patch("getpaid.backends.payu_rest.views.get_request_body", return_value=data_1):
            self.client.post(confirm_url,
                             data={},
                             **{
                                 "HTTP_OPENPAYU_SIGNATURE": "sender=checkout;signature=0984ef00ab1f4abb137849ae665d33e9;algorithm=MD5;content=DOCUMENT"
                             })
            payment.refresh_from_db()
            assert payment.status == 'paid'

    def test_payment_failed_flow(self):
        Payment = apps.get_model('getpaid', 'Payment')
        order = Order(name='Test PLN order', total='20.00', currency='PLN')
        order.save()
        payment = Payment(pk=23, order=order, amount=order.total, currency=order.currency,
                          backend='getpaid.backends.payu_rest')
        payment.save(force_insert=True)

        confirm_url = "http://localhost" + reverse('getpaid:payu_rest:confirm')

        # Fake PayU pings on confirmation URL
        # PENDING
        data_1 = b"""{"order":{"orderId":"6N73GWVD9P180712GUEST000P01","extOrderId":"23","orderCreateDate":"2018-07-12T14:55:18.209+02:00","notifyUrl":"http://getpaid.requestcatcher.com/","customerIp":"127.0.0.1","merchantPosId":"123456","description":"Test Payment","currencyCode":"PLN","totalAmount":"2000","status":"PENDING","products":[{"name":"Order #123456 from example.com","unitPrice":"2000","quantity":"1"}]},"properties":[{"name":"PAYMENT_ID","value":"73543299"}]}"""
        with mock.patch("getpaid.backends.payu_rest.views.get_request_body", return_value=data_1):
            self.client.post(confirm_url,
                             data={},
                             **{
                                 "HTTP_OPENPAYU_SIGNATURE": "sender=checkout;signature=f5482f0bca32c3094f6840637ae0c52f;algorithm=MD5;content=DOCUMENT"
                             })
            payment.refresh_from_db()
            assert payment.status == 'in_progress'

        # FAILED
        data_2 = b"""{"order":{"orderId":"6N73GWVD9P180712GUEST000P01","extOrderId":"23","orderCreateDate":"2018-07-12T14:55:18.209+02:00","notifyUrl":"http://getpaid.requestcatcher.com/","customerIp":"127.0.0.1","merchantPosId":"123456","description":"Test Payment","currencyCode":"PLN","totalAmount":"2000","status":"CANCELED","products":[{"name":"Order #123456 from example.com","unitPrice":"2000","quantity":"1"}]},"properties":[{"name":"PAYMENT_ID","value":"73543299"}]}"""
        with mock.patch("getpaid.backends.payu_rest.views.get_request_body", return_value=data_2):
            self.client.post(confirm_url,
                             data={},
                             **{
                                 "HTTP_OPENPAYU_SIGNATURE": "sender=checkout;signature=c69bc143125a7423e5fdfa6714db9753;algorithm=MD5;content=DOCUMENT"
                             })
            payment.refresh_from_db()
            assert payment.status == 'cancelled'
