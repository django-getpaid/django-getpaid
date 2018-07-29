import json

from django.http import HttpResponse
from django.urls import reverse

from getpaid.processor import BaseProcessor


class PaymentProcessor(BaseProcessor):
    slug = "dummy"
    title = "Dummy"
    accepted_currencies = ['PLN', 'EUR']
    method = 'POST'

    def handle_callback(self, request, *args, **kwargs):
        payload = json.loads(request.data)
        if payload['status'] == 'OK':
            self.payment.on_success()
        else:
            self.payment.on_failure()

        return HttpResponse('OK')

    def get_redirect_params(self):
        return {
            'payment': self.payment.pk,
            'value': self.payment.amount,
            'currency': self.payment.currency,
            'description': self.payment.description,
            'callback': reverse('getpaid:callback-detail', kwargs=dict(pk=self.payment.pk)),
            'success_url': reverse('getpaid:payment-success', kwargs=dict(pk=self.payment.pk)),
            'failure_url': reverse('getpaid:payment-failure', kwargs=dict(pk=self.payment.pk)),
        }

    def get_redirect_url(self):
        return reverse('getpaid:dummy:gateway')
