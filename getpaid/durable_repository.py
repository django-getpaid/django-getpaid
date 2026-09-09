"""Explicit next-major storage path. Requires unreleased getpaid_core.durable.

Every synchronous mutation locks the existing payment before dependent reads.
Async methods run only local storage work on a thread-sensitive connection.
"""

from contextlib import contextmanager
from dataclasses import replace

import swapper
from asgiref.sync import sync_to_async
from django.db import models, transaction
from getpaid_core.durable import (
    LegacyPaymentState,
    PaymentFacts,
    plan_migration,
)

from getpaid.durable_codec import dump_record, load_record
from getpaid.durable_models import DurableOperation, DurablePaymentState


def _writer(model, using):
    """Private bypass of the read-only public manager; never exposed to callers."""
    return models.QuerySet(model=model, using=using)


def _insert(model, using, **values):
    # bulk_create avoids model.save(), deliberately refused on public instances.
    row = model(**values)
    _writer(model, using).bulk_create([row])
    return row


class DjangoDurablePaymentRepository:
    def __init__(self, model_class=None, *, using='default'):
        configured = swapper.load_model('getpaid', 'Payment')
        self.model_class = configured if model_class is None else model_class
        if self.model_class is not configured:
            raise ValueError(
                'model_class must be the configured swappable payment model.'
            )
        self.using = using

    def atomic(self):
        """Compose synchronous storage and application writes on this DB alias.

        Never put provider I/O inside this boundary. Use *_sync methods here;
        wrapping async methods cannot join the caller's thread-local transaction.
        """
        return transaction.atomic(using=self.using)

    @contextmanager
    def _locked_payment(self, payment_id):
        with self.atomic():
            try:
                payment = (
                    self.model_class._default_manager
                    .using(self.using)
                    .select_for_update(of=('self',))
                    .get(pk=payment_id)
                )
            except self.model_class.DoesNotExist as exc:
                raise KeyError(payment_id) from exc
            yield payment

    def migrate_payment_sync(self, payment_id):
        """Initialize once from stored 3.x state after stopping legacy writers."""
        with self._locked_payment(payment_id) as payment:
            if (
                DurablePaymentState.objects
                .using(self.using)
                .filter(payment_id=payment.pk)
                .exists()
            ):
                raise ValueError('Durable payment already initialized.')
            legacy = replace(
                LegacyPaymentState.from_payment(payment),
                payment_id=str(payment.pk),
            )
            plan = plan_migration(legacy)
            _insert(
                DurablePaymentState,
                self.using,
                payment_id=payment.pk,
                facts=dump_record(plan.facts),
                reconciliation_required=plan.facts.reconciliation_required,
            )
            return plan

    def get_payment_facts_sync(self, payment_id):
        try:
            state = DurablePaymentState.objects.using(self.using).get(
                payment_id=payment_id
            )
        except DurablePaymentState.DoesNotExist as exc:
            raise KeyError(payment_id) from exc
        return load_record(state.facts, PaymentFacts)

    def get_operation_sync(self, payment_id, operation_id):
        row = (
            DurableOperation.objects
            .using(self.using)
            .filter(payment__payment_id=payment_id, operation_id=operation_id)
            .first()
        )
        if row is None:
            return
        raise ValueError('Operation decoding not implemented yet.')

    migrate_payment = sync_to_async(migrate_payment_sync, thread_sensitive=True)
    get_payment_facts = sync_to_async(
        get_payment_facts_sync, thread_sensitive=True
    )
    get_operation = sync_to_async(get_operation_sync, thread_sensitive=True)
