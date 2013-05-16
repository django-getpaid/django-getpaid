from django.db import models
from django.utils.timezone import utc
from django.utils.translation import ugettext_lazy as _
from datetime import datetime
import sys
from abstract_mixin import AbstractMixin
import signals
from utils import import_backend_modules

PAYMENT_STATUS_CHOICES = (
        ('new', _("new")),
        ('in_progress', _("in progress")),
        ('partially_paid', _("partially paid")),
        ('paid', _("paid")),
        ('failed', _("failed")),
        )

class PaymentManager(models.Manager):
    def get_query_set(self):
        return super(PaymentManager, self).get_query_set().select_related('order')


class PaymentFactory(models.Model, AbstractMixin):
    """
    This is an abstract class that defines a structure of Payment model that will be
    generated dynamically with one additional field: ``order``
    """
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

    def __unicode__(self):
        return _("Payment #%(id)d") % { 'id' : self.id }

    @classmethod
    def contribute(cls, order, **kwargs):
        return {'order': models.ForeignKey(order, **kwargs)}


    @classmethod
    def create(cls, order, backend):
        """
            Builds Payment object based on given Order instance
        """
        payment = Payment()
        payment.order = order
        payment.backend = backend
        signals.new_payment_query.send(sender=None, order=order, payment=payment)
        if payment.currency is None or payment.amount is None:
            raise NotImplementedError('Please provide a listener for getpaid.signals.new_payment_query')
        payment.save()
        signals.new_payment.send(sender=None, order=order, payment=payment)
        return payment

    def get_processor(self):
        try:
            __import__(self.backend)
            module = sys.modules[self.backend]
            return module.PaymentProcessor
        except (ImportError, AttributeError):
            raise ValueError("Backend '%s' is not available or provides no processor." % self.backend)

    def change_status(self, new_status):
        """
        Always change payment status via this method. Otherwise the signal
        will not be emitted.
        """
        old_status = self.status
        self.status = new_status
        self.save()
        signals.payment_status_changed.send(
            sender=type(self), instance=self,
            old_status=old_status, new_status=new_status
            )

    def on_success(self, amount=None):
        """
        Called when payment receives successful balance income. It defaults to
        complete payment, but can optionally accept received amount as a parameter
        to handle partial payments.

        Returns boolean value if payment was fully paid
        """
        self.paid_on = datetime.utcnow().replace(tzinfo=utc)
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


from django.db.models.loading import cache as app_cache, register_models
#from utils import import_backend_modules

def register_to_payment(order_class, **kwargs):
    """
    A function for registering unaware order class to ``getpaid``. This will
    generate a ``Payment`` model class that will store payments with
    ForeignKey to original order class

    This also will build a model class for every enabled backend.
    """
    global Payment
    global Order
    class Payment(PaymentFactory.construct(order=order_class, **kwargs)):
        objects = PaymentManager()
        class Meta:
            ordering = ('-created_on',)
            verbose_name = _("Payment")
            verbose_name_plural = _("Payments")

    Order = order_class

    # Now build models for backends

    backend_models_modules = import_backend_modules('models')
    for backend_name, models in backend_models_modules.items():
        app_cache.register_models(backend_name, *models.build_models(Payment))
    return Payment


