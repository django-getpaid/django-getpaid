"""Abstract models for django-getpaid v3.

Models are plain Django models. FSM transitions are NOT defined on the model.
Instead, use getpaid_core.fsm.create_payment_machine(payment) to attach
transition triggers at runtime.
"""

import logging
import uuid
from decimal import Decimal
from importlib import import_module

import swapper
from django import forms
from django.db import models
from django.db.transaction import atomic
from django.forms import BaseForm
from django.http import HttpRequest, HttpResponse
from django.shortcuts import resolve_url
from django.utils.translation import gettext_lazy as _
from django.views import View
from getpaid_core.fsm import (
    ALLOWED_CALLBACKS,
    create_payment_machine,
)

from getpaid.exceptions import ChargeFailure
from getpaid.types import (
    BuyerInfo,
    ChargeResponse,
    ItemInfo,
    PaymentStatusResponse,
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
        if self.payments.exclude(status=ps.FAILED).exists():
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

    def get_buyer_info(self) -> BuyerInfo:
        raise NotImplementedError

    def get_description(self) -> str:
        raise NotImplementedError


class AbstractPayment(models.Model):
    """Abstract payment model.

    FSM transitions are NOT defined on the model. Instead, use
    getpaid_core.fsm.create_payment_machine(payment) to attach
    transition triggers at runtime.
    """

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

    class Meta:
        abstract = True
        ordering = ['-created_on']
        verbose_name = _('Payment')
        verbose_name_plural = _('Payments')

    def __str__(self):
        return f'Payment #{self.id}'

    # ---- Properties ----

    @property
    def fully_paid(self) -> bool:
        return self.amount_paid >= self.amount_required

    def is_fully_paid(self) -> bool:
        """Check if payment is fully paid. Used by core FSM guard."""
        return self.amount_paid >= self.amount_required

    def is_fully_refunded(self) -> bool:
        """Check if payment is fully refunded. Used by core FSM guard."""
        return (
            self.amount_refunded > 0
            and self.amount_refunded >= self.amount_paid
        )

    # ---- Delegation helpers ----

    def get_unique_id(self) -> str:
        """Return unique identifier for this payment."""
        return str(self.id)

    def get_items(self) -> list[ItemInfo]:
        """Relay to order's get_items()."""
        return self.order.get_items()

    def get_buyer_info(self) -> BuyerInfo:
        return self.order.get_buyer_info()

    def _get_processor(self):
        """Get processor instance for this payment's backend."""
        # Circular import workaround: registry imports processor
        from getpaid.registry import registry

        if self.backend in registry:
            processor_class = registry[self.backend]
        else:
            # last resort if backend removed from INSTALLED_APPS
            module = import_module(self.backend)
            processor_class = module.PaymentProcessor
        return processor_class(self)

    def get_form(self, *args, **kwargs) -> BaseForm:
        """Interfaces processor's get_form."""
        return self._get_processor().get_form(*args, **kwargs)

    def get_template_names(self, view: View | None = None) -> list[str]:
        """Interfaces processor's get_template_names."""
        return self._get_processor().get_template_names(view=view)

    def handle_paywall_callback(
        self, request: HttpRequest, **kwargs
    ) -> HttpResponse:
        """Interfaces processor's handle_paywall_callback."""
        return self._get_processor().handle_paywall_callback(request, **kwargs)

    def fetch_status(self) -> PaymentStatusResponse:
        """Interfaces processor's fetch_payment_status."""
        return self._get_processor().fetch_payment_status()

    @atomic
    def fetch_and_update_status(self) -> PaymentStatusResponse:
        """Used during PULL flow to fetch and update payment status."""
        status_report = self.fetch_status()
        callback_name = status_report.get('callback')
        if callback_name:
            if callback_name not in ALLOWED_CALLBACKS:
                logger.warning(
                    'Disallowed callback %r requested for payment %s.',
                    callback_name,
                    self.id,
                    extra={
                        'payment_id': self.id,
                        'payment_status': self.status,
                        'callback': callback_name,
                    },
                )
                status_report['exception'] = ValueError(
                    f'Disallowed callback: {callback_name!r}'
                )
                return status_report

            # Attach FSM and try the callback
            create_payment_machine(self)
            callback = getattr(self, callback_name, None)
            amount = status_report.get('amount', None)
            if callback is not None and self.may_trigger(callback_name):
                try:
                    status_report['callback_result'] = callback(amount=amount)
                    self.save()
                    status_report['saved'] = True
                except Exception as exc:
                    status_report['exception'] = exc
            else:
                logger.debug(
                    'Cannot run fetch+update callback %s.',
                    callback_name,
                    extra={
                        'payment_id': self.id,
                        'payment_status': self.status,
                        'callback': callback_name,
                    },
                )
        return status_report

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
        return resolve_url(self.order.get_return_url(self, success=success))

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
        """Interfaces processor's prepare_transaction."""
        return self._get_processor().prepare_transaction(
            request=request, view=view, **kwargs
        )

    def prepare_transaction_for_rest(
        self,
        request: HttpRequest | None = None,
        view: View | None = None,
        **kwargs,
    ) -> RestfulResult:
        """Helper returning data as dict for REST integration."""
        result = self.prepare_transaction(request=request, view=view, **kwargs)
        data = {'status_code': result.status_code, 'result': result}
        if result.status_code == 200:
            data['target_url'] = result.context_data['paywall_url']
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
                    for name, field in result.context_data[
                        'form'
                    ].fields.items()
                ],
            }
        elif result.status_code == 302:
            data['target_url'] = result.url
        else:
            data['message'] = result.content
        return data

    @atomic
    def charge(
        self,
        amount: Decimal | float | int | None = None,
        **kwargs,
    ) -> ChargeResponse:
        """Interfaces processor's charge with FSM transitions."""
        create_payment_machine(self)
        if amount is None:
            amount = self.amount_locked
        if amount > self.amount_locked:
            raise ValueError('Cannot charge more than locked value.')
        processor = self._get_processor()
        result = processor.charge(amount=amount, **kwargs)
        if 'amount_charged' in result or result.get('success', False):
            amount_charged = result.get('amount_charged', amount)
            self.amount_locked -= amount_charged
            self.confirm_payment(amount=amount_charged)
            if self.may_trigger('mark_as_paid'):
                try:
                    self.mark_as_paid()
                except Exception:
                    logger.debug(
                        'Cannot mark as fully paid, left as partially paid.',
                        extra={
                            'payment_id': self.id,
                            'payment_status': self.status,
                        },
                    )
        elif result.get('async_call', False):
            if self.may_trigger('confirm_charge_sent'):
                self.confirm_charge_sent()
            else:
                logger.debug(
                    'Cannot confirm charge sent.',
                    extra={
                        'payment_id': self.id,
                        'payment_status': self.status,
                    },
                )
        else:
            raise ChargeFailure(
                'Error occurred while trying to charge locked amount.'
            )
        self.save()
        return result
