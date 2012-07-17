#import logging
#from celery import task
#from getpaid.backends.payu import PaymentProcessor
#from getpaid.models import Payments
#
#logger = logging.getLogger('getpaid.backends.payu')
#
#@task()
#def get_payment_status(payment_id):
#    pass
#    try:
#        payment = Payment.objects.get(pk=int(payment_id))
#    except Payments.DoesNotExist:
#        logger.error('Payment does not exist pk=%d' % payment_id)
#        return
#    processor = PaymentProcessor(payment)
#    processor.get_payment_status()