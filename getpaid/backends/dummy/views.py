from django.core.urlresolvers import reverse
from django.shortcuts import get_object_or_404
from django.views.generic.edit import FormView

from getpaid.backends.dummy import PaymentProcessor
from getpaid.backends.dummy.forms import DummyQuestionForm
from getpaid.models import Payment


class DummyAuthorizationView(FormView):
    form_class = DummyQuestionForm
    template_name = "getpaid_dummy_backend/dummy_authorization.html"

    def get_context_data(self, **kwargs):
        context = super(DummyAuthorizationView, self).get_context_data(**kwargs)
        self.payment = get_object_or_404(Payment, pk=self.kwargs['pk'], status='in_progress', backend='getpaid.backends.dummy')
        context['payment'] = self.payment
        context['order'] = self.payment.order
        context['order_name'] = PaymentProcessor(self.payment).get_order_description(self.payment, self.payment.order)  # TODO: Refactoring of get_order_description needed, should not require payment arg
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
        self.payment = get_object_or_404(Payment, pk=self.kwargs['pk'], status='in_progress', backend='getpaid.backends.dummy')

        if form.cleaned_data['authorize_payment'] == '1':
            self.success = True
            if not self.payment.on_success():
                # This method returns if payment was fully paid
                # if it is not, we should alert user that payment was not successfully ended anyway
                self.success = False
        else:
            self.success = False
            self.payment.on_failure()
        return super(DummyAuthorizationView, self).form_valid(form)
