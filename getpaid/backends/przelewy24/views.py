import logging
from django.core.urlresolvers import reverse
from django.http import HttpResponse, HttpResponseRedirect
from django.views.generic.base import View
from django.views.generic.detail import DetailView
from getpaid.backends.przelewy24 import PaymentProcessor
from getpaid.models import Payment

logger = logging.getLogger('getpaid.backends.przelewy24')


class OnlineView(View):
    """
    This View answers on Przelewy24 online request that is acknowledge of payment
    status change.
    """

    def post(self, request, *args, **kwargs):
        try:
            p24_session_id = request.POST['p24_session_id']
            p24_order_id = request.POST['p24_order_id']
            p24_kwota = request.POST['p24_kwota']
            p24_order_id_full = request.POST['p24_order_id_full']
            p24_crc = request.POST['p24_crc']
        except KeyError:
            logger.warning('Got malformed POST request: %s' % str(request.POST))
            return HttpResponse('MALFORMED', status=500)

        if PaymentProcessor.on_payment_status_change(p24_session_id, p24_order_id, p24_kwota, p24_order_id_full,
                                                     p24_crc):
            return HttpResponse('OK')
        else:
            return HttpResponse('CRC ERR')


class SuccessView(DetailView):
    """
    This view just redirects to standard backend success link after it schedule payment status checking.
    """
    model = Payment

    def get(self, request, *args, **kwargs):
        return HttpResponse('GET not allowed')

    def post(self, request, *args, **kwargs):
        try:
            p24_session_id = request.POST['p24_session_id']
            p24_order_id = request.POST['p24_order_id']
            p24_kwota = request.POST['p24_kwota']
            p24_order_id_full = request.POST['p24_order_id_full']
            p24_crc = request.POST['p24_crc']
        except KeyError:
            logger.warning('Got malformed POST request: %s' % str(request.POST))
            return HttpResponse('MALFORMED', status=500)

        PaymentProcessor.on_payment_status_change(p24_session_id, p24_order_id, p24_kwota, p24_order_id_full, p24_crc)

        self.object = self.get_object()
        context = self.get_context_data(object=self.object)
        return self.render_to_response(context)

    def render_to_response(self, context, **response_kwargs):
        return HttpResponseRedirect(reverse('getpaid:success-fallback', kwargs={'pk': self.object.pk}))


class FailureView(DetailView):
    """
    This view just redirects to standard backend failure link after it schedule payment status checking.
    """
    model = Payment

    def post(self, request, *args, **kwargs):
        try:
            p24_session_id = request.POST['p24_session_id']
            p24_order_id = request.POST['p24_order_id']
            p24_kwota = request.POST['p24_kwota']
            p24_order_id_full = request.POST['p24_order_id_full']
            p24_crc = request.POST['p24_crc']
        except KeyError:
            logger.warning('Got malformed POST request: %s' % str(request.POST))
            return HttpResponse('MALFORMED', status=500)

        PaymentProcessor.on_payment_status_change(p24_session_id, p24_order_id, p24_kwota, p24_order_id_full, p24_crc)

        self.object = self.get_object()
        context = self.get_context_data(object=self.object)
        return self.render_to_response(context)

    def render_to_response(self, context, **response_kwargs):
        logger.error("Payment %s failed on backend error" % (self.kwargs['pk'],))
        return HttpResponseRedirect(reverse('getpaid:failure-fallback', kwargs={'pk': self.object.pk}))
