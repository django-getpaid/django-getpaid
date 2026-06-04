"""Payment types and enums.

Django-specific enum wrappers with choices property.
Inherits values from getpaid-core to prevent enum drift.
Re-exports core types unchanged.
"""

from decimal import Decimal
from typing import Any, TypedDict

from django.http import HttpResponse
from django.utils.functional import classproperty
from django.utils.translation import pgettext_lazy
from getpaid_core.enums import (
    BackendMethod,
    ConfirmationMethod,
)
from getpaid_core.enums import FraudStatus as _CoreFraudStatus
from getpaid_core.enums import PaymentStatus as _CorePaymentStatus
from getpaid_core.types import BuyerInfo, ChargeResponse, ItemInfo

# Re-export core types directly
__all__ = [
    'BackendMethod',
    'BuyerInfo',
    'ChargeResponse',
    'ConfirmationMethod',
    'FraudStatus',
    'ItemInfo',
    'PaymentStatus',
    'PaymentStatusResponse',
    'RestfulResult',
]


class PaymentStatus(_CorePaymentStatus):
    """Payment status with Django choices support.

    Inherits all values from getpaid-core's PaymentStatus,
    eliminating enum value drift. Adds .choices and .CHOICES
    classproperties for Django model fields.
    """

    @classproperty
    def choices(cls):
        return (
            (cls.NEW.value, pgettext_lazy('payment status', 'new')),
            (
                cls.PREPARED.value,
                pgettext_lazy('payment status', 'in progress'),
            ),
            (
                cls.PRE_AUTH.value,
                pgettext_lazy('payment status', 'pre-authed'),
            ),
            (
                cls.IN_CHARGE.value,
                pgettext_lazy('payment status', 'charge process started'),
            ),
            (
                cls.PARTIAL.value,
                pgettext_lazy('payment status', 'partially paid'),
            ),
            (cls.PAID.value, pgettext_lazy('payment status', 'paid')),
            (
                cls.FAILED.value,
                pgettext_lazy('payment status', 'failed'),
            ),
            (
                cls.REFUND_STARTED.value,
                pgettext_lazy('payment status', 'refund started'),
            ),
            (
                cls.REFUNDED.value,
                pgettext_lazy('payment status', 'refunded'),
            ),
        )

    @classproperty
    def CHOICES(cls):
        """Backward compatibility."""
        return cls.choices


class FraudStatus(_CoreFraudStatus):
    """Fraud status with Django choices support.

    Inherits all values from getpaid-core's FraudStatus,
    eliminating enum value drift. Adds .choices and .CHOICES
    classproperties for Django model fields.
    """

    @classproperty
    def choices(cls):
        return (
            (
                cls.UNKNOWN.value,
                pgettext_lazy('fraud status', 'unknown'),
            ),
            (
                cls.ACCEPTED.value,
                pgettext_lazy('fraud status', 'accepted'),
            ),
            (
                cls.REJECTED.value,
                pgettext_lazy('fraud status', 'rejected'),
            ),
            (
                cls.CHECK.value,
                pgettext_lazy('fraud status', 'needs manual verification'),
            ),
        )

    @classproperty
    def CHOICES(cls):
        """Backward compatibility."""
        return cls.choices


class GetpaidInternalResponse(TypedDict):
    raw_response: Any
    exception: Exception | None


class PaymentStatusResponse(GetpaidInternalResponse):
    amount: Decimal | None
    callback: str | None
    callback_result: Any | None
    saved: bool | None


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
