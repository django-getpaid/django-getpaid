import logging
from django.core.urlresolvers import reverse
from django.http import HttpResponse, Http404, HttpResponseRedirect
from django.views.generic import DetailView
from django.views.generic.base import View
from getpaid.backends.pagseguro import PaymentProcessor
from getpaid.models import Payment

logger = logging.getLogger('getpaid.backends.pagseguro')


class NotificationsView(View):
    """
    This view answers on Moip notifications requests.
    See http://labs.moip.com.br/referencia/nasp/

    The most important logic of this view is delegated to the
    ``PaymentProcessor.processNotification()`` method
    """
    def post(self, request, *args, **kwargs):
        try:

            request.encoding = 'ISO-8859-1'
            dados = dict((k, v.encode('ISO-8859-1')) for k, v in request.POST.items())
            
            logger.info('Retorno de pagamento por PagSeguro: ' + str({
                'dados': dados,
            }))

        except KeyError:
            logger.warning('Got malformed POST request: %s' % str(request.POST))
            raise Http404

        status = PaymentProcessor.process_notification(dados)
        return HttpResponse(status)

    def get(self, request, *args, **kwargs):
        return HttpResponse("ok")


class SuccessView(DetailView):
    """
    This view just redirects to standard backend success link.
    """
    model = Payment

    def render_to_response(self, context, **response_kwargs):
        return HttpResponseRedirect(reverse('getpaid-success-fallback', kwargs={'pk': self.object.pk}))
