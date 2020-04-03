import logging

from django.dispatch import receiver

from getpaid import PaymentStatus
from getpaid.signals import payment_status_changed

logger = logging.getLogger("getpaid_example")


@receiver(payment_status_changed)
def payment_status_changed_listener(sender, instance, old_status, new_status, **kwargs):
    """
    You can do something when payment is accepted. Let's change order status.
    """
    logger.debug(
        "payment_status_changed_listener, old=%s, new=%s", old_status, new_status
    )
    if new_status == PaymentStatus.PAID:
        instance.order.status = "P"
        instance.order.save()
