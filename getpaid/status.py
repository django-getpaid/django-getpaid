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
    IN_PROGRESS = "in_progress"
    ACCEPTED = "accepted_for_proc"
    PAID = "paid"
    PARTIAL = "partially_paid"
    CANCELLED = "cancelled"
    FAILED = "failed"
    REFUNDED = "refunded"

    CHOICES = (
        (NEW, pgettext_lazy("payment status", "new")),
        (IN_PROGRESS, pgettext_lazy("payment status", "in progress")),
        (ACCEPTED, pgettext_lazy("payment status", "accepted for processing")),
        (PARTIAL, pgettext_lazy("payment status", "partially paid")),
        (PAID, pgettext_lazy("payment status", "paid")),
        (CANCELLED, pgettext_lazy("payment status", "cancelled")),
        (FAILED, pgettext_lazy("payment status", "failed")),
        (REFUNDED, pgettext_lazy("payment status", "refunded")),
    )

    values = [s[0] for s in CHOICES]
