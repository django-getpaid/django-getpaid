from django.core.urlresolvers import reverse
from django.shortcuts import get_object_or_404
from django.views.generic.edit import FormView
from . import PaymentProcessor
from .forms import PaymillForm
from getpaid.models import Payment
import pymill


class PaymillView(FormView):
    form_class = PaymillForm
    template_name = 'getpaid_paymill_backend/paymill.html'

    def get_context_data(self, **kwargs):
        context = super(PaymillView, self).get_context_data(**kwargs)
        self.payment = get_object_or_404(Payment, pk=self.kwargs['pk'], status='in_progress', backend='getpaid.backends.paymill')
        context['payment'] = self.payment
        context['amount_int'] = int(self.payment.amount * 100)
        context['order'] = self.payment.order
        context['order_name'] = PaymentProcessor(self.payment).get_order_description(self.payment, self.payment.order)  # TODO: Refactoring of get_order_description needed, should not require payment arg
        context['PAYMILL_PUBLIC_KEY'] = PaymentProcessor.get_backend_setting('PAYMILL_PUBLIC_KEY')
        return context

    def get_success_url(self):
        url = None
        if self.success:
            url = reverse('getpaid:success-fallback', kwargs={'pk': self.payment.pk})
        else:
            url = reverse('getpaid:failure-fallback', kwargs={'pk': self.payment.pk})
        return url

    def form_valid(self, form):
        # Change payment status and jump to success_url or failure_url
        self.payment = get_object_or_404(Payment, pk=self.kwargs['pk'], status='in_progress', backend='getpaid.backends.paymill')

        pmill = pymill.Pymill(PaymentProcessor.get_backend_setting('PAYMILL_PRIVATE_KEY'))

        token = form.cleaned_data['token']
        card = pmill.new_card(token)

        amount = int(self.payment.amount * 100)
        currency = self.payment.currency

        transaction = pmill.transact(amount, payment=card, currency=currency)

        if transaction:
            self.success = True
            if not self.payment.on_success():
                # This method returns if payment was fully paid
                # if it is not, we should alert user that payment was not successfully ended anyway
                self.success = False
        else:
            self.success = False
            self.payment.on_failure()
        return super(PaymillView, self).form_valid(form)
