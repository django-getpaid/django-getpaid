import logging
import uuid
from decimal import Decimal
from importlib import import_module
from typing import cast

import swapper
from django import forms
from django.conf import settings as django_settings
from django.db import models
from django.db.models import Q
from django.db.transaction import atomic
from django.forms import BaseForm
from django.http import HttpRequest, HttpResponse
from django.shortcuts import resolve_url
from django.utils.translation import gettext_lazy as _
from django.views import View
from getpaid_core.enums import FraudEvent
from getpaid_core.fsm import apply_payment_update
from getpaid_core.protocols import Payment as CorePaymentProtocol
from getpaid_core.types import PaymentUpdate

from getpaid.exceptions import ChargeFailure
from getpaid.runtime import (
    cancel_payment_refund,
    charge_payment,
    fetch_and_update_payment_status,
    fetch_payment_status,
    prepare_payment,
    release_payment_lock,
    start_payment_refund,
)
from getpaid.types import (
    BuyerInfo,
    ChargeResponse,
    ItemInfo,
    RestfulResult,
)
from getpaid.types import FraudStatus as fs
from getpaid.types import PaymentStatus as ps

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
        if self.payments.exclude(status=ps.FAILED).exists():  # ty: ignore[unresolved-attribute]
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
        choices=ps.choices,
        default=ps.NEW,
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
        db_index=True,
        default='',
        unique=True,
    )
    description = models.CharField(
        _('description'), max_length=128, blank=True, default=''
    )
    fraud_status = models.CharField(
        _('fraud status'),
        max_length=20,
        choices=fs.choices,
        default=fs.UNKNOWN,
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
                condition=~Q(status=ps.FAILED),
                name='getpaid_unique_non_failed_payment_per_order',
            ),
        ]

    def __str__(self):
        return f'Payment #{self.id}'

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
        # Circular import workaround: registry imports processor
        from getpaid.registry import registry

        backend_key = str(self.backend)
        if self.backend in registry:
            processor_class = registry[self.backend]
            processor_config = _resolve_processor_config(
                processor_class,
                backend_key,
                aliases=registry.get_aliases(backend_key),
            )
        else:
            # last resort if backend removed from INSTALLED_APPS
            module = import_module(backend_key)
            processor_class = module.PaymentProcessor
            processor_config = _resolve_processor_config(
                processor_class,
                backend_key,
                aliases={backend_key},
            )
        return processor_class(self, config=processor_config)

    def get_form(self, *args, **kwargs) -> BaseForm:
        """Interfaces processor's get_form."""
        return self._get_processor().get_form(*args, **kwargs)

    def get_template_names(self, view: View | None = None) -> list[str]:
        """Interfaces processor's get_template_names."""
        return self._get_processor().get_template_names(view=view)

    def handle_paywall_callback(
        self, request: HttpRequest, **kwargs
    ) -> HttpResponse:
        from getpaid.runtime import handle_callback_request

        return handle_callback_request(self, request, **kwargs)

    def fetch_status(self):
        return fetch_payment_status(self)

    @atomic
    def fetch_and_update_status(self):
        fetch_and_update_payment_status(self)
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

    # ---- Action helpers (delegate to processor) ----

    def prepare_transaction(
        self,
        request: HttpRequest | None = None,
        view: View | None = None,
        **kwargs,
    ) -> HttpResponse:
        return prepare_payment(self, request=request, view=view, **kwargs)

    def prepare_transaction_for_rest(
        self,
        request: HttpRequest | None = None,
        view: View | None = None,
        **kwargs,
    ) -> RestfulResult:
        result = self.prepare_transaction(request=request, view=view, **kwargs)
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
        amount_to_charge = amount
        if amount_to_charge is None:
            amount_to_charge = self.amount_locked
        if amount_to_charge > self.amount_locked:
            raise ValueError('Cannot charge more than locked value.')
        result = charge_payment(self, amount=amount_to_charge, **kwargs)
        if not result.success:
            raise ChargeFailure(
                'Error occurred while trying to charge locked amount.'
            )
        return result

    @atomic
    def release_lock(self, **kwargs):
        return release_payment_lock(self, **kwargs)

    @atomic
    def start_refund(
        self,
        amount: Decimal | float | int | None = None,
        **kwargs,
    ):
        refund_amount = Decimal(str(amount)) if amount is not None else None
        return start_payment_refund(self, amount=refund_amount, **kwargs)

    @atomic
    def cancel_refund(self, **kwargs):
        return cancel_payment_refund(self, **kwargs)


def _resolve_processor_config(
    processor_class,
    backend_key: str,
    *,
    aliases: set[str],
) -> dict:
    """Resolve backend settings for both Django and core processors."""
    backend_settings = getattr(
        django_settings,
        'GETPAID_BACKEND_SETTINGS',
        {},
    )
    slug = getattr(processor_class, 'slug', '')
    class_module = processor_class.__module__

    candidate_keys: list[str] = []
    if slug:
        candidate_keys.extend([slug, f'getpaid.backends.{slug}'])

    candidate_keys.extend(
        key
        for key in (
            backend_key,
            *sorted(aliases),
            class_module,
            f'{class_module}.{processor_class.__name__}',
        )
        if key not in candidate_keys
    )

    if class_module.endswith('.processor'):
        backend_module = class_module.rsplit('.', 1)[0]
        if backend_module not in candidate_keys:
            candidate_keys.append(backend_module)

    for key in candidate_keys:
        if key in backend_settings:
            return backend_settings[key]
    return {}
