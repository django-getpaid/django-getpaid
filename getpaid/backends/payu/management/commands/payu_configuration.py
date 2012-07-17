from django.core.management.base import BaseCommand
from django.core.urlresolvers import reverse
from getpaid.backends.payu import PaymentProcessor

class Command(BaseCommand):
    help = 'Display URL path for PayU Online URL configuration'

    def handle(self, *args, **options):
        self.stdout.write('Login to PayU configuration page and setup following links:\n\n')
        self.stdout.write(' * Success URL: %s\n' % reverse('getpaid-payu-success', kwargs={'pk': 1234}).replace('1234', '%orderId%'))
        self.stdout.write(' * Failure URL: %s\n' % reverse('getpaid-payu-failure', kwargs={'pk': 1234}).replace('1234', '%orderId%'))
        self.stdout.write(' * Online  URL: %s\n\n' % reverse('getpaid-payu-online'))
        self.stdout.write('Please remember to convert this paths to fully qualified URL by prefixing them with protocol and domain name (http(s)://yourdomain).\n')
        if PaymentProcessor.get_backend_setting('testing', False):
            self.stdout.write('\nTesting mode is ON\nPlease be sure that you enabled testing payments in PayU configuration page.\n')
        if PaymentProcessor.get_backend_setting('signing', False):
            self.stdout.write('\nRequest signing is ON\nPlease be sure that you enabled signing payments in PayU configuration page.\n')