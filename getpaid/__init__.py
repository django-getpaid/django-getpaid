from django.utils.translation import pgettext_lazy

__version__ = "2.0.0-rc.2"
default_app_config = "getpaid.apps.GetpaidConfig"


class PaymentStatus:
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
