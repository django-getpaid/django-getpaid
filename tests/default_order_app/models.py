from decimal import Decimal

from django.db import models

from getpaid.abstracts import AbstractOrder


class Order(AbstractOrder):
    description = models.CharField(max_length=100, default='Test order')
    total = models.DecimalField(decimal_places=2, max_digits=8, default='10.00')
    currency = models.CharField(max_length=3, default='EUR')

    def get_absolute_url(self):
        return '/order/'

    def get_total_amount(self):
        return Decimal(self.total)

    def get_buyer_info(self):
        return {'email': 'test@example.com'}

    def get_description(self):
        return self.description
