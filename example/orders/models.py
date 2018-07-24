from django.db import models
from django.urls import reverse
from django.utils.encoding import python_2_unicode_compatible

import getpaid

ORDER_STATUS_CHOICES = (
    ('W', 'Waiting for payment'),
    ('P', 'Payment complete')
)


@python_2_unicode_compatible
class Order(models.Model):
    """
    This is an example Order object. This one is very simple - is only one item,
    but you can easily create more complicated models with multi-items it does not matter
    for payment processing.
    """
    name = models.CharField(max_length=100, default="Lock, Stock and Two Smoking Barrels")
    total = models.DecimalField(decimal_places=2, max_digits=8, default='199.99')
    currency = models.CharField(max_length=3, default='EUR')
    status = models.CharField(max_length=1, blank=True, default='W',
                              choices=ORDER_STATUS_CHOICES)

    def get_absolute_url(self):
        return reverse('order_detail', kwargs={'pk': self.pk})

    def __str__(self):
        return self.name

    def clean(self):
        self.currency = self.currency.upper()


Payment = getpaid.register_to_payment(Order,
                                      unique=False,
                                      related_name='payments')
