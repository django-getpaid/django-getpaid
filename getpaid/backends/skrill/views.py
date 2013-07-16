import logging
from django.core.urlresolvers import reverse
from django.http import HttpResponse, HttpResponseRedirect
from django.views.generic.base import View
from django.views.generic.detail import DetailView
from getpaid.backends.skrill import PaymentProcessor
from getpaid.models import Payment

logger = logging.getLogger('getpaid.backends.skrill')

class OnlineView(View):
    """
    This View answers on Skrill's online request that is acknowledge of payment
    status change.

    The most important logic of this view is delegated to ``PaymentProcessor.online()`` method
    """
    def post(self, request, *args, **kwargs):
        logger.debug("received post from skrill: %s" % str(dict(request.POST.copy())) )
        try:
            merchant_id = request.POST['merchant_id']
            transaction_id = request.POST['transaction_id']
            mb_transaction_id = request.POST['mb_transaction_id']
            mb_amount = request.POST['mb_amount']
            mb_currency = request.POST['mb_currency']
            amount = request.POST['amount']
            currency = request.POST['currency']
            status = request.POST['status']
            sig = request.POST['md5sig']
            pay_from_email = request.POST['pay_from_email']
        except KeyError:
            logger.warning('Got malformed POST request: %s' % str(request.POST))
            return HttpResponse('MALFORMED')

        status = PaymentProcessor.online(merchant_id, transaction_id, mb_amount, amount, mb_currency, currency,  status, sig, mb_transaction_id, pay_from_email)
        return HttpResponse(status)

class SuccessView(DetailView):
    """
    This view just redirects to standard backend success link.
    """
    model = Payment

    def render_to_response(self, context, **response_kwargs):
        return HttpResponseRedirect(reverse('getpaid-success-fallback', kwargs={'pk': self.object.pk}))

class FailureView(DetailView):
    """
    This view just redirects to standard backend failure link.
    """
    model = Payment

    def render_to_response(self, context, **response_kwargs):
        logger.error("Payment %s failed on backend error %s" % (self.kwargs['pk'], self.kwargs['error']))
        return HttpResponseRedirect(reverse('getpaid-failure-fallback', kwargs={'pk': self.object.pk}))
