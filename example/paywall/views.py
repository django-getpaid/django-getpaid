import json

import httpx
from django.conf import settings
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.views.decorators.csrf import csrf_exempt
from django.views.generic import FormView

from getpaid.status import PaymentStatus as ps

from .forms import QuestionForm
from .models import PaymentEntry


class AuthorizationView(FormView):
    """
    This view simulates the behavior of payment broker
    """

    form_class = QuestionForm
    template_name = 'paywall/fake_gateway_authorization_form.html'
    success = None

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        params = (
            self.request.POST or self.request.GET
        )  # both cases for testability
        if 'pay_id' in params:
            obj = get_object_or_404(PaymentEntry, id=params.get('pay_id'))
            context['ext_id'] = obj.ext_id
            context['value'] = obj.value
            context['currency'] = obj.currency
            context['description'] = obj.description

            context['message'] = 'Presenting pre-registered payment'
        else:
            context['ext_id'] = params.get('ext_id')
            context['value'] = params.get('value')
            context['currency'] = params.get('currency')
            context['description'] = params.get('description')

            context['message'] = 'Presenting directly requested payment'
        return context

    def get_initial(self):
        initial = super().get_initial()
        params = self.request.POST or self.request.GET
        if 'pay_id' in params:
            obj = get_object_or_404(PaymentEntry, id=params.get('pay_id'))
            initial['callback'] = obj.callback
            initial['success_url'] = obj.success_url
            initial['failure_url'] = obj.failure_url
        else:
            initial['callback'] = params.get('callback', '')
            initial['success_url'] = params.get('success_url', '')
            initial['failure_url'] = params.get('failure_url', '')
        return initial

    def get_success_url(self):
        if self.success:
            return self.form.cleaned_data['success_url']
        return self.form.cleaned_data['failure_url']

    def form_valid(self, form):
        self.form = form
        callback = form.cleaned_data['callback']
        url = self.request.build_absolute_uri(callback) if callback else None
        if url:
            if form.cleaned_data['authorize_payment'] == '1':
                self.success = True
                if settings.PAYWALL_MODE == 'LOCK':
                    httpx.post(url, json={'new_status': ps.PRE_AUTH})
                else:
                    httpx.post(url, json={'new_status': ps.PAID})
            else:
                self.success = False
                httpx.post(url, json={'new_status': ps.FAILED})
        return super().form_valid(form)


authorization_view = csrf_exempt(AuthorizationView.as_view())


def get_status(request, pk, **kwargs):
    obj = get_object_or_404(PaymentEntry, pk=pk)
    return JsonResponse({
        'payment_status': obj.payment_status,
        'fraud_status': obj.fraud_status,
    })


@csrf_exempt
def rest_register_payment(request):
    legal_fields = [
        'ext_id',
        'value',
        'currency',
        'description',
        'callback',
        'success_url',
        'failure_url',
    ]
    params = {
        k: v for k, v in json.loads(request.body).items() if k in legal_fields
    }
    payment = PaymentEntry.objects.create(**params)

    url = request.build_absolute_uri(reverse('paywall:gateway'))
    url += f'?pay_id={payment.id}'

    content = {'url': url}
    return JsonResponse(content)


@csrf_exempt
def rest_operation(request):
    """
    For test purposes backend can "suggest" the flow of payment.
    """
    data = json.loads(request.body)

    payment_id = data['id']
    new_status = data['new_status']

    payment = PaymentEntry.objects.create(id=payment_id)
    if new_status == ps.PRE_AUTH:
        payment.send_confirm_lock()
    elif new_status == ps.PAID:
        if payment.payment_status == ps.PRE_AUTH:
            payment.send_confirm_charge()
        elif payment.payment_status == ps.REFUND_STARTED:
            payment.cancel_refund()
        else:
            raise NotImplementedError(
                f'Cannot handle change to {ps.PAID} from {payment.payment_status}'
            )
    elif new_status == ps.FAILED:
        payment.send_fail()
    elif new_status == ps.REFUND_STARTED:
        payment.start_refund()
    elif new_status == ps.REFUNDED:
        payment.send_confirm_refund()

    return JsonResponse({'id': str(payment_id), 'new_status': new_status})
