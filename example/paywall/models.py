import uuid

import httpx
from django.db import models
from getpaid_core.enums import FraudStatus, PaymentStatus

from getpaid.types import FRAUD_STATUS_CHOICES, PAYMENT_STATUS_CHOICES


class PaymentEntry(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    ext_id = models.CharField(max_length=100, db_index=True, default=uuid.uuid4)
    value = models.DecimalField(decimal_places=2, max_digits=20)
    currency = models.CharField(max_length=3)
    description = models.TextField(blank=True)
    callback = models.URLField(blank=True)
    success_url = models.URLField(blank=True)
    failure_url = models.URLField(blank=True)
    payment_status = models.CharField(
        max_length=50,
        choices=PAYMENT_STATUS_CHOICES,
        default=PaymentStatus.PREPARED,
    )
    fraud_status = models.CharField(
        max_length=50,
        choices=FRAUD_STATUS_CHOICES,
        default=FraudStatus.UNKNOWN,
    )

    def _send_status_to_callback(self, status):
        httpx.post(
            self.callback, json={'id': str(self.id), 'new_status': status}
        )

    def send_confirm_lock(self):
        self.payment_status = PaymentStatus.PRE_AUTH
        self.save()
        self._send_status_to_callback(PaymentStatus.PRE_AUTH)

    def send_confirm_charge(self):
        self.payment_status = PaymentStatus.PAID
        self.save()
        self._send_status_to_callback(PaymentStatus.PAID)

    def send_fail(self):
        self.payment_status = PaymentStatus.FAILED
        self.save()
        self._send_status_to_callback(PaymentStatus.FAILED)

    def start_refund(self):
        self.payment_status = PaymentStatus.REFUND_STARTED
        self.save()

    def send_confirm_refund(self):
        self.payment_status = PaymentStatus.REFUNDED
        self.save()
        self._send_status_to_callback(PaymentStatus.REFUNDED)

    def cancel_refund(self):
        self.payment_status = PaymentStatus.PAID
        self.save()
