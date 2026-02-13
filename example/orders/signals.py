import logging

from django.db.models.signals import post_save
from django.dispatch import receiver

from getpaid import PaymentStatus

logger = logging.getLogger('getpaid_example')


@receiver(post_save)
def payment_status_changed_listener(sender, instance, **kwargs):
    """Update order status when payment is completed."""
    # Only act on Payment models
    if not hasattr(instance, 'order') or not hasattr(instance, 'status'):
        return

    from getpaid.abstracts import AbstractPayment

    if not isinstance(instance, AbstractPayment):
        return

    if instance.status == PaymentStatus.PAID:
        logger.debug(
            'Payment %s is PAID, updating order status.',
            instance.id,
        )
        instance.order.status = 'P'
        instance.order.save()
