import uuid
from importlib import import_module

import pendulum
import swapper
from django.conf import settings
from django.db import models
from django.shortcuts import resolve_url
from django.utils.translation import ugettext_lazy as _

from . import FraudStatus, PaymentStatus, signals
from .registry import registry


class AbstractOrder(models.Model):
    class Meta:
        abstract = True

    def get_return_url(self, *args, success=None, **kwargs):
        """
        Method used to determine the final url the client should see after
        returning from gateway. Client will be redirected to this url after
        backend handled the original callback (i.e. updated payment status)
        and only if SUCCESS_URL or FAILURE_URL settings are NOT set.
        By default it returns the result of `get_absolute_url`
        """
        return self.get_absolute_url()

    def get_absolute_url(self):
        """
        Standard method recommended in Django docs. It should return
        the URL to see details of particular Order.
        """
        raise NotImplementedError

    def is_ready_for_payment(self):
        """Most of the validation is made in PaymentMethodForm using but if you
        need any extra validation. For example you most probably want to disable
        making another payment for order that is already paid."""
        return True

    def get_items(self):
        """
        There are backends that require some sort of item list to be attached
        to the payment. But it's up to you if the list is real or contains only
        one item called "Payment for stuff in {myshop}" ;)

        :return: List of {"name": str, "quantity": Decimal, "unit_price": Decimal} dicts.
        """
        return [
            {
                "name": self.get_description(),
                "quantity": 1,
                "unit_price": self.get_total_amount(),
            }
        ]

    def get_total_amount(self):
        """
        This method must return the total value of the Order.

        :return: Decimal object
        """
        raise NotImplementedError

    def get_user_info(self) -> dict:
        """
        This method should return dict with necessary user info.
        For most backends email should be sufficient.
        Expected field names: `email`, `first_name`, `last_name`, `phone`
        """
        raise NotImplementedError

    def get_description(self) -> str:
        """
        :return: Description of the Order. Should return the value of appropriate field.
        """
        raise NotImplementedError


class AbstractPayment(models.Model):
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
    status = models.CharField(
        _("status"),
        max_length=20,
        choices=PaymentStatus.CHOICES,
        default=PaymentStatus.NEW,
        db_index=True,
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
    fraud_status = models.CharField(
        _("fraud status"),
        max_length=20,
        choices=FraudStatus.CHOICES,
        default=FraudStatus.UNKNOWN,
        db_index=True,
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

    @property
    def processor(self):
        if self._processor is None:
            self._processor = self.get_processor()
        return self._processor

    def get_items(self):
        """
        Some backends require the list of items to be added to Payment.

        This method relays the call to Order. It is here simply because
        you can change the Order's fieldname when customizing Payment model.
        In that case you need to overwrite this method so that it properly
        returns a list.
        """
        # TODO: type/interface annotation
        return self.order.get_items()

    def get_processor(self):
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

    def change_status(self, new_status):
        """
        Used for changing the status of the Payment.
        You should always change payment status via this method.
        Otherwise the signal will not be emitted.
        """
        if self.status != new_status:
            # do anything only when status is really changed
            old_status = self.status
            self.status = new_status
            self.save()
            signals.payment_status_changed.send(
                sender=self.__class__,
                instance=self,
                old_status=old_status,
                new_status=new_status,
            )

    def change_fraud_status(self, new_status, message=""):
        """
        Used for changing fraud status of the Payment.
        You should always change payment fraud status via this method.
        Otherwise the signal will not be emitted.
        """
        if self.fraud_status != new_status:
            # do anything only when status is really changed
            old_status = self.fraud_status
            self.fraud_status = new_status
            self.fraud_message = message
            self.save()
            signals.payment_fraud_changed.send(
                sender=self.__class__,
                instance=self,
                old_status=old_status,
                new_status=new_status,
                message=message,
            )

    @property
    def fully_paid(self):
        return self.amount_paid >= self.amount_required

    def on_success(self, amount=None):
        """
        Called when payment receives successful balance income. It defaults to
        complete payment, but can optionally accept received amount as a parameter
        to handle partial payments.

        Returns boolean value whether payment was fully paid.
        """
        if getattr(settings, "USE_TZ", False):
            timezone = getattr(settings, "TIME_ZONE", "local")
            self.last_payment_on = pendulum.now(timezone)
        else:
            self.last_payment_on = pendulum.now("UTC")

        if amount:
            self.amount_paid = amount
        else:
            self.amount_paid = self.amount_required

        if self.fully_paid:
            self.change_status(PaymentStatus.PAID)
        else:
            self.change_status(PaymentStatus.PARTIAL)

        return self.fully_paid

    def on_failure(self):
        """
        Called when payment has failed. By default changes status to 'failed'
        """
        self.change_status(PaymentStatus.FAILED)

    def get_paywall_method(self) -> str:
        """
        Interfaces processor's ``get_paywall_method``.

        Returns the method to be used to complete the payment - 'POST', 'GET', or 'REST.
        """
        return self.processor.get_paywall_method()

    def get_form(self, *args, **kwargs):
        """
        Interfaces processor's ``get_form``.

        Returns a Form to be used on intermediate page if the method returned by
        ``get_redirect_method`` is 'POST'.
        """
        return self.processor.get_form(*args, **kwargs)

    def get_paywall_url(self, params=None) -> str:
        """
        Interfaces processor's ``get_paywall_url``.

        Returns URL where the user will be redirected to complete the payment.

        Takes optional ``params`` which can help with constructing the url.
        """
        return self.processor.get_paywall_url(params)

    def get_template_names(self, view=None):
        """
        Interfaces processor's ``get_template_names``.

        Used to get templates for intermediate page when ``get_redirect_method``
        returns 'POST'.
        """
        return self.processor.get_template_names(view=view)

    def get_paywall_params(self, request) -> dict:
        """
        Interfaces processor's ``get_paywall_params``.

        Returns a dictionary containing all the data required by
        backend to process the payment in appropriate format.
        The data is extracted from Payment and Order.
        """
        return self.processor.get_paywall_params(request)

    def prepare_paywall_headers(self, obj: dict = None) -> dict:
        """
        Interfaces processor's ``prepare_paywall_headers``.

        Prepares headers for REST request to paywall.
        """
        return self.processor.prepare_paywall_headers(obj)

    def handle_paywall_response(self, response) -> dict:
        """
        Interfaces processor's ``handle_paywall_response``.

        Validates and dictifies any direct response from paywall.
        """
        return self.processor.handle_paywall_response(response)

    def handle_paywall_callback(self, request, *args, **kwargs):
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
        return self.processor.handle_paywall_callback(request, *args, **kwargs)

    def fetch_status(self):
        """
        Interfaces processor's ``fetch_payment_status``.

        Used during 'PULL' flow. Fetches status from paywall and translates it to
        a value from ``PAYMENT_STATUS_CHOICES``.
        """
        return self.processor.fetch_payment_status()

    def fetch_and_update_status(self):
        """
        Used during 'PULL' flow to automatically fetch and update
        Payment's status.
        """
        remote_status = self.fetch_status()
        status = remote_status.get("status", None)
        amount = remote_status.get("amount", None)
        if (
            status is not None and status in [PaymentStatus.PAID, PaymentStatus.PARTIAL]
        ) or amount is not None:
            self.on_success(amount)
        elif status == PaymentStatus.FAILED:
            self.on_failure()
        elif status is not None:
            self.change_status(status)
        return status

    def lock(self, amount=None):
        """
        Used to lock payment for future charge.
        Returns locked amount.
        """
        if amount is None:
            amount = self.amount_required
        amount_locked = self.processor.lock(amount)
        if amount_locked:
            self.amount_locked = amount_locked
            self.change_status(PaymentStatus.ACCEPTED)
        else:
            self.on_failure()
        return amount_locked

    def charge_locked(self, amount=None):
        """
        Charges the locked payment.
        This method is used eg. in flows that pre-authorize payment during
        order placement and charge money just before shipping.
        """
        if self.status != PaymentStatus.ACCEPTED:
            raise ValueError("Only accepted payments can be charged.")
        if amount is None:
            amount = self.amount_locked
        if amount > self.amount_locked:
            raise ValueError("Cannot charge more than is locked.")
        amount_charged = self.processor.charge_locked(amount)
        if amount_charged:
            self.amount_locked -= amount_charged
            self.on_success(amount_charged)
        return amount_charged

    def release(self):
        """
        Release locked payment. This can happen if pre-authorized payment cannot
        be fulfilled (eg. the ordered product is no longer available for some reason).
        """
        if self.status != PaymentStatus.ACCEPTED:
            raise ValueError("Only accepted (locked) payments can be released.")

        released_amount = self.processor.release()
        self.amount_locked -= released_amount
        self.change_status(PaymentStatus.REFUNDED)
        return released_amount

    def refund(self, amount=None):
        """
        Interfaces processor's ``refund``.

        :param: amount - optional refund amount - if not given, refunds paid value.
        :returns: the result of processor's ``refund`` method that should return the amount refunded.

        """
        if self.status not in [PaymentStatus.PAID, PaymentStatus.PARTIAL]:
            raise ValueError("Only paid paymets can be refunded.")
        if amount is None:
            amount = self.amount_locked
        if amount:
            if amount > self.amount_locked:
                raise ValueError("Cannot refund more than what was paid.")
            self.amount_refunded = self.processor.refund(amount)
            self.amount_locked -= self.amount_refunded
            self.refunded_on = pendulum.now()
            self.save()
            if self.amount_locked == 0:
                self.change_status(PaymentStatus.REFUNDED)
        return self.amount_refunded

    def get_return_redirect_url(self, request, success):
        fallback_settings = getattr(settings, "GETPAID", {})

        if success:
            url = self.processor.get_setting(
                "SUCCESS_URL", getattr(fallback_settings, "SUCCESS_URL", None)
            )
        else:
            url = self.processor.get_setting(
                "FAILURE_URL", getattr(fallback_settings, "FAILURE_URL", None)
            )

        if url is not None:
            # we may want to return to Order summary or smth
            kwargs = self.get_return_redirect_kwargs(request, success)
            return resolve_url(url, **kwargs)
        return resolve_url(self.order.get_return_url(self, success=success))

    def get_return_redirect_kwargs(self, request, success):
        return {"pk": self.order_id}


class Payment(AbstractPayment):
    class Meta(AbstractPayment.Meta):
        swappable = swapper.swappable_setting("getpaid", "Payment")
