import logging
from django.core.urlresolvers import reverse
from django.http import HttpResponse, HttpResponseRedirect
from django.views.generic.base import View
from django.views.generic.detail import DetailView
from getpaid.backends.payu import PaymentProcessor
from getpaid.models import Payment

logger = logging.getLogger('getpaid.backends.payu')


class OnlineView(View):
    """
    This View answers on PayU online request that is acknowledge of payment
    status change.

    The most important logic of this view is delegated to ``PaymentProcessor.online()`` method
    """
    def post(self, request, *args, **kwargs):
        try:
            pos_id = request.POST['pos_id']
            session_id = request.POST['session_id']
            ts = request.POST['ts']
            sig = request.POST['sig']
        except KeyError:
            logger.warning('Got malformed POST request: %s' % str(request.POST))
            return HttpResponse('MALFORMED')

        status = PaymentProcessor.online(pos_id, session_id, ts, sig)
        return HttpResponse(status)


class SuccessView(DetailView):
    """
    This view just redirects to standard backend success link.
    """
    model = Payment

    def render_to_response(self, context, **response_kwargs):
        return HttpResponseRedirect(reverse('getpaid:success-fallback', kwargs={'pk': self.object.pk}))


class FailureView(DetailView):
    """
    This view just redirects to standard backend failure link.
    """
    model = Payment

    def render_to_response(self, context, **response_kwargs):
        logger.error("Payment %s failed on backend error %s" % (self.kwargs['pk'], self.kwargs['error']))
        return HttpResponseRedirect(reverse('getpaid:failure-fallback', kwargs={'pk': self.object.pk}))
