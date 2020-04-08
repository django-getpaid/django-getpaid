import uuid

from django.db import models


class PaymentEntry(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    payment = models.CharField(max_length=100)
    value = models.DecimalField(decimal_places=2, max_digits=20)
    currency = models.CharField(max_length=3)
    description = models.TextField()
    callback = models.URLField()
    success_url = models.URLField()
    failure_url = models.URLField()
