from decimal import Decimal
from enum import Enum
from typing import Any, TypedDict

from django.http import HttpResponse
from django.utils.functional import classproperty
from django.utils.translation import pgettext_lazy


class FraudStatus(str, Enum):
    UNKNOWN = 'unknown'
    ACCEPTED = 'accepted'
    REJECTED = 'rejected'
    CHECK = 'check'

    @classproperty
    def choices(cls):
        return (
            (cls.UNKNOWN.value, pgettext_lazy('fraud status', 'unknown')),
            (cls.ACCEPTED.value, pgettext_lazy('fraud status', 'accepted')),
            (cls.REJECTED.value, pgettext_lazy('fraud status', 'rejected')),
            (
                cls.CHECK.value,
                pgettext_lazy('fraud status', 'needs manual verification'),
            ),
        )

    @classproperty
    def CHOICES(cls):
        """
        Backward compatibility with pre-Enum version.
        """
        return cls.choices


class PaymentStatus(str, Enum):
    """
    Internal payment statuses.
    """

    NEW = 'new'
    PREPARED = 'prepared'
    PRE_AUTH = 'pre-auth'
    IN_CHARGE = 'charge_started'
    PARTIAL = 'partially_paid'
    PAID = 'paid'
    FAILED = 'failed'
    REFUND_STARTED = 'refund_started'
    REFUNDED = 'refunded'

    @classproperty
    def choices(cls):
        return (
            (cls.NEW.value, pgettext_lazy('payment status', 'new')),
            (
                cls.PREPARED.value,
                pgettext_lazy('payment status', 'in progress'),
            ),
            (cls.PRE_AUTH.value, pgettext_lazy('payment status', 'pre-authed')),
            (
                cls.IN_CHARGE.value,
                pgettext_lazy('payment status', 'charge process started'),
            ),
            (
                cls.PARTIAL.value,
                pgettext_lazy('payment status', 'partially paid'),
            ),
            (cls.PAID.value, pgettext_lazy('payment status', 'paid')),
            (cls.FAILED.value, pgettext_lazy('payment status', 'failed')),
            (
                cls.REFUND_STARTED.value,
                pgettext_lazy('payment status', 'refund started'),
            ),
            (cls.REFUNDED.value, pgettext_lazy('payment status', 'refunded')),
        )

    @classproperty
    def CHOICES(cls):
        """
        Backward compatibility with pre-Enum version.
        """
        return cls.choices


class BackendMethod(str, Enum):
    GET = 'GET'
    POST = 'POST'
    REST = 'REST'


class ConfirmationMethod(str, Enum):
    PUSH = 'PUSH'
    PULL = 'PULL'


class GetpaidInternalResponse(TypedDict):
    raw_response: Any
    exception: Exception | None


class ChargeResponse(GetpaidInternalResponse):
    amount_charged: Decimal | None
    success: bool | None
    async_call: bool | None


class PaymentStatusResponse(GetpaidInternalResponse):
    amount: Decimal | None
    callback: str | None
    callback_result: Any | None
    saved: bool | None


class ItemInfo(TypedDict):
    name: str
    quantity: int
    unit_price: Decimal


class BuyerInfo(TypedDict):
    email: str
    first_name: str | None
    last_name: str | None
    phone: str | int | None


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
