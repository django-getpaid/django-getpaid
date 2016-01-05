# coding: utf8
from decimal import Decimal
from mock import Mock, patch
from hashlib import md5

from django.apps import apps
from django.core.urlresolvers import reverse
from django.test import TestCase
from django.utils import six
from django.core.exceptions import ImproperlyConfigured

from getpaid.backends.transferuj import PaymentProcessor
from getpaid.backends import transferuj
from getpaid_test_project.orders.models import Order
from getpaid_test_project.orders.factories import PaymentFactory
from getpaid.utils import get_backend_settings


if six.PY3:
    unicode = str

class TransferujBackendTestCase(TestCase):
    def test_online_not_allowed_ip(self):
        self.assertEqual('IP ERR',
                         PaymentProcessor.online('0.0.0.0', None, None, None, None, None,
                                                                             None, None, None, None, None, None))

        #Tests allowing IP given in settings
        with self.settings(GETPAID_BACKENDS_SETTINGS={
            'getpaid.backends.transferuj': {'allowed_ip': ('1.1.1.1', '1.2.3.4'), 'key': ''},
        }):
            self.assertEqual('IP ERR',
                             PaymentProcessor.online('0.0.0.0', None, None, None, None,
                                                                                 None, None, None, None, None, None,
                                                                                 None))
            self.assertNotEqual('IP ERR',
                                PaymentProcessor.online('1.1.1.1', None, None, None, None,
                                                                                    None, None, None, None, None, None,
                                                                                    None))
            self.assertNotEqual('IP ERR',
                                PaymentProcessor.online('1.2.3.4', None, None, None, None,
                                                                                    None, None, None, None, None, None,
                                                                                    None))

        #Tests allowing all IP
        with self.settings(GETPAID_BACKENDS_SETTINGS={
            'getpaid.backends.transferuj': {'allowed_ip': [], 'key': ''},
        }):
            self.assertNotEqual('IP ERR',
                                PaymentProcessor.online('0.0.0.0', None, None, None, None,
                                                                                    None, None, None, None, None, None,
                                                                                    None))
            self.assertNotEqual('IP ERR',
                                PaymentProcessor.online('1.1.1.1', None, None, None, None,
                                                                                    None, None, None, None, None, None,
                                                                                    None))
            self.assertNotEqual('IP ERR',
                                PaymentProcessor.online('1.2.3.4', None, None, None, None,
                                                                                    None, None, None, None, None, None,
                                                                                    None))

    def test_online_wrong_sig(self):
        self.assertEqual('SIG ERR',
                         PaymentProcessor.online('195.149.229.109', '1234', '1', '', '1',
                                                                             '123.45', None, None, None, None, None,
                                                                             'xxx'))
        self.assertNotEqual('SIG ERR',
                            PaymentProcessor.online('195.149.229.109', '1234', '1', '', '1',
                                                                                '123.45', None, None, None, None, None,
                                                                                '21b028c2dbdcb9ca272d1cc67ed0574e'))

    def test_online_wrong_id(self):
        self.assertEqual('ID ERR',
                         PaymentProcessor.online('195.149.229.109', '1111', '1', '', '1',
                                                                             '123.45', None, None, None, None, None,
                                                                             '15bb75707d4374bc6e578c0cbf5a7fc7'))
        self.assertNotEqual('ID ERR',
                            PaymentProcessor.online('195.149.229.109', '1234', '1', '', '1',
                                                                                '123.45', None, None, None, None, None,
                                                                                'f5f8276fbaa98a6e05b1056ab7c3a589'))

    def test_online_crc_error(self):
        self.assertEqual('CRC ERR',
                         PaymentProcessor.online('195.149.229.109', '1234', '1', '',
                                                                             '99999', '123.45', None, None, None, None,
                                                                             None, 'f5f8276fbaa98a6e05b1056ab7c3a589'))
        self.assertEqual('CRC ERR',
                         PaymentProcessor.online('195.149.229.109', '1234', '1', '',
                                                                             'GRRGRRG', '123.45', None, None, None,
                                                                             None, None,
                                                                             '6a9e045010c27dfed24774b0afa37d0b'))

    def test_online_payment_ok(self):
        Payment = apps.get_model('getpaid', 'Payment')
        order = Order(name='Test EUR order', total='123.45', currency='PLN')
        order.save()
        payment = Payment(order=order, amount=order.total, currency=order.currency, backend='getpaid.backends.payu')
        payment.save(force_insert=True)
        self.assertEqual('TRUE', PaymentProcessor.online('195.149.229.109', '1234', '1', '',
                                                                                     payment.pk, '123.45', '123.45', '',
                                                                                     'TRUE', 0, '',
                                                                                     '21b028c2dbdcb9ca272d1cc67ed0574e'))
        payment = Payment.objects.get(pk=payment.pk)
        self.assertEqual(payment.status, 'paid')
        self.assertNotEqual(payment.paid_on, None)
        self.assertEqual(payment.amount_paid, Decimal('123.45'))

    def test_online_payment_ok_over(self):
        Payment = apps.get_model('getpaid', 'Payment')
        order = Order(name='Test EUR order', total='123.45', currency='PLN')
        order.save()
        payment = Payment(order=order, amount=order.total, currency=order.currency, backend='getpaid.backends.payu')
        payment.save(force_insert=True)
        self.assertEqual('TRUE', PaymentProcessor.online('195.149.229.109', '1234', '1', '',
                                                                                     payment.pk, '123.45', '223.45', '',
                                                                                     'TRUE', 0, '',
                                                                                     '21b028c2dbdcb9ca272d1cc67ed0574e'))
        payment = Payment.objects.get(pk=payment.pk)
        self.assertEqual(payment.status, 'paid')
        self.assertNotEqual(payment.paid_on, None)
        self.assertEqual(payment.amount_paid, Decimal('223.45'))

    def test_online_payment_partial(self):
        Payment = apps.get_model('getpaid', 'Payment')
        order = Order(name='Test EUR order', total='123.45', currency='PLN')
        order.save()
        payment = Payment(order=order, amount=order.total, currency=order.currency, backend='getpaid.backends.payu')
        payment.save(force_insert=True)
        self.assertEqual('TRUE', PaymentProcessor.online('195.149.229.109', '1234', '1', '',
                                                                                     payment.pk, '123.45', '23.45', '',
                                                                                     'TRUE', 0, '',
                                                                                     '21b028c2dbdcb9ca272d1cc67ed0574e'))
        payment = Payment.objects.get(pk=payment.pk)
        self.assertEqual(payment.status, 'partially_paid')
        self.assertNotEqual(payment.paid_on, None)
        self.assertEqual(payment.amount_paid, Decimal('23.45'))

    def test_online_payment_failure(self):
        Payment = apps.get_model('getpaid', 'Payment')
        order = Order(name='Test EUR order', total='123.45', currency='PLN')
        order.save()
        payment = Payment(order=order, amount=order.total, currency=order.currency, backend='getpaid.backends.payu')
        payment.save(force_insert=True)
        self.assertEqual('TRUE', PaymentProcessor.online('195.149.229.109', '1234', '1', '',
                                                                                     payment.pk, '123.45', '23.45', '',
                                                                                     False, 0, '',
                                                                                     '21b028c2dbdcb9ca272d1cc67ed0574e'))
        payment = Payment.objects.get(pk=payment.pk)
        self.assertEqual(payment.status, 'failed')


class PaymentProcessorGetGatewayUrl(TestCase):

    def setUp(self):
        self.payment = PaymentFactory()
        self.pp = PaymentProcessor(self.payment)

    def update_settings(self, data):
        settings = get_backend_settings('getpaid.backends.transferuj')
        settings.update(data)

        return {'getpaid.backends.transferuj': settings}

    def get_geteway_data(self):
        settings = self.update_settings({'method': 'post'})
        with self.settings(GETPAID_BACKENDS_SETTINGS=settings):
            url, method, data = self.pp.get_gateway_url(Mock())

        return data

    def test_return_types(self):
        settings = self.update_settings({'method': 'get'})

        with self.settings(GETPAID_BACKENDS_SETTINGS=settings):
            url, method, data = self.pp.get_gateway_url(Mock())

        self.assertEquals(method, 'GET')
        self.assertEquals(data, {})
        self.assertIsInstance(url, str)

    def test_default_config_url_transaction_params(self):
        data = self.get_geteway_data()

        crc = data['crc']
        kwota = data['kwota']
        id_ = data['id']
        key = PaymentProcessor.get_backend_setting('key')
        md5sum = six.text_type(id_) + kwota + six.text_type(crc) + key
        md5sum = md5sum.encode('utf-8')

        self.assertEquals(crc, self.payment.pk)
        self.assertEquals(kwota, six.text_type(self.payment.amount))
        self.assertEquals(id_, 1234)
        self.assertEquals(data['md5sum'], md5(md5sum).hexdigest())

    def test_default_config_url_data_params(self):
        data = self.get_geteway_data()

        self.assertEquals(data['email'], 'test@test.com')
        self.assertIn('opis', data)
        self.assertNotIn('jezyk', data)

    def get_urls(self):
        return {
            'wyn_url': reverse('getpaid-transferuj-online'),
            'pow_url_blad': reverse('getpaid-transferuj-failure',
                                    kwargs={'pk': self.payment.pk}),
            'pow_url': reverse('getpaid-transferuj-success',
                               kwargs={'pk': self.payment.pk}),
        }

    def test_default_config_url_urls(self):
        data = self.get_geteway_data()

        for key, u in self.get_urls().items():
            str_ = data[key]
            self.assertTrue(str_.endswith(u),
                            "{} not end with {}".format(str_, u))

    @patch.object(transferuj, 'get_domain')
    def test_domains_http(self, patch_domain):
        patch_domain.return_value = 'test'

        data = self.get_geteway_data()

        for key in self.get_urls():
            self.assertTrue(data[key].startswith('http://test/'))

    @patch.object(transferuj, 'get_domain')
    def test_domains_https(self, patch_domain):
        patch_domain.return_value = 'test'
        settings = self.update_settings({
            'force_ssl_online': True,
            'force_ssl_return': True,
        })

        with self.settings(GETPAID_BACKENDS_SETTINGS=settings):
            data = self.get_geteway_data()

        for key in self.get_urls():
            str_ = data[key]
            self.assertTrue(str_.startswith('https://test/'),
                            "{} not start with https://test/".format(str_))

    def test_post(self):
        settings = self.update_settings({'method': 'post'})

        with self.settings(GETPAID_BACKENDS_SETTINGS=settings):
            url, method, data = self.pp.get_gateway_url(Mock())

        self.assertEquals(method, 'POST')
        self.assertNotEquals(data, {})

    def test_bad_type(self):
        settings = self.update_settings({'method': 'update'})

        with self.settings(GETPAID_BACKENDS_SETTINGS=settings):
            with self.assertRaises(ImproperlyConfigured):
                self.pp.get_gateway_url(Mock())
