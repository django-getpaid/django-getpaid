import logging
from celery import task
from django.db.models.loading import get_model


logger = logging.getLogger('getpaid.backends.payu')

Payment = get_model('getpaid', 'Payment')

@task()
def get_payment_status_task(payment_id, session_id):
    try:
        payment = Payment.objects.get(pk=int(payment_id))
    except Payment.DoesNotExist:
        logger.error('Payment does not exist pk=%d' % payment_id)
        return
    # Avoiding circular import?
    from getpaid.backends.payu import PaymentProcessor
    processor = PaymentProcessor(payment)
    processor.get_payment_status(session_id)