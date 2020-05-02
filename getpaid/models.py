import logging
import uuid
from decimal import Decimal
from importlib import import_module
from typing import List, Optional, Union

import swapper
from django import forms
from django.db import models
from django.db.transaction import atomic
from django.forms import BaseForm
from django.http import HttpRequest, HttpResponse
from django.shortcuts import resolve_url
from django.utils.timezone import now
from django.utils.translation import ugettext_lazy as _
from django.views import View
from django_fsm import (
    ConcurrentTransitionMixin,
    FSMField,
    TransitionNotAllowed,
    can_proceed,
    transition,
)

from . import FraudStatus as fs
from . import PaymentStatus as ps
from .exceptions import ChargeFailure, GetPaidException
from .processor import BaseProcessor
from .registry import registry
from .types import (
    BuyerInfo,
    ChargeResponse,
    ItemInfo,
    PaymentStatusResponse,
    RestfulResult,
)

logger = logging.getLogger(__name__)


class AbstractOrder(models.Model):
    """
    Please consider setting either primary or secondary key of your Orders to
    UUIDField. This way you will hide your volume which is valuable business
    information that should be kept hidden. If you set it as secondary key,
    remember to use ``dbindex=True`` (primary keys are indexed by default).
    Read more: https://docs.djangoproject.com/en/3.0/ref/models/fields/#uuidfield
    """

    class Meta:
        abstract = True

    def get_return_url(self, *args, success=None, **kwargs) -> str:
        """
        Method used to determine the final url the client should see after
        returning from gateway. Client will be redirected to this url after
        backend handled the original callback (i.e. updated payment status)
        and only if SUCCESS_URL or FAILURE_URL settings are NOT set.
        By default it returns the result of `get_absolute_url`
        """
        return self.get_absolute_url()

    def get_absolute_url(self) -> str:
        """
        Standard method recommended in Django docs. It should return
        the URL to see details of particular Payment (or usually - Order).
        """
        raise NotImplementedError

    def is_ready_for_payment(self) -> bool:
        """Most of the validation is made in PaymentMethodForm but if you need
        any extra validation. For example you most probably want to disable
        making another payment for order that is already paid.

        You can raise :class:`~django.forms.ValidationError` if you want more
        verbose error message.
        """
        if self.payments.exclude(status=ps.FAILED).exists():
            raise forms.ValidationError(_("Non-failed Payments exist for this Order."))
        return True

    def get_items(self) -> List[ItemInfo]:
        """
        There are backends that require some sort of item list to be attached
        to the payment. But it's up to you if the list is real or contains only
        one item called "Payment for stuff in {myshop}" ;)

        :return: List of :class:`ItemInfo` dicts. Default: order summary.
        :rtype: List[ItemInfo]
        """
        return [
            {
                "name": self.get_description(),
                "quantity": 1,
                "unit_price": self.get_total_amount(),
            }
        ]

    def get_total_amount(self) -> Decimal:
        """
        This method must return the total value of the Order.

        :return: Decimal object
        """
        raise NotImplementedError

    def get_buyer_info(self) -> BuyerInfo:
        """
        This method should return dict with necessary user info.
        For most backends email should be sufficient.
        Refer to :class`BuyerInfo` for expected structure.
        """
        raise NotImplementedError

    def get_description(self) -> str:
        """
        :return: Description of the Order. Should return the value of appropriate field.
        """
        raise NotImplementedError


class AbstractPayment(ConcurrentTransitionMixin, models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    order = models.ForeignKey(
        swapper.get_model_name("getpaid", "Order"),
        verbose_name=_("order"),
        on_delete=models.CASCADE,
        related_name="payments",
    )
    amount_required = models.DecimalField(
        _("amount required"),
        decimal_places=2,
        max_digits=20,
        help_text=_(
            "Amount required to fulfill the payment; in selected currency, normal notation"
        ),
    )
    currency = models.CharField(_("currency"), max_length=3)
    status = FSMField(
        _("status"), choices=ps.CHOICES, default=ps.NEW, db_index=True, protected=True,
    )
    backend = models.CharField(_("backend"), max_length=100, db_index=True)
    created_on = models.DateTimeField(_("created on"), auto_now_add=True, db_index=True)
    last_payment_on = models.DateTimeField(
        _("paid on"), blank=True, null=True, default=None, db_index=True
    )
    amount_locked = models.DecimalField(
        _("amount paid"),
        decimal_places=2,
        max_digits=20,
        default=0,
        help_text=_("Amount locked with this payment, ready to charge."),
    )
    amount_paid = models.DecimalField(
        _("amount paid"),
        decimal_places=2,
        max_digits=20,
        default=0,
        help_text=_("Amount actually paid."),
    )
    refunded_on = models.DateTimeField(
        _("refunded on"), blank=True, null=True, default=None, db_index=True
    )
    amount_refunded = models.DecimalField(
        _("amount refunded"), decimal_places=4, max_digits=20, default=0
    )
    external_id = models.CharField(
        _("external id"), max_length=64, blank=True, db_index=True, default=""
    )
    description = models.CharField(
        _("description"), max_length=128, blank=True, default=""
    )
    fraud_status = FSMField(
        _("fraud status"),
        max_length=20,
        choices=fs.CHOICES,
        default=fs.UNKNOWN,
        db_index=True,
        protected=True,
    )
    fraud_message = models.TextField(_("fraud message"), blank=True)

    _processor = None

    class Meta:
        abstract = True
        ordering = ["-created_on"]
        verbose_name = _("Payment")
        verbose_name_plural = _("Payments")

    def __str__(self):
        return "Payment #{self.id}".format(self=self)

    # First some helpful properties and internals

    @property
    def processor(self) -> BaseProcessor:
        if self._processor is None:
            self._processor = self.get_processor()
        return self._processor

    @property
    def fully_paid(self) -> bool:
        return self.amount_paid >= self.amount_required

    def get_processor(self) -> BaseProcessor:
        """
        Returns the processor instance for the backend that
        was chosen for this Payment. By default it takes it from global
        backend registry and tries to import it when it's not there.
        You most probably don't want to mess with this.
        """
        if self.backend in registry:
            processor = registry[self.backend]
        else:
            # last resort if backend has been removed from INSTALLED_APPS
            module = import_module(self.backend)
            processor = getattr(module, "PaymentProcessor")
        return processor(self)

    # Then some customization enablers

    def get_unique_id(self) -> str:
        """
        Return unique identifier for this payment. Most paywalls call this
        "external id". Default: str(self.id) which is uuid4.
        """
        return str(self.id)

    def get_items(self) -> List[ItemInfo]:
        """
        Some backends require the list of items to be added to Payment.

        This method relays the call to Order. It is here simply because
        you can change the Order's fieldname when customizing Payment model.
        In that case you need to overwrite this method so that it properly
        returns a list.
        """
        # TODO: type/interface annotation
        return self.order.get_items()

    def get_buyer_info(self) -> BuyerInfo:
        return self.order.get_buyer_info()

    def get_form(self, *args, **kwargs) -> BaseForm:
        """
        Interfaces processor's ``get_form``.

        Returns a Form to be used on intermediate page if the method returned by
        ``get_redirect_method`` is 'POST'.
        """
        return self.processor.get_form(*args, **kwargs)

    def get_template_names(self, view=None) -> List[str]:
        """
        Interfaces processor's ``get_template_names``.

        Used to get templates for intermediate page when ``get_redirect_method``
        returns 'POST'.
        """
        return self.processor.get_template_names(view=view)

    def handle_paywall_callback(self, request, **kwargs) -> HttpResponse:
        """
        Interfaces processor's ``handle_paywall_callback``.

        Called when 'PUSH' flow is used for a backend. In this scenario paywall
        will send a request to our server with information about the state of
        Payment. Broker can send several such requests during Payment's lifetime.
        Backend should analyze this request and return appropriate response that
        can be understood by paywall.

        :param request: Request sent by paywall.

        :return: HttpResponse instance
        """
        return self.processor.handle_paywall_callback(request, **kwargs)

    def fetch_status(self) -> PaymentStatusResponse:
        """
        Interfaces processor's ``fetch_payment_status``.

        Used during 'PULL' flow. Fetches status from paywall and proposes a callback
        depending on the response.
        """
        return self.processor.fetch_payment_status()

    @atomic
    def fetch_and_update_status(self) -> PaymentStatusResponse:
        """
        Used during 'PULL' flow to automatically fetch and update
        Payment's status.
        """
        status_report = self.fetch_status()
        callback_name = status_report.get("callback")
        if callback_name:
            callback = getattr(self, callback_name)
            amount = status_report.get("amount", None)
            try:
                if can_proceed(callback):
                    status_report["callback_result"] = callback(amount=amount)
                    self.save()
                    status_report["saved"] = True
                else:
                    logger.debug(
                        f"Cannot run fetch+update callback {callback_name}.",
                        extra={
                            "payment_id": self.id,
                            "payment_status": self.status,
                            "callback": callback_name,
                        },
                    )
            except (GetPaidException, TransitionNotAllowed) as e:
                status_report["exception"] = e
        return status_report

    def get_return_redirect_url(self, request, success: bool) -> str:
        if success:
            url = self.processor.get_setting("SUCCESS_URL")
        else:
            url = self.processor.get_setting("FAILURE_URL")

        if url is not None:
            # we may want to return to Order summary or smth
            kwargs = self.get_return_redirect_kwargs(request, success)
            return resolve_url(url, **kwargs)
        return resolve_url(self.order.get_return_url(self, success=success))

    def get_return_redirect_kwargs(self, request, success: bool) -> dict:
        return {"pk": self.id}

    # Actions / FSM transitions

    def prepare_transaction(
        self,
        request: Optional[HttpRequest] = None,
        view: Optional[View] = None,
        **kwargs,
    ) -> HttpResponse:
        """
        Interfaces processor's :meth:`~getpaid.processor.BaseProcessor.prepare_transaction`.
        """
        return self.processor.prepare_transaction(request=request, view=None, **kwargs)

    def prepare_transaction_for_rest(
        self,
        request: Optional[HttpRequest] = None,
        view: Optional[View] = None,
        **kwargs,
    ) -> RestfulResult:
        """
        Helper function returning data as dict to better integrate with
        Django REST Framework.
        """
        result = self.prepare_transaction(request=request, view=view, **kwargs)
        data = {"status_code": result.status_code, "result": result}
        if result.status_code == 200:
            data["target_url"] = result.context_data["paywall_url"]
            data["form"] = {
                "fields": [
                    {
                        "name": name,
                        "value": field.initial,
                        "label": field.label or name,
                        "widget": field.widget.__class__.__name__,
                        "help_text": field.help_text,
                        "required": field.required,
                    }
                    for name, field in result.context_data["form"].fields
                ],
            }
        elif result.status_code == 302:
            data["target_url"] = result.url
        else:
            data["message"] = result.content
        return data

    @transition(field=status, source=ps.NEW, target=ps.PREPARED)
    def confirm_prepared(self, **kwargs) -> None:
        """
        Used to confirm that paywall registered POSTed form.
        """

    @transition(field=status, source=[ps.NEW, ps.PREPARED], target=ps.PRE_AUTH)
    def confirm_lock(
        self, amount: Optional[Union[Decimal, float, int]] = None, **kwargs
    ) -> None:
        """
        Used to confirm that certain amount has been locked (pre-authed).
        """
        if amount is None:
            amount = self.amount_required
        self.amount_locked = amount

    @atomic
    def charge(
        self, amount: Optional[Union[Decimal, float, int]] = None, **kwargs
    ) -> ChargeResponse:
        """
        Interfaces processor's :meth:`~getpaid.processor.BaseProcessor.charge`.
        """
        if amount is None:
            amount = self.amount_locked
        if amount > self.amount_locked:
            raise ValueError("Cannot charge more than locked value.")
        result = self.processor.charge(amount=amount, **kwargs)
        if "amount_charged" in result or result.get("success", False):
            self.amount_paid = result.get("amount_charged", amount)
            self.amount_locked -= self.amount_paid
            self.confirm_payment()
            if can_proceed(self.mark_as_paid):
                self.mark_as_paid()
            else:
                logger.debug(
                    "Cannot mark as fully paid, left as partially paid.",
                    extra={"payment_id": self.id, "payment_status": self.status,},
                )
        elif result.get("async_call", False):
            if can_proceed(self.confirm_charge_sent):
                self.confirm_charge_sent()
            else:
                logger.debug(
                    "Cannot confirm charge sent.",
                    extra={"payment_id": self.id, "payment_status": self.status,},
                )
        else:
            raise ChargeFailure("Error occurred while trying to charge locked amount.")
        self.save()
        return result

    @transition(field=status, source=ps.PRE_AUTH, target=ps.IN_CHARGE)
    def confirm_charge_sent(self, **kwargs) -> None:
        """
        Used during async charge cycle - after you send charge request,
        the confirmation will be sent to callback endpoint.
        """

    @transition(
        field=status,
        source=[ps.PRE_AUTH, ps.PREPARED, ps.IN_CHARGE, ps.PARTIAL],
        target=ps.PARTIAL,
    )
    def confirm_payment(
        self, amount: Optional[Union[Decimal, float, int]] = None, **kwargs
    ) -> None:
        """
        Used when receiving callback confirmation.
        """
        if amount is None:
            if not self.amount_locked:  # coming directly from PREPARED
                self.amount_locked = self.amount_required
            amount = self.amount_locked
        self.amount_paid += amount

    def _check_fully_paid(self) -> bool:
        return self.fully_paid

    @transition(
        field=status, source=ps.PARTIAL, target=ps.PAID, conditions=[_check_fully_paid]
    )
    def mark_as_paid(self, **kwargs) -> None:
        """
        Marks payment as fully paid if condition is met.
        """

    @transition(field=status, source=ps.PRE_AUTH, target=ps.REFUNDED)
    def release_lock(self, **kwargs) -> Decimal:
        """
        Interfaces processor's :meth:`~getpaid.processor.BaseProcessor.charge`.
        """
        self.amount_refunded = self.amount_locked
        self.amount_locked = 0
        return self.processor.release_lock(**kwargs)

    @transition(field=status, source=[ps.PAID, ps.PARTIAL], target=ps.REFUND_STARTED)
    def start_refund(
        self, amount: Optional[Union[Decimal, float, int]] = None, **kwargs
    ) -> Decimal:
        """
        Interfaces processor's :meth:`~getpaid.processor.BaseProcessor.charge`.
        """
        if amount is None:
            amount = self.amount_paid
        if amount > self.amount_paid:
            raise ValueError("Cannot refund more than amount paid.")
        return self.processor.start_refund(amount=amount, **kwargs)

    @transition(field=status, source=ps.REFUND_STARTED, target=ps.PARTIAL)
    def cancel_refund(self, **kwargs) -> bool:
        """
        Interfaces processor's :meth:`~getpaid.processor.BaseProcessor.charge`.
        """
        return self.processor.cancel_refund()

    @transition(field=status, source=ps.REFUND_STARTED, target=ps.PARTIAL)
    def confirm_refund(
        self, amount: Optional[Union[Decimal, float, int]] = None, **kwargs
    ) -> None:
        """
        Used when receiving callback confirmation.
        """
        if amount is None:
            amount = self.amount_paid
        self.amount_refunded += amount
        self.refunded_on = now()

    def _is_full_refund(self) -> bool:
        return self.amount_refunded == self.amount_paid

    @transition(
        field=status,
        source=ps.PARTIAL,
        target=ps.REFUNDED,
        conditions=[_is_full_refund],
    )
    def mark_as_refunded(self, **kwargs) -> None:
        """
        Verify if refund was partial or full.
        """

    @transition(
        field=status, source=[ps.NEW, ps.PRE_AUTH, ps.PREPARED], target=ps.FAILED
    )
    def fail(self, **kwargs) -> None:
        """
        Sets Payment as failed.
        """

    # Finally: Fraud-related actions.
    # The "uber-private" ones should be used only by processor.

    @transition(field=fraud_status, source=fs.UNKNOWN, target=fs.REJECTED)
    def ___mark_as_fraud(self, message: str = "") -> None:
        self.fraud_message = message

    @transition(field=fraud_status, source=fs.UNKNOWN, target=fs.ACCEPTED)
    def ___mark_as_legit(self, message: str = "") -> None:
        self.fraud_message = message

    @transition(field=fraud_status, source=fs.UNKNOWN, target=fs.CHECK)
    def ___mark_for_check(self, message: str = "") -> None:
        self.fraud_message = message

    @transition(field=fraud_status, source=fs.CHECK, target=fs.REJECTED)
    def mark_as_fraud(self, message: str = "", **kwargs) -> None:
        self.fraud_message += f"\n==MANUAL REJECT==\n{message}"

    @transition(field=fraud_status, source=fs.CHECK, target=fs.ACCEPTED)
    def mark_as_legit(self, message: str = "", **kwargs) -> None:
        self.fraud_message += f"\n==MANUAL ACCEPT==\n{message}"


class Payment(AbstractPayment):
    class Meta(AbstractPayment.Meta):
        swappable = swapper.swappable_setting("getpaid", "Payment")
