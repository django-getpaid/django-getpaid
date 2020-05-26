from decimal import Decimal
from enum import Enum
from typing import Any, List, Optional, Union

from django.http import HttpResponse
from django.utils.decorators import classproperty
from django.utils.translation import pgettext_lazy
from typing_extensions import TypedDict


class FraudStatus(str, Enum):
    UNKNOWN = "unknown"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    CHECK = "check"

    @classproperty
    def choices(cls):
        return (
            (cls.UNKNOWN.value, pgettext_lazy("fraud status", "unknown")),
            (cls.ACCEPTED.value, pgettext_lazy("fraud status", "accepted")),
            (cls.REJECTED.value, pgettext_lazy("fraud status", "rejected")),
            (cls.CHECK.value, pgettext_lazy("fraud status", "needs manual verification")),
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

    NEW = "new"
    PREPARED = "prepared"
    PRE_AUTH = "pre-auth"
    IN_CHARGE = "charge_started"
    PARTIAL = "partially_paid"
    PAID = "paid"
    FAILED = "failed"
    REFUND_STARTED = "refund_started"
    REFUNDED = "refunded"

    @classproperty
    def choices(cls):
        return (
            (cls.NEW.value, pgettext_lazy("payment status", "new")),
            (cls.PREPARED.value, pgettext_lazy("payment status", "in progress")),
            (cls.PRE_AUTH.value, pgettext_lazy("payment status", "pre-authed")),
            (cls.IN_CHARGE.value, pgettext_lazy("payment status", "charge process started")),
            (cls.PARTIAL.value, pgettext_lazy("payment status", "partially paid")),
            (cls.PAID.value, pgettext_lazy("payment status", "paid")),
            (cls.FAILED.value, pgettext_lazy("payment status", "failed")),
            (cls.REFUND_STARTED.value, pgettext_lazy("payment status", "refund started")),
            (cls.REFUNDED.value, pgettext_lazy("payment status", "refunded")),
        )

    @classproperty
    def CHOICES(cls):
        """
        Backward compatibility with pre-Enum version.
        """
        return cls.choices


class BackendMethod(str, Enum):
    GET = "GET"
    POST = "POST"
    REST = "REST"


class ConfirmationMethod(str, Enum):
    PUSH = "PUSH"
    PULL = "PULL"


class GetpaidInternalResponse(TypedDict):
    raw_response: Any
    exception: Optional[Exception]


class ChargeResponse(GetpaidInternalResponse):
    amount_charged: Optional[Decimal]
    success: Optional[bool]
    async_call: Optional[bool]


class PaymentStatusResponse(GetpaidInternalResponse):
    amount: Optional[Decimal]
    callback: Optional[str]
    callback_result: Optional[Any]
    saved: Optional[bool]


class ItemInfo(TypedDict):
    name: str
    quantity: int
    unit_price: Decimal


class BuyerInfo(TypedDict):
    email: str
    first_name: Optional[str]
    last_name: Optional[str]
    phone: Optional[Union[str, int]]


class FormField(TypedDict):
    name: str
    value: Any
    label: Optional[str]
    widget: str
    help_text: Optional[str]
    required: bool


class PaymentForm(TypedDict):
    fields: List[FormField]


class RestfulResult(TypedDict):
    status_code: int
    result: HttpResponse
    target_url: Optional[str]
    form: Optional[PaymentForm]
    message: Optional[Union[str, bytes]]
