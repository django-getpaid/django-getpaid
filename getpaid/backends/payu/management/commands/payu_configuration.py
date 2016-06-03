from django.core.management.base import BaseCommand
from django.core.urlresolvers import reverse
from getpaid.backends.payu import PaymentProcessor
from getpaid.utils import get_domain


class Command(BaseCommand):
    help = 'Display URL path for PayU Online URL configuration'

    def handle(self, *args, **options):

        current_site = get_domain()

        self.stdout.write('Login to PayU configuration page and setup following links:\n\n')
        self.stdout.write(' * Success URL: http://%s%s\n                https://%s%s\n\n' % (
            current_site,
            reverse('getpaid:payu:success', kwargs={'pk': 1234}).replace('1234', '%orderId%'),
            current_site,
            reverse('getpaid:payu:success', kwargs={'pk': 1234}).replace('1234', '%orderId%'),

            )
        )

        self.stdout.write(' * Failure URL: http://%s%s\n                https://%s%s\n\n' % (
            current_site,
            reverse('getpaid:payu:failure', kwargs={'pk': 1234, 'error': 9999}).replace('1234', r'%orderId%').replace('9999', r'%error%'),
            current_site,
            reverse('getpaid:payu:failure', kwargs={'pk': 1234, 'error': 9999}).replace('1234', r'%orderId%').replace('9999', r'%error%'),
            )

        )

        self.stdout.write(' * Online  URL: http://%s%s\n                https://%s%s\n\n' % (
            current_site,
            reverse('getpaid:payu:online'),
            current_site,
            reverse('getpaid:payu:online'),
            )
        )

        self.stdout.write('To change domain name please edit Sites settings. Don\'t forget to setup your web server to accept https connection in order to use secure links.\n')
        if PaymentProcessor.get_backend_setting('testing', False):
            self.stdout.write('\nTesting mode is ON\nPlease be sure that you enabled testing payments in PayU configuration page.\n')
        if PaymentProcessor.get_backend_setting('signing', False):
            self.stdout.write('\nRequest signing is ON\n * Please be sure that you enabled signing payments in PayU configuration page.\n')
