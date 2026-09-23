from django.db import models

from getpaid.abstracts import AbstractOrder, AbstractPayment


class Order(AbstractOrder):
    name = models.CharField(max_length=100)
    total = models.DecimalField(max_digits=20, decimal_places=2)
    currency = models.CharField(max_length=3)


class JoinedPaymentManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset().select_related('order')


class Payment(AbstractPayment):
    id = models.CharField(primary_key=True, max_length=100)
    objects = JoinedPaymentManager()
