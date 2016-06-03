import logging
from django.core.urlresolvers import reverse
from django.http import HttpResponse, HttpResponseRedirect
from django.views.generic.base import View
from django.views.generic.detail import DetailView
from getpaid.backends.dotpay import PaymentProcessor
from getpaid.models import Payment

logger = logging.getLogger('getpaid.backends.dotpay')


class OnlineView(View):
    """
    This View answers on PayU online request that is acknowledge of payment
    status change.

    The most important logic of this view is delegated to ``PaymentProcessor.online()`` method
    """
    def post(self, request, *args, **kwargs):

        try:
            params = {
                'id': request.POST['id'],
                'status': request.POST['status'],
                'control': request.POST['control'],
                't_id': request.POST['t_id'],
                'amount': request.POST['amount'],
                'email': request.POST['email'],

                'orginal_amount': request.POST['orginal_amount'],
                't_status': request.POST['t_status'],
                'md5': request.POST['md5'],


                'service': request.POST.get('service', ''),
                'code': request.POST.get('code', ''),
                'username': request.POST.get('username', ''),
                'password': request.POST.get('password', ''),

            }
        except KeyError:
            logger.warning('Got malformed POST request: %s' % str(request.POST))
            return HttpResponse('MALFORMED')

        status = PaymentProcessor.online(params, ip=request.META['REMOTE_ADDR'])
        return HttpResponse(status)


class ReturnView(DetailView):
    """
    This view just redirects to standard backend success or failure link.
    """
    model = Payment

    def post(self, request, *args, **kwargs):
        return self.get(request, *args, **kwargs)

    def render_to_response(self, context, **response_kwargs):
        if self.request.POST['status'] == 'OK':
            return HttpResponseRedirect(reverse('getpaid:success-fallback', kwargs={'pk': self.object.pk}))
        else:
            return HttpResponseRedirect(reverse('getpaid:failure-fallback', kwargs={'pk': self.object.pk}))
