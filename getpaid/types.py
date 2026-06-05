"""Payment types and enums.

Django-specific enum wrappers with choices property.
Composes getpaid-core enums to avoid Python 3.14's enum subclassing restriction.
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
    FraudStatus as _CoreFraudStatus,
    PaymentStatus as _CorePaymentStatus,
)
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


class _EnumWrapperMeta(type):
    """Metaclass that delegates class-level attribute access to a core enum.

    Enables `PaymentStatus.NEW` style access by intercepting attribute lookups
    on the wrapper class and forwarding them to the composed core enum.
    """

    _core: type  # Will be set to the core enum class

    def __getattr__(cls, name):
        attr = getattr(cls._core, name)
        if isinstance(attr, cls._core):
            wrapper = object.__new__(cls)
            wrapper._core_value = attr
            return wrapper
        return attr

    def __getitem__(cls, key):
        return cls._core[key]

    def __iter__(cls):
        return iter(cls._core)

    def __len__(cls):
        return len(list(cls._core))

    def __str__(cls):
        return str(cls._core)


class _EnumWrapper:
    """Mixin providing instance-level behavior for enum wrappers."""

    _core_value: Any  # Set by metaclass on delegated access

    def __new__(cls, value):
        return cls._core(value)

    def __eq__(self, other):
        if isinstance(other, self._core):
            return self._core_value == other
        if isinstance(other, str):
            return self._core_value.value == other
        if type(self) is type(other):
            return self._core_value == other._core_value
        return NotImplemented

    def __hash__(self):
        return hash(self._core_value)

    def __str__(self):
        return str(self._core_value)

    def __repr__(self):
        return f'<{type(self).__name__}.{self._core_value.name}: {self._core_value.value!r}>'


# ============================================================================
# PaymentStatus wrapper
# ============================================================================

class PaymentStatus(_EnumWrapper, metaclass=_EnumWrapperMeta):
    """Payment status wrapper with Django choices support.

    Composes getpaid-core's PaymentStatus to avoid Python 3.14's
    enum subclassing restriction (EnumType._check_for_existing_members_).
    Provides .choices and .CHOICES classproperties for Django model fields.
    All core members are accessible by name and support equality comparison.
    """

    _core = _CorePaymentStatus

    @classproperty
    def choices(cls):
        return (
            (cls._core.NEW.value, pgettext_lazy('payment status', 'new')),
            (
                cls._core.PREPARED.value,
                pgettext_lazy('payment status', 'in progress'),
            ),
            (
                cls._core.PRE_AUTH.value,
                pgettext_lazy('payment status', 'pre-authed'),
            ),
            (
                cls._core.IN_CHARGE.value,
                pgettext_lazy('payment status', 'charge process started'),
            ),
            (
                cls._core.PARTIAL.value,
                pgettext_lazy('payment status', 'partially paid'),
            ),
            (cls._core.PAID.value, pgettext_lazy('payment status', 'paid')),
            (
                cls._core.FAILED.value,
                pgettext_lazy('payment status', 'failed'),
            ),
            (
                cls._core.REFUND_STARTED.value,
                pgettext_lazy('payment status', 'refund started'),
            ),
            (
                cls._core.REFUNDED.value,
                pgettext_lazy('payment status', 'refunded'),
            ),
        )

    @classproperty
    def CHOICES(cls):
        """Backward compatibility."""
        return cls.choices


# ============================================================================
# FraudStatus wrapper
# ============================================================================

class FraudStatus(_EnumWrapper, metaclass=_EnumWrapperMeta):
    """Fraud status wrapper with Django choices support.

    Composes getpaid-core's FraudStatus to avoid Python 3.14's
    enum subclassing restriction. Provides .choices and .CHOICES
    classproperties for Django model fields.
    All core members are accessible by name and support equality comparison.
    """

    _core = _CoreFraudStatus

    @classproperty
    def choices(cls):
        return (
            (
                cls._core.UNKNOWN.value,
                pgettext_lazy('fraud status', 'unknown'),
            ),
            (
                cls._core.ACCEPTED.value,
                pgettext_lazy('fraud status', 'accepted'),
            ),
            (
                cls._core.REJECTED.value,
                pgettext_lazy('fraud status', 'rejected'),
            ),
            (
                cls._core.CHECK.value,
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
