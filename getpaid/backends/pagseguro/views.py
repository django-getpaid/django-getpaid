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

        request.encoding = 'ISO-8859-1'
        
        notification_code = request.POST.get('notificationCode','')[:]
        notification_type = request.POST.get('notificationType','')[:]
        
        dados = {
            'notificationCode': notification_code,
            'notificationType': notification_type,
        }

        logger.info('PagSeguro notificationCode: ' + str({
            'post': request.POST,
        }))

        if not notification_code:
            logger.warning('Got malformed POST request: %s' % str(request.POST))
            raise Http404
        
        try:
            status = PaymentProcessor.process_notification(dados)
            return HttpResponse("OK")
        except Exception as e:
            return HttpResponse("Unathorized", status=404)

    def get(self, request, *args, **kwargs):
        return HttpResponse("ok")


class SuccessView(DetailView):
    """
    This view just redirects to standard backend success link.
    """
    model = Payment

    def render_to_response(self, context, **response_kwargs):
        return HttpResponseRedirect(reverse('getpaid-success-fallback', kwargs={'pk': self.object.pk}))
