# Create your views here.
from django.conf import settings
from django.core.urlresolvers import reverse
from django.http import Http404, HttpResponseRedirect
from django.shortcuts import get_object_or_404
from django.views.generic.base import RedirectView
from django.views.generic.edit import FormView
from getpaid.forms import PaymentMethodForm
from getpaid.models import Payment

class NewPaymentView(FormView):
    form_class = PaymentMethodForm

    def get_form(self, form_class):
        self.currency = self.kwargs['currency']
        return form_class(self.currency, **self.get_form_kwargs())


    def get(self, request, *args, **kwargs):
        """
        This view operates only on POST requests from order view where you select payment method
        """
        raise Http404

    def form_valid(self, form):
        from getpaid.models import Payment
        payment = Payment.create(form.cleaned_data['order'], form.cleaned_data['backend'])
        gateway_url = payment.get_processor()(payment).get_gateway_url(self.request)
        payment.change_status('in_progress')
        return HttpResponseRedirect(gateway_url)

    def form_invalid(self, form):
        raise Http404



class FallbackView(RedirectView):
    success = None
    permanent = False

    def get_redirect_url(self, **kwargs):
        self.payment = get_object_or_404(Payment, pk=self.kwargs['pk'])
        if self.success :
            url_name = getattr(settings, 'GETPAID_SUCCESS_URL_NAME', None)
            if url_name is not None:
                return reverse(url_name, kwargs={'pk': self.payment.order})
        else:
            url_name = getattr(settings, 'GETPAID_FAILURE_URL_NAME', None)
            if url_name is not None:
                return reverse(url_name, kwargs={'pk': self.payment.order})
        return self.payment.order.get_absolute_url()

