import logging
import uuid
from decimal import Decimal
from typing import cast

import swapper
from django import forms
from django.db import models
from django.db.models import Q
from django.db.transaction import atomic
from django.forms import BaseForm
from django.http import HttpRequest, HttpResponse
from django.shortcuts import resolve_url
from django.utils.translation import gettext_lazy as _
from django.views import View
from getpaid_core.enums import (
    FraudEvent,
    FraudStatus,
    PaymentStatus,
)
from getpaid_core.fsm import apply_payment_update
from getpaid_core.protocols import Payment as CorePaymentProtocol
from getpaid_core.types import PaymentUpdate

from getpaid.flow_adapter import (
    DjangoPaymentFlowAdapter,
    _get_processor,
    prepare_transaction,
)
from getpaid.repository import DjangoPaymentRepository
from getpaid.types import (
    FRAUD_STATUS_CHOICES,
    PAYMENT_STATUS_CHOICES,
    BuyerInfo,
    ChargeResponse,
    ItemInfo,
    RestfulResult,
)

logger = logging.getLogger(__name__)


class AbstractOrder(models.Model):
    """Base class for Order models.

    Consider using UUIDField as primary or secondary key to hide volume.
    """

    class Meta:
        abstract = True

    def get_return_url(
        self,
        *args,
        success: bool | None = None,
        **kwargs,
    ) -> str:
        """Return URL after payment completion.

        Override to customize. Default: get_absolute_url().
        """
        return self.get_absolute_url()

    def get_absolute_url(self) -> str:
        raise NotImplementedError

    def is_ready_for_payment(self) -> bool:
        """Validate order is ready for payment.

        Override for custom validation. Raise ValidationError
        for verbose error messages.
        """
        if self.payments.exclude(status=PaymentStatus.FAILED).exists():  # ty: ignore[unresolved-attribute]
            raise forms.ValidationError(
                _('Non-failed Payments exist for this Order.')
            )
        return True

    def get_items(self) -> list[ItemInfo]:
        """Return list of items for the payment."""
        return [
            {
                'name': self.get_description(),
                'quantity': 1,
                'unit_price': self.get_total_amount(),
            }
        ]

    def get_total_amount(self) -> Decimal:
        raise NotImplementedError

    def get_currency(self) -> str:
        field_name = 'currency'
        return cast('str', getattr(self, field_name))

    def get_buyer_info(self) -> BuyerInfo:
        raise NotImplementedError

    def get_description(self) -> str:
        raise NotImplementedError


class AbstractPayment(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    order = models.ForeignKey(
        swapper.get_model_name('getpaid', 'Order'),
        verbose_name=_('order'),
        on_delete=models.CASCADE,
        related_name='payments',
    )
    amount_required = models.DecimalField(
        _('amount required'),
        decimal_places=2,
        max_digits=20,
        help_text=_(
            'Amount required to fulfill the payment; '
            'in selected currency, normal notation'
        ),
    )
    currency = models.CharField(_('currency'), max_length=3)
    status = models.CharField(
        _('status'),
        max_length=50,
        choices=PAYMENT_STATUS_CHOICES,
        default=PaymentStatus.NEW,
        db_index=True,
    )
    backend = models.CharField(_('backend'), max_length=100, db_index=True)
    created_on = models.DateTimeField(
        _('created on'), auto_now_add=True, db_index=True
    )
    last_payment_on = models.DateTimeField(
        _('paid on'),
        blank=True,
        null=True,
        default=None,
        db_index=True,
    )
    amount_locked = models.DecimalField(
        _('amount locked'),
        decimal_places=2,
        max_digits=20,
        default=0,
        help_text=_('Amount locked with this payment, ready to charge.'),
    )
    amount_paid = models.DecimalField(
        _('amount paid'),
        decimal_places=2,
        max_digits=20,
        default=0,
        help_text=_('Amount actually paid.'),
    )
    refunded_on = models.DateTimeField(
        _('refunded on'),
        blank=True,
        null=True,
        default=None,
        db_index=True,
    )
    amount_refunded = models.DecimalField(
        _('amount refunded'),
        decimal_places=2,
        max_digits=20,
        default=0,
    )
    external_id = models.CharField(
        _('external id'),
        max_length=64,
        blank=True,
        null=True,
        db_index=True,
        default=None,
        unique=True,
    )
    description = models.CharField(
        _('description'), max_length=128, blank=True, default=''
    )
    fraud_status = models.CharField(
        _('fraud status'),
        max_length=20,
        choices=FRAUD_STATUS_CHOICES,
        default=FraudStatus.UNKNOWN,
        db_index=True,
    )
    fraud_message = models.TextField(_('fraud message'), blank=True)
    provider_data = models.JSONField(
        _('provider data'), default=dict, blank=True
    )

    class Meta:
        abstract = True
        ordering = ['-created_on']
        verbose_name = _('Payment')
        verbose_name_plural = _('Payments')
        constraints = [
            models.UniqueConstraint(
                fields=['order'],
                condition=~Q(status=PaymentStatus.FAILED),
                name='getpaid_unique_non_failed_payment_per_order',
            ),
        ]

    def __str__(self):
        return f'Payment #{self.id}'

    def clean(self):
        super().clean()
        self._normalize_external_id()

    def save(self, *args, **kwargs):
        self._normalize_external_id()
        super().save(*args, **kwargs)

    def _normalize_external_id(self) -> None:
        """Normalize empty external_id to None.

        external_id is unique; empty strings would collide, while
        multiple NULLs are allowed.
        """
        if not self.external_id:
            self.external_id = None

    # ---- Properties ----

    @property
    def fully_paid(self) -> bool:
        return self.amount_paid >= self.amount_required

    def is_fully_paid(self) -> bool:
        return self.amount_paid >= self.amount_required

    def is_fully_refunded(self) -> bool:
        return (
            self.amount_refunded > 0
            and self.amount_refunded >= self.amount_paid
        )

    def flag_as_fraud(self, message=''):
        payment = cast(CorePaymentProtocol, self)
        apply_payment_update(
            payment,
            PaymentUpdate(
                fraud_event=FraudEvent.REJECT,
                fraud_message=message,
            ),
        )

    def flag_as_legit(self, message=''):
        payment = cast(CorePaymentProtocol, self)
        apply_payment_update(
            payment,
            PaymentUpdate(
                fraud_event=FraudEvent.ACCEPT,
                fraud_message=message,
            ),
        )

    def flag_for_check(self, message=''):
        payment = cast(CorePaymentProtocol, self)
        apply_payment_update(
            payment,
            PaymentUpdate(
                fraud_event=FraudEvent.REVIEW,
                fraud_message=message,
            ),
        )

    # ---- Delegation helpers ----

    def get_unique_id(self) -> str:
        """Return unique identifier for this payment."""
        return str(self.id)

    def get_items(self) -> list[ItemInfo]:
        """Relay to order's get_items()."""
        return self.order.get_items()  # ty: ignore[possibly-missing-attribute]

    def get_buyer_info(self) -> BuyerInfo:
        return self.order.get_buyer_info()  # ty: ignore[possibly-missing-attribute]

    def _get_processor(self):
        """Get processor instance for this payment's backend."""
        return _get_processor(self, type(self))

    def get_form(self, *args, **kwargs) -> BaseForm:
        """Interfaces processor's get_form."""
        return self._get_processor().get_form(*args, **kwargs)

    def get_template_names(self, view: View | None = None) -> list[str]:
        """Interfaces processor's get_template_names."""
        return self._get_processor().get_template_names(view=view)

    def handle_paywall_callback(
        self, request: HttpRequest, **kwargs
    ) -> HttpResponse:
        return _handle_paywall_callback(self, request, **kwargs)

    def fetch_status(self):
        return DjangoPaymentFlowAdapter(self, type(self)).fetch_status()

    @atomic
    def fetch_and_update_status(self):
        # Row-level lock so concurrent status updates (e.g. a webhook
        # arriving while a PULL status check runs) are serialized.
        if self.pk is not None:
            list(
                type(self)
                ._default_manager.select_for_update()
                .filter(pk=self.pk)
            )
        self.fetch_status()
        return self

    def get_return_redirect_url(
        self, request: HttpRequest, success: bool
    ) -> str:
        """Determine redirect URL after payment."""
        processor = self._get_processor()
        if success:
            url = processor.get_setting('SUCCESS_URL')
        else:
            url = processor.get_setting('FAILURE_URL')

        if url is not None:
            kwargs = self.get_return_redirect_kwargs(request, success)
            return resolve_url(url, **kwargs)
        return resolve_url(self.order.get_return_url(self, success=success))  # ty: ignore[possibly-missing-attribute]

    def get_return_redirect_kwargs(
        self, request: HttpRequest, success: bool
    ) -> dict:
        return {'pk': self.id}

    # ---- Action helpers ----

    def prepare_transaction(
        self,
        request: HttpRequest | None = None,
        view: View | None = None,
        **kwargs,
    ) -> HttpResponse:
        return prepare_transaction(
            self, request=request, view=view, **kwargs
        )

    def prepare_transaction_for_rest(
        self,
        request: HttpRequest | None = None,
        view: View | None = None,
        **kwargs,
    ) -> RestfulResult:
        result = self.prepare_transaction(
            request=request, view=view, **kwargs
        )
        data = {'status_code': result.status_code, 'result': result}
        if result.status_code == 200:
            ctx = getattr(result, 'context_data', None)
            if ctx is None:
                data['message'] = 'Response has no context_data'
                return data
            data['target_url'] = ctx['paywall_url']
            data['form'] = {
                'fields': [
                    {
                        'name': name,
                        'value': field.initial,
                        'label': field.label or name,
                        'widget': field.widget.__class__.__name__,
                        'help_text': field.help_text,
                        'required': field.required,
                    }
                    for name, field in ctx['form'].fields.items()
                ],
            }
        elif result.status_code == 302:
            data['target_url'] = result.url  # ty: ignore[unresolved-attribute]
        else:
            data['message'] = result.content
        return data  # ty: ignore[invalid-return-type]

    @atomic
    def charge(
        self,
        amount: Decimal | float | int | None = None,
        **kwargs,
    ) -> ChargeResponse:
        return DjangoPaymentFlowAdapter(self, type(self)).charge(
            amount=Decimal(str(amount)) if amount is not None else None,
            **kwargs,
        )

    @atomic
    def release_lock(self, **kwargs):
        return DjangoPaymentFlowAdapter(self, type(self)).release_lock(
            **kwargs
        )

    @atomic
    def start_refund(
        self,
        amount: Decimal | float | int | None = None,
        **kwargs,
    ):
        return DjangoPaymentFlowAdapter(self, type(self)).start_refund(
            amount=Decimal(str(amount)) if amount is not None else None,
            **kwargs,
        )

    @atomic
    def cancel_refund(self, **kwargs):
        return DjangoPaymentFlowAdapter(self, type(self)).cancel_refund(
            **kwargs
        )


def _handle_paywall_callback(payment, request, **kwargs):
    """Handle paywall callback via core async path."""
    from getpaid.adapters import adapt_callback_request
    from getpaid.bridge import bridge

    processor = kwargs.pop('processor', None) or _get_processor(
        payment, type(payment)
    )
    data, headers, raw_body = adapt_callback_request(request)
    bridge.call_verify_callback(
        processor, data, headers, raw_body, request, **kwargs
    )
    update = bridge.call(
        processor,
        processor.handle_callback,
        data,
        headers,
        raw_body=raw_body,
        **kwargs,
    )
    if isinstance(update, HttpResponse):
        return update
    if update is not None:
        apply_payment_update(payment, update)
        DjangoPaymentRepository(type(payment))._save(payment)
    return HttpResponse(b'OK')
