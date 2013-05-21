import logging
from celery.task.base import task
from django.db.models.loading import get_model


logger = logging.getLogger('getpaid.backends.payu')


@task
def get_payment_status_task(payment_id, session_id):
    Payment = get_model('getpaid', 'Payment')
    try:
        payment = Payment.objects.get(pk=int(payment_id))
    except Payment.DoesNotExist:
        logger.error('Payment does not exist pk=%d' % payment_id)
        return

    from getpaid.backends.payu import PaymentProcessor # Avoiding circular import
    processor = PaymentProcessor(payment)
    processor.get_payment_status(session_id)