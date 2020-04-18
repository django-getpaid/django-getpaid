import uuid

import requests
from django.db import models
from django_fsm import FSMField, transition

from getpaid.status import FraudStatus as fs
from getpaid.status import PaymentStatus as ps


class PaymentEntry(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    ext_id = models.CharField(max_length=100, db_index=True, default=uuid.uuid4)
    value = models.DecimalField(decimal_places=2, max_digits=20)
    currency = models.CharField(max_length=3)
    description = models.TextField(blank=True)
    callback = models.URLField(blank=True)
    success_url = models.URLField(blank=True)
    failure_url = models.URLField(blank=True)
    payment_status = FSMField(protected=True, choices=ps.CHOICES, default=ps.PREPARED)
    fraud_status = FSMField(protected=True, choices=fs.CHOICES, default=fs.UNKNOWN)

    def _send_status_to_callback(self, status):
        requests.post(self.callback, json={"id": str(self.id), "new_status": status})

    @transition(field=payment_status, source=ps.PREPARED, target=ps.PRE_AUTH)
    def send_confirm_lock(self):
        self._send_status_to_callback(ps.PRE_AUTH)

    @transition(field=payment_status, source=ps.PRE_AUTH, target=ps.PAID)
    def send_confirm_charge(self):
        self._send_status_to_callback(ps.PAID)

    @transition(
        field=payment_status, source=[ps.PREPARED, ps.PRE_AUTH], target=ps.FAILED
    )
    def send_fail(self):
        self._send_status_to_callback(ps.FAILED)

    @transition(field=payment_status, source=ps.PAID, target=ps.REFUND_STARTED)
    def start_refund(self):
        pass

    @transition(
        field=payment_status,
        source=[ps.PRE_AUTH, ps.REFUND_STARTED],
        target=ps.REFUNDED,
    )
    def send_confirm_refund(self):
        self._send_status_to_callback(ps.REFUNDED)

    @transition(field=payment_status, source=ps.REFUND_STARTED, target=ps.PAID)
    def cancel_refund(self):
        pass
