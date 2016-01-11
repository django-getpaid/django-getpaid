import logging
from celery.task.base import get_task_logger, task
from django.apps import apps


logger = logging.getLogger('getpaid.backends.payu')
task_logger = get_task_logger('getpaid.backends.payu')


@task(max_retries=50, default_retry_delay=2*60)
def get_payment_status_task(payment_id, session_id):
    Payment = apps.get_model('getpaid', 'Payment')
    try:
        payment = Payment.objects.get(pk=int(payment_id))
    except Payment.DoesNotExist:
        task_logger.error('Payment does not exist pk=%s', payment_id)
        return
    from getpaid.backends.payu import PaymentProcessor # Avoiding circular import
    processor = PaymentProcessor(payment)
    processor.get_payment_status(session_id)


@task(max_retries=50, default_retry_delay=2 * 60)
def accept_payment(payment_id, session_id):
    Payment = apps.get_model('getpaid', 'Payment')
    try:
        payment = Payment.objects.get(pk=int(payment_id))
    except Payment.DoesNotExist:
        task_logger.error('Payment does not exist pk=%s', payment_id)
        return

    from getpaid.backends.payu import PaymentProcessor # Avoiding circular import
    processor = PaymentProcessor(payment)
    processor.accept_payment(session_id)