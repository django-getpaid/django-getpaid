from enum import Enum

from django.utils.translation import pgettext_lazy


class FraudStatus(str, Enum):
    UNKNOWN = "unknown"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    CHECK = "check"

    @property
    def choices(self):
        return (
            (self.UNKNOWN, pgettext_lazy("fraud status", "unknown")),
            (self.ACCEPTED, pgettext_lazy("fraud status", "accepted")),
            (self.REJECTED, pgettext_lazy("fraud status", "rejected")),
            (self.CHECK, pgettext_lazy("fraud status", "needs manual verification")),
        )

    @property
    def CHOICES(self):
        """
        Backward compatibility with pre-Enum version.
        """
        return self.choices


class PaymentStatus(str, Enum):
    """
    Internal payment statuses.
    """

    NEW = "new"
    PREPARED = "prepared"
    PRE_AUTH = "pre-auth"
    IN_CHARGE = "charge_started"
    PARTIAL = "partially_paid"
    PAID = "paid"
    FAILED = "failed"
    REFUND_STARTED = "refund_started"
    REFUNDED = "refunded"

    @property
    def choices(self):
        return (
            (self.NEW, pgettext_lazy("payment status", "new")),
            (self.PREPARED, pgettext_lazy("payment status", "in progress")),
            (self.PRE_AUTH, pgettext_lazy("payment status", "pre-authed")),
            (self.IN_CHARGE, pgettext_lazy("payment status", "charge process started")),
            (self.PARTIAL, pgettext_lazy("payment status", "partially paid")),
            (self.PAID, pgettext_lazy("payment status", "paid")),
            (self.FAILED, pgettext_lazy("payment status", "failed")),
            (self.REFUND_STARTED, pgettext_lazy("payment status", "refund started")),
            (self.REFUNDED, pgettext_lazy("payment status", "refunded")),
        )

    @property
    def CHOICES(self):
        """
        Backward compatibility with pre-Enum version.
        """
        return self.choices
