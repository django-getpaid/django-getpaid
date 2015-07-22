# getpaid views
import logging
from django.conf import settings
from django.core.exceptions import PermissionDenied, ImproperlyConfigured
from django.core.urlresolvers import reverse
from django.http import Http404, HttpResponseRedirect
from django.shortcuts import get_object_or_404
from django.template.response import TemplateResponse
from django.views.generic.base import RedirectView
from django.views.generic.edit import FormView
from getpaid.forms import PaymentMethodForm, ValidationError
from getpaid.signals import (redirecting_to_payment_gateway_signal,
                             order_additional_validation)


logger = logging.getLogger(__name__)


class NewPaymentView(FormView):
    form_class = PaymentMethodForm
    template_name = "getpaid/payment_post_form.html"

    def get_form(self, form_class):
        self.currency = self.kwargs['currency']
        return form_class(self.currency, **self.get_form_kwargs())

    def get(self, request, *args, **kwargs):
        """
        This view operates only on POST requests from order view where
        you select payment method
        """
        raise Http404

    def form_valid(self, form):
        from getpaid.models import Payment
        try:
            order_additional_validation\
                .send(sender=None, request=self.request,
                    order=form.cleaned_data['order'],
                    backend=form.cleaned_data['backend'])
        except ValidationError:
            return self.form_invalid(form)

        payment = Payment.create(form.cleaned_data['order'],
                                 form.cleaned_data['backend'])
        processor = payment.get_processor()(payment)
        gateway_url_tuple = processor.get_gateway_url(self.request)
        payment.change_status('in_progress')
        redirecting_to_payment_gateway_signal.send(sender=None,
            request=self.request, order=form.cleaned_data['order'],
            payment=payment, backend=form.cleaned_data['backend'])

        if gateway_url_tuple[1].upper() == 'GET':
            return HttpResponseRedirect(gateway_url_tuple[0])
        elif gateway_url_tuple[1].upper() == 'POST':
            context = self.get_context_data()
            context['gateway_url'] = \
                processor.get_gateway_url(self.request)[0]
            context['form'] = processor.get_form(gateway_url_tuple[2])

            return TemplateResponse(request=self.request,
                template=self.get_template_names(),
                context=context)
        else:
            raise ImproperlyConfigured()

    def form_invalid(self, form):
        raise PermissionDenied


class FallbackView(RedirectView):
    success = None
    permanent = False

    def get_redirect_url(self, **kwargs):
        from getpaid.models import Payment
        self.payment = get_object_or_404(Payment, pk=self.kwargs['pk'])

        if self.success:
            url_name = getattr(settings, 'GETPAID_SUCCESS_URL_NAME', None)
            if url_name is not None:
                return reverse(url_name, kwargs={'pk': self.payment.order_id})
        else:
            url_name = getattr(settings, 'GETPAID_FAILURE_URL_NAME', None)
            if url_name is not None:
                return reverse(url_name, kwargs={'pk': self.payment.order_id})
        return self.payment.order.get_absolute_url()
