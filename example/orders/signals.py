import logging

from django.dispatch import receiver
from django_fsm.signals import post_transition

from getpaid import PaymentStatus

logger = logging.getLogger("getpaid_example")


@receiver(post_transition)
def payment_status_changed_listener(sender, instance, name, source, target, **kwargs):
    """
    You can do something when payment is accepted. Let's change order status.
    """
    logger.debug("payment_status_changed_listener, old=%s, new=%s", source, target)
    if target == PaymentStatus.PAID:
        instance.order.status = "P"
        instance.order.save()
