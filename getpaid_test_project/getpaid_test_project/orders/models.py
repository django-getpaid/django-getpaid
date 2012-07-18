from django.core.urlresolvers import reverse
from django.db import models
import getpaid

class Order(models.Model):
    """
    This is an example Order object. This one is very simple - is only one item,
    but you can easily create more complicated models with multi-items it does not matter
    for payment processing.
    """
    name = models.CharField(max_length=100)
    total = models.DecimalField(decimal_places=2, max_digits=8, default=0)
    currency = models.CharField(max_length=3, default='EUR')
    status = models.CharField(max_length=1, blank=True, default='W', choices=(('W', 'Waiting for payment'),
                                                                               ('P', 'Payment complete')))
    def get_absolute_url(self):
        return reverse('order_detail', kwargs={'pk': self.pk})

    def __unicode__(self):
        return self.name

    def clean(self):
        self.currency = self.currency.upper()


getpaid.register_to_payment(Order, unique=False, related_name='payments')

#noinspection PyUnresolvedReferences
import listeners