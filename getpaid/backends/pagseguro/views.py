import logging
from django.http import HttpResponse
from django.views.generic.base import View
from getpaid.backends.pagseguro import PaymentProcessor
from getpaid.models import Payment

logger = logging.getLogger('getpaid.backends.pagseguro')



class NotificationsView(View):
    """
    This view answers on PagSeguro notifications requests.
    See https://pagseguro.uol.com.br/v2/guia-de-integracao/api-de-notificacoes.html#rmcl

    The most important logic of this view is delegated to the
    ``PaymentProcessor.processNotification()`` method
    """
    def post(self, request, *args, **kwargs):
        try:
            notification_code = request.POST['notificationCode']
            notification_type = request.POST['notificationType']
        except KeyError:
            logger.warning('Got malformed POST request: %s' % str(request.POST))
            return HttpResponse('MALFORMED')

        status = PaymentProcessor.process_notification(notification_code, notification_type)
        return HttpResponse(status)