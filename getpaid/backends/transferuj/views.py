import logging

from django.urls import reverse
from django import http
from django.views.generic.base import View
from django.views.generic.detail import DetailView

from getpaid.backends.transferuj import PaymentProcessor
from getpaid.models import Payment
from getpaid.utils import get_ip_address

logger = logging.getLogger('getpaid.backends.transferuj')


class OnlineView(View):
    """
    This View answers on Transferuj.pl payment status change request

    The most important logic of this view is delegated to ``PaymentProcessor.online()`` method
    """

    def post(self, request, *args, **kwargs):
        try:
            id = request.POST['id']
            tr_id = request.POST['tr_id']
            tr_date = request.POST['tr_date']
            tr_crc = request.POST['tr_crc']
            tr_amount = request.POST['tr_amount']
            tr_paid = request.POST['tr_paid']
            tr_desc = request.POST['tr_desc']
            tr_status = request.POST['tr_status']
            tr_error = request.POST['tr_error']
            tr_email = request.POST['tr_email']
            md5sum = request.POST['md5sum']
        except KeyError:
            logger.warning('Got malformed POST request: %s' % str(request.POST))
            return http.HttpResponseBadRequest('MALFORMED', content_type='text/plain')

        status = PaymentProcessor.online(get_ip_address(request), id, tr_id, tr_date, tr_crc, tr_amount, tr_paid,
                                         tr_desc, tr_status, tr_error, tr_email, md5sum)
        if status != u"TRUE":
            http.HttpResponseBadRequest(status)
        return http.HttpResponse(status, content_type='text/plain')


class SuccessView(DetailView):
    """
    This view just redirects to standard backend success link.
    """
    model = Payment

    def render_to_response(self, context, **response_kwargs):
        return http.HttpResponseRedirect(reverse('getpaid:success-fallback', kwargs={'pk': self.object.pk}))

    def post(self, *args, **kwargs):
        return self.get(*args, **kwargs)


class FailureView(DetailView):
    """
    This view just redirects to standard backend failure link.
    """
    model = Payment

    def render_to_response(self, context, **response_kwargs):
        return http.HttpResponseRedirect(reverse('getpaid:failure-fallback', kwargs={'pk': self.object.pk}))

    def post(self, *args, **kwargs):
        return self.get(*args, **kwargs)
