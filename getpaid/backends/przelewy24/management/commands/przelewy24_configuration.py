from django.contrib.sites.models import Site
from django.core.management.base import BaseCommand
from django.core.urlresolvers import reverse
from getpaid.backends.przelewy24 import PaymentProcessor


class Command(BaseCommand):
    help = 'Additional Przelewy24 configuration'

    def handle(self, *args, **options):
        current_site = Site.objects.get_current()

        self.stdout.write(
            'Please contact with Przelewy24 (serwis@przelewy24.pl) and provide them with the following URL: \n\n')

        self.stdout.write(
            ('https://' if PaymentProcessor.get_backend_setting('ssl_return', False) else 'http://') + '%s%s\n\n' % (
                current_site.domain, reverse('getpaid-przelewy24-online'))
        )

        self.stdout.write(
            'This is an additional URL for accepting payment status updates.\n\n')

        self.stdout.write(
            'To change domain name please edit Sites settings. Don\'t forget to setup your web server to accept https connection in order to use secure links.\n')
        if PaymentProcessor.get_backend_setting('sandbox', False):
            self.stdout.write('\nSandbox mode is ON.\n')
