"""Payment types and enums.

Re-export getpaid-core enums directly (no wrapper — core StrEnum members
are already string-comparable and iterable). Provide Django CHOICES tuples
as plain module-level constants.
"""

from django.utils.translation import pgettext_lazy
from getpaid_core.enums import (
    BackendMethod,
    ConfirmationMethod,
    FraudStatus,
    PaymentStatus,
)

# Also re-exported from getpaid_core for consumer convenience.
from getpaid_core.types import BuyerInfo, ItemInfo
from getpaid_core.types import ChargeResult as ChargeResponse

__all__ = [
    'BackendMethod',
    'BuyerInfo',
    'ChargeResponse',
    'ConfirmationMethod',
    'FraudStatus',
    'ItemInfo',
    'PaymentStatus',

    'RestfulResult',
]


# ---------------------------------------------------------------------------
# Django CHOICES constants
# ---------------------------------------------------------------------------

PAYMENT_STATUS_CHOICES = tuple(
    (member.value, label)
    for member, label in [
        (PaymentStatus.NEW, pgettext_lazy('payment status', 'new')),
        (PaymentStatus.PREPARED, pgettext_lazy('payment status', 'in progress')),
        (PaymentStatus.PRE_AUTH, pgettext_lazy('payment status', 'pre-authed')),
        (PaymentStatus.IN_CHARGE, pgettext_lazy('payment status', 'charge process started')),
        (PaymentStatus.PARTIAL, pgettext_lazy('payment status', 'partially paid')),
        (PaymentStatus.PAID, pgettext_lazy('payment status', 'paid')),
        (PaymentStatus.FAILED, pgettext_lazy('payment status', 'failed')),
        (PaymentStatus.REFUND_STARTED, pgettext_lazy('payment status', 'refund started')),
        (PaymentStatus.REFUNDED, pgettext_lazy('payment status', 'refunded')),
        (PaymentStatus.CANCELLED, pgettext_lazy('payment status', 'cancelled')),
    ]
)

FRAUD_STATUS_CHOICES = tuple(
    (member.value, label)
    for member, label in [
        (FraudStatus.UNKNOWN, pgettext_lazy('fraud status', 'unknown')),
        (FraudStatus.ACCEPTED, pgettext_lazy('fraud status', 'accepted')),
        (FraudStatus.REJECTED, pgettext_lazy('fraud status', 'rejected')),
        (FraudStatus.CHECK, pgettext_lazy('fraud status', 'needs manual verification')),
    ]
)


# ---------------------------------------------------------------------------
# TypedDicts (Django-specific)
# ---------------------------------------------------------------------------

from typing import Any, TypedDict

from django.http import HttpResponse


class FormField(TypedDict):
    name: str
    value: Any
    label: str | None
    widget: str
    help_text: str | None
    required: bool


class PaymentForm(TypedDict):
    fields: list[FormField]


class RestfulResult(TypedDict):
    status_code: int
    result: HttpResponse
    target_url: str | None
    form: PaymentForm | None
    message: str | bytes | None
