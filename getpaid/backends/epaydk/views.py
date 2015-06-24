import logging
from django.core.urlresolvers import reverse
from django.http import HttpResponse, HttpResponseRedirect,\
    HttpResponseNotAllowed, HttpResponseBadRequest
from django.views.generic.base import View
from django.utils.six.moves.urllib.parse import parse_qsl
from django.views.generic.detail import DetailView
from django.db.models.loading import get_model
from getpaid.backends.epaydk import PaymentProcessor
from .forms import EpaydkOnlineForm
from collections import OrderedDict


logger = logging.getLogger(__name__)


class OnlineView(View):
    """
    This View answers on Epay.dk online request that is acknowledge of payment
    status change.

    The most important logic of this view is delegated
    to ``PaymentProcessor.online()`` method.

    """
    def post(self, request):
        return HttpResponseNotAllowed('GET', '405 Method Not Allowed')

    def get(self, request, *args, **kwargs):
        form = EpaydkOnlineForm(request.GET)
        if form.is_valid():
            params_list = parse_qsl(request.META['QUERY_STRING'])
            params = OrderedDict()
            for field, _ in params_list:
                params[field] = form.cleaned_data[field]
            if PaymentProcessor.is_received_request_valid(params):
                status = PaymentProcessor.online(params)
                return HttpResponse(status)
            logger.warning("Received invalid request - wrong md5 hash!")
        logger.warning('Received invalid request from Epay.dk: %s',
                       request.GET)
        logger.debug("errors: %s", form.errors)
        return HttpResponseBadRequest('400 Bad Request')


class SuccessView(DetailView):
    """
    This view just redirects to standard backend success link.
    """

    def get_queryset(self):
        self.model = get_model('getpaid', 'Payment')
        return self.model._default_manager.all()

    def render_to_response(self, context, **response_kwargs):
        return HttpResponseRedirect(reverse('getpaid-success-fallback',
                                            kwargs={'pk': self.object.pk}))


class FailureView(DetailView):
    """
    This view just redirects to standard backend failure link.
    """

    def get_queryset(self):
        self.model = get_model('getpaid', 'Payment')
        return self.model._default_manager.all()

    def render_to_response(self, context, **response_kwargs):
        logger.error("Payment %s failed on backend error %s" % \
                     (self.kwargs['pk'], self.kwargs['error']))
        return HttpResponseRedirect(reverse('getpaid-failure-fallback',
                                            kwargs={'pk': self.object.pk}))
