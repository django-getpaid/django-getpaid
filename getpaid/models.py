import uuid
from importlib import import_module

import pendulum
import swapper
from django.conf import settings
from django.db import models
from django.utils.translation import ugettext_lazy as _

from . import FraudStatus, PaymentStatus, signals
from .registry import registry


class AbstractOrder(models.Model):
    class Meta:
        abstract = True

    def get_redirect_url(self, *args, success=None, **kwargs):
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

    def get_user_info(self):
        """
        This method should return dict with necessary user info.
        For most backends email should be sufficient.
        Expected field names: `email`, `first_name`, `last_name`, `phone`
        """
        raise NotImplementedError

    def get_description(self):
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
    amount = models.DecimalField(_("amount"), decimal_places=4, max_digits=20)
    currency = models.CharField(_("currency"), max_length=3)
    status = models.CharField(
        _("status"),
        max_length=20,
        choices=PaymentStatus.CHOICES,
        default=PaymentStatus.NEW,
        db_index=True,
    )
    backend = models.CharField(_("backend"), max_length=50)
    created_on = models.DateTimeField(_("created on"), auto_now_add=True, db_index=True)
    paid_on = models.DateTimeField(
        _("paid on"), blank=True, null=True, default=None, db_index=True
    )
    amount_paid = models.DecimalField(
        _("amount paid"), decimal_places=4, max_digits=20, default=0
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
        """
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

    def on_success(self, amount=None):
        """
        Called when payment receives successful balance income. It defaults to
        complete payment, but can optionally accept received amount as a parameter
        to handle partial payments.

        Returns boolean value whether payment was fully paid.
        """
        if getattr(settings, "USE_TZ", False):
            timezone = getattr(settings, "TIME_ZONE", "local")
            self.paid_on = pendulum.now(timezone)
        else:
            self.paid_on = pendulum.now("UTC")

        if amount:
            self.amount_paid = amount
        else:
            self.amount_paid = self.amount

        fully_paid = self.amount_paid >= self.amount

        if fully_paid:
            self.change_status("paid")
        else:
            self.change_status("partially_paid")

        return fully_paid

    def on_failure(self):
        """
        Called when payment has failed. By default changes status to 'failed'
        """
        self.change_status("failed")

    def get_redirect_params(self):
        """
        Interfaces processor's ``get_redirect_params``.

        Redirect params is a dictionary containing all the data required by
        backend to process the payment in appropriate format.
        The data is extracted from Paymentand Order.
        """
        return self.processor.get_redirect_params()

    def get_redirect_url(self):
        """
        Interfaces processor's ``get_redirect_url``.

        Returns URL where the user will be redirected to complete the payment.
        """
        return self.processor.get_redirect_url()

    def get_redirect_method(self):
        """
        Interfaces processor's ``get_redirect_method``.

        Returns the method to be used to complete the payment - 'POST' or 'GET'.
        """
        return self.processor.get_redirect_method()

    def get_form(self, *args, **kwargs):
        """
        Interfaces processor's ``get_form``.

        Returns a Form to be used on intermediate page if the method returned by
        ``get_redirect_method`` is 'POST'.
        """
        return self.processor.get_form(*args, **kwargs)

    def get_template_names(self, view=None):
        """
        Interfaces processor's ``get_template_names``.

        Used to get templates for intermediate page when ``get_redirect_method``
        returns 'POST'.
        """
        return self.processor.get_template_names(view=view)

    def handle_callback(self, request, *args, **kwargs):
        """
        Interfaces processor's ``handle_callback``.

        Called when 'PUSH' flow is used for a backend. In this scenario
        broker's server will send a request to our server with information
        about the state of Payment. Broker can send several such requests during
        Payment's lifetime. Backend should analyze this request and return
        appropriate response that can be understood by broker's service.

        :param request: Request sent by payment broker.

        :return: HttpResponse instance
        """
        return self.processor.handle_callback(request, *args, **kwargs)

    def fetch_status(self):
        """
        Interfaces processor's ``fetch_status``.

        Used during 'PULL' flow. Fetches status from broker's service
        and translates it to a value from ``PAYMENT_STATUS_CHOICES``.
        """
        return self.processor.fetch_status()

    def fetch_and_update_status(self):
        """
        Used during 'PULL' flow to automatically fetch and update
        Payment's status.
        """
        remote_status = self.fetch_status()
        status = remote_status.get("status", None)
        amount = remote_status.get("amount", None)
        if (status is not None and "paid" in status) or amount is not None:
            self.on_success(amount)
        elif status == "failed":
            self.on_failure()
        elif status is not None:
            self.change_status(status)


class Payment(AbstractPayment):
    class Meta(AbstractPayment.Meta):
        swappable = swapper.swappable_setting("getpaid", "Payment")
