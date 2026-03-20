from decimal import Decimal

from asgiref.sync import sync_to_async
from django.utils import timezone


class DjangoPaymentRepository:
    def __init__(self, model_class) -> None:
        self.model_class = model_class

    async def get_by_id(self, payment_id):
        return await sync_to_async(
            self._get_by_id,
            thread_sensitive=True,
        )(payment_id)

    async def create(self, **kwargs):
        return await sync_to_async(
            self._create,
            thread_sensitive=True,
        )(**kwargs)

    async def save(self, payment):
        return await sync_to_async(
            self._save,
            thread_sensitive=True,
        )(payment)

    async def update_status(self, payment_id, status, **fields):
        return await sync_to_async(
            self._update_status,
            thread_sensitive=True,
        )(payment_id, status, **fields)

    async def list_by_order(self, order_id):
        return await sync_to_async(
            self._list_by_order,
            thread_sensitive=True,
        )(order_id)

    def _get_by_id(self, payment_id):
        payment = self.model_class.objects.select_related('order').get(
            pk=payment_id
        )
        return self._normalize_payment(payment)

    def _create(self, **kwargs):
        payment = self.model_class.objects.create(**kwargs)
        return self._normalize_payment(payment)

    def _save(self, payment):
        current_time = timezone.now()
        if (
            getattr(payment, 'amount_paid', 0)
            and getattr(
                payment,
                'last_payment_on',
                None,
            )
            is None
        ):
            payment.last_payment_on = current_time
        if (
            getattr(payment, 'amount_refunded', 0)
            and getattr(
                payment,
                'refunded_on',
                None,
            )
            is None
        ):
            payment.refunded_on = current_time
        payment.save()
        return self._normalize_payment(payment)

    def _update_status(self, payment_id, status, **fields):
        payment = self.model_class.objects.select_related('order').get(
            pk=payment_id
        )
        payment.status = status
        for key, value in fields.items():
            setattr(payment, key, value)
        return self._save(payment)

    def _list_by_order(self, order_id):
        payments = list(
            self.model_class.objects.select_related('order').filter(
                order_id=order_id,
            )
        )
        return [self._normalize_payment(payment) for payment in payments]

    def _normalize_payment(self, payment):
        for field_name in (
            'amount_required',
            'amount_paid',
            'amount_locked',
            'amount_refunded',
        ):
            value = getattr(payment, field_name)
            if not isinstance(value, Decimal):
                setattr(payment, field_name, Decimal(str(value)))
        if payment.provider_data is None:
            payment.provider_data = {}
        return payment
