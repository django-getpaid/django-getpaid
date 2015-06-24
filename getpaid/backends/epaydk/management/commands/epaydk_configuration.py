from django.contrib.sites.models import Site
from django.core.management.base import BaseCommand
from django.core.urlresolvers import reverse
from getpaid.backends.payu import PaymentProcessor


class Command(BaseCommand):
    help = 'Display URL path for Epay.dk Online URL configuration'

    def handle(self, *args, **options):

        current_site = Site.objects.get_current()

        self.stdout.write('Login to PayU configuration page and setup following links:\n\n')
        self.stdout.write(' * Success URL: http://%s%s\n                https://%s%s\n\n' % (
            current_site.domain,
            reverse('getpaid-epaydk-success', kwargs={'pk': 1234}).replace('1234', '%orderId%'),
            current_site.domain,
            reverse('getpaid-epaydk-success', kwargs={'pk': 1234}).replace('1234', '%orderId%'),

            )
        )

        self.stdout.write(' * Failure URL: http://%s%s\n                https://%s%s\n\n' % (
            current_site.domain,
            reverse('getpaid-epaydk-failure', kwargs={'pk': 1234, 'error': 9999}).replace('1234', r'%orderId%').replace('9999', r'%error%'),
            current_site.domain,
            reverse('getpaid-epaydk-failure', kwargs={'pk': 1234, 'error': 9999}).replace('1234', r'%orderId%').replace('9999', r'%error%'),
            )

        )

        self.stdout.write(' * Online  URL: http://%s%s\n                https://%s%s\n\n' % (
            current_site.domain,
            reverse('getpaid-epaydk-online'),
            current_site.domain,
            reverse('getpaid-epaydk-online'),
            )
        )

        self.stdout.write('To change domain name please edit Sites settings. '
        'Don\'t forget to setup your web server to accept https connection in'
        ' order to use secure links.\n')
