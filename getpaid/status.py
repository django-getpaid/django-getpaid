from django.utils.translation import pgettext_lazy


class FraudStatus:
    UNKNOWN = "unknown"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    CHECK = "check"

    CHOICES = (
        (UNKNOWN, pgettext_lazy("fraud status", "unknown")),
        (ACCEPTED, pgettext_lazy("fraud status", "accepted")),
        (REJECTED, pgettext_lazy("fraud status", "rejected")),
        (CHECK, pgettext_lazy("fraud status", "check")),
    )

    values = [s[0] for s in CHOICES]


class PaymentStatus:
    """
    Internal payment statuses.
    """

    NEW = "new"
    PREPARED = "prepared"
    PRE_AUTH = "pre-auth"
    IN_CHARGE = "charge_started"
    PAID = "paid"
    PARTIAL = "partially_paid"
    FAILED = "failed"
    REFUND_STARTED = "refund_started"
    REFUNDED = "refunded"

    CHOICES = (
        (NEW, pgettext_lazy("payment status", "new")),
        (PREPARED, pgettext_lazy("payment status", "in progress")),
        (PRE_AUTH, pgettext_lazy("payment status", "accepted for processing")),
        (PARTIAL, pgettext_lazy("payment status", "partially paid")),
        (PAID, pgettext_lazy("payment status", "paid")),
        (FAILED, pgettext_lazy("payment status", "failed")),
        (REFUND_STARTED, pgettext_lazy("payment status", "refund started")),
        (REFUNDED, pgettext_lazy("payment status", "refunded")),
    )

    values = [s[0] for s in CHOICES]

    unmovable = (FAILED, CANCELLED, REFUNDED)

    # TODO: upgrade using django-fsm
