# Create your views here.
from django.conf import settings
from django.core.exceptions import PermissionDenied, ImproperlyConfigured
from django.core.urlresolvers import reverse
from django.http import Http404, HttpResponseRedirect
from django.shortcuts import get_object_or_404
from django.views.generic import DetailView
from django.views.generic.base import RedirectView, TemplateView
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

        if gateway_url[1] == 'GET':
            return HttpResponseRedirect(gateway_url)
        elif gateway_url[1] == 'POST':
            return HttpResponseRedirect(reverse("getpaid-payment-post", args=[payment.pk]))
        else:
            raise ImproperlyConfigured()

    def form_invalid(self, form):
        raise PermissionDenied

class PaymentPostView(DetailView):
    model = Payment
    template_name = "payment_post_form.html"

    def get_template_names(self):
        names = super(PaymentPostView, self).get_template_names()

        processor = self.object.get_processor()(self.object)

        try:
            names.insert(0, processor.get_backend_setting('template'))
        except ImproperlyConfigured:
            pass
        return names

    def get_context_data(self, **kwargs):
        context = super(PaymentPostView, self).get_context_data(**kwargs)
        processor = self.object.get_processor()(self.object)

        context['gateway_url'] = processor.get_gateway_url(self.request)[0]
        context['form'] = processor.get_form()
        return context

class FallbackView(RedirectView):
    success = None
    permanent = False

    def get_redirect_url(self, **kwargs):
        self.payment = get_object_or_404(Payment, pk=self.kwargs['pk'])
        if self.success :
            url_name = getattr(settings, 'GETPAID_SUCCESS_URL_NAME', None)
            if url_name is not None:
                return reverse(url_name, kwargs={'pk': self.payment.order_id})
        else:
            url_name = getattr(settings, 'GETPAID_FAILURE_URL_NAME', None)
            if url_name is not None:
                return reverse(url_name, kwargs={'pk': self.payment.order_id})
        return self.payment.order.get_absolute_url()