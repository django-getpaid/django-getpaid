import uuid
from importlib import import_module

import pendulum
import swapper
from django.conf import settings
from django.db import models
from django.utils.translation import ugettext_lazy as _

from . import signals

PAYMENT_STATUS_CHOICES = (
    ('new', _("new")),
    ('in_progress', _("in progress")),
    ('accepted_for_proc', _("accepted for processing")),
    ('partially_paid', _("partially paid")),
    ('paid', _("paid")),
    ('cancelled', _("cancelled")),
    ('failed', _("failed")),
)


class AbstractOrder(models.Model):
    class Meta:
        abstract = True

    def get_redirect_url(self, *args, **kwargs):
        return self.get_absolute_url()

    def get_absolute_url(self):
        raise NotImplementedError

    def is_ready_for_payment(self):
        return True


class AbstractPayment(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    order = models.ForeignKey(swapper.get_model_name('getpaid', 'Order'), verbose_name=_("order"),
                              on_delete=models.CASCADE, related_name='payments')
    amount = models.DecimalField(_("amount"), decimal_places=4, max_digits=20)
    currency = models.CharField(_("currency"), max_length=3)
    status = models.CharField(_("status"), max_length=20, choices=PAYMENT_STATUS_CHOICES, default='new', db_index=True)
    backend = models.CharField(_("backend"), max_length=50)
    created_on = models.DateTimeField(_("created on"), auto_now_add=True, db_index=True)
    paid_on = models.DateTimeField(_("paid on"), blank=True, null=True, default=None, db_index=True)
    amount_paid = models.DecimalField(_("amount paid"), decimal_places=4, max_digits=20, default=0)
    external_id = models.CharField(_("external id"), max_length=64, blank=True, null=True)
    description = models.CharField(_("description"), max_length=128, blank=True, null=True)

    class Meta:
        abstract = True
        ordering = ['-created_on']
        verbose_name = _('Payment')
        verbose_name_plural = _('Payments')

    def __str__(self):
        return _("Payment #{self.id}".format(self=self))

    def get_processor(self):
        module = import_module(self.backend)
        return module.PaymentProcessor(self)

    def change_status(self, new_status):
        """
        Always change payment status via this method. Otherwise the signal
        will not be emitted.
        """
        if self.status != new_status:
            # do anything only when status is really changed
            old_status = self.status
            self.status = new_status
            self.save()
            signals.payment_status_changed.send(
                sender=self.__class__, instance=self,
                old_status=old_status, new_status=new_status
            )

    def on_success(self, amount=None):
        """
        Called when payment receives successful balance income. It defaults to
        complete payment, but can optionally accept received amount as a parameter
        to handle partial payments.

        Returns boolean value if payment was fully paid
        """
        if getattr(settings, 'USE_TZ', False):
            self.paid_on = pendulum.now('UTC')
        else:
            timezone = getattr(settings, 'TIME_ZONE', 'local')
            self.paid_on = pendulum.now(timezone)
        if amount:
            self.amount_paid = amount
        else:
            self.amount_paid = self.amount
        fully_paid = (self.amount_paid >= self.amount)
        if fully_paid:
            self.change_status('paid')
        else:
            self.change_status('partially_paid')
        return fully_paid

    def on_failure(self):
        """
        Called when payment was failed
        """
        self.change_status('failed')

    def get_redirect_params(self):
        return self.get_processor().get_redirect_params()

    def get_form(self, *args, **kwargs):
        return self.get_processor().get_form(*args, **kwargs)

    def handle_callback(self, request, *args, **kwargs):
        return self.get_processor().handle_callback(request, *args, **kwargs)

    def get_items(self):
        """
        Some backends require the list of items to be added to Payment.
        Item format: {name: "", amount: ""}
        :return:
        """
        raise NotImplementedError


class Payment(AbstractPayment):
    class Meta(AbstractPayment.Meta):
        swappable = swapper.swappable_setting('getpaid', 'Payment')
