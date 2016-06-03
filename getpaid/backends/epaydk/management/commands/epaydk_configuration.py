from django.core.management.base import BaseCommand
from django.core.urlresolvers import reverse
from getpaid.utils import get_domain


class Command(BaseCommand):
    help = 'Display URL path for Epay.dk Online URL configuration'

    def handle(self, *args, **options):
        current_site = get_domain()
        self.stdout.write('Login to Epay.dk configuration page and '
                          'setup following links:\n\n')

        success_name = 'getpaid:epaydk:success'
        path = reverse(success_name)
        self.stdout.write(' * accepturl URL: http://%s%s\n\thttps://%s%s\n\n' % (
            current_site,
            path,
            current_site,
            path
            )
        )

        failure_name = 'getpaid:epaydk:failure'
        path = reverse(failure_name)
        self.stdout.write(' * cancelurl URL: http://%s%s\n\thttps://%s%s\n\n' % (
            current_site,
            path,
            current_site,
            path
            )
        )

        path = reverse('getpaid:epaydk:online')
        self.stdout.write(' * callbackurl  URL: http://%s%s\n\thttps://%s%s\n\n' % (
            current_site,
            path,
            current_site,
            path,
            )
        )

        self.stdout.write('To change domain name please edit Sites settings.\n'
        'Don\'t forget to setup your web server to accept\nhttps connection in'
        ' order to use secure links.\n')
