import logging
from celery.task.base import task
from django.apps import apps

logger = logging.getLogger('getpaid.backends.przelewy24')


@task
def get_payment_status_task(payment_id, p24_session_id, p24_order_id, p24_kwota):
    Payment = apps.get_model('getpaid', 'Payment')
    try:
        payment = Payment.objects.get(pk=int(payment_id))
    except Payment.DoesNotExist:
        logger.error('Payment does not exist pk=%d' % payment_id)
        return

    from getpaid.backends.przelewy24 import PaymentProcessor  # Avoiding circular import
    processor = PaymentProcessor(payment)
    processor.get_payment_status(p24_session_id, p24_order_id, p24_kwota)
