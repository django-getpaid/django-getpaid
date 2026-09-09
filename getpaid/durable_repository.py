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
    OperationRecord,
    PaymentFacts,
    ReplayRecord,
    plan_migration,
    plan_observation,
    plan_operation_failure,
    plan_outcome,
    plan_reservation,
    plan_resolution,
    plan_submission,
)
from getpaid_core.exceptions import OperationConflictError

from getpaid.durable_codec import dump_record, load_record
from getpaid.durable_models import (
    DurableOperation,
    DurablePaymentState,
    DurableReplay,
)


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

    def seed_sync(self, facts):
        """Initialize an uninitialized root from explicitly supplied import facts.

        This is not a repair/update API. Core migration validation may add a
        reconciliation flag; it never clears a supplied flag or retained claims.
        """
        if type(facts) is not PaymentFacts:
            raise TypeError('seed requires PaymentFacts.')
        with self._locked_payment(facts.payment_id) as payment:
            if str(payment.pk) != facts.payment_id:
                raise ValueError(
                    'Use the canonical string payment primary key.'
                )
            if (
                DurablePaymentState.objects
                .using(self.using)
                .filter(payment_id=payment.pk)
                .exists()
            ):
                raise ValueError('Durable payment already initialized.')
            plan = plan_migration(
                LegacyPaymentState(
                    payment_id=facts.payment_id,
                    amount_required=facts.amount_required,
                    backend=facts.backend,
                    amount_paid=facts.captured_funds,
                    amount_refunded=facts.refunded_funds,
                    amount_locked=facts.remaining_authorization,
                    status=facts.status,
                    external_id=facts.external_id,
                    fraud_status=facts.fraud_status,
                    fraud_message=facts.fraud_message,
                    provider_data=facts.provider_data,
                )
            )
            facts = replace(
                facts,
                reconciliation_required=facts.reconciliation_required
                or plan.facts.reconciliation_required,
            )
            _insert(
                DurablePaymentState,
                self.using,
                payment_id=payment.pk,
                facts=dump_record(facts),
                reconciliation_required=facts.reconciliation_required,
            )
            return replace(plan, facts=facts)

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
            return None
        return load_record(row.record, OperationRecord)

    @contextmanager
    def _current(self, payment_id):
        with self._locked_payment(payment_id) as payment:
            try:
                state = DurablePaymentState.objects.using(self.using).get(
                    payment_id=payment.pk
                )
            except DurablePaymentState.DoesNotExist as exc:
                raise KeyError(payment_id) from exc
            facts = load_record(state.facts, PaymentFacts)
            operations = tuple(
                load_record(row.record, OperationRecord)
                for row in DurableOperation.objects
                .using(self.using)
                .filter(payment_id=state.pk)
                .order_by('pk')
            )
            yield state, facts, operations

    @staticmethod
    def _operation(operations, operation_id):
        for operation in operations:
            if operation.operation_id == operation_id:
                return operation
        raise OperationConflictError(
            'Operation was never reserved on this payment.'
        )

    def _write_facts(self, state, facts):
        previous = load_record(state.facts, PaymentFacts)
        if (
            facts.payment_id != previous.payment_id
            or facts.backend != previous.backend
        ):
            raise ValueError('Durable identity cannot change.')
        if any(
            item not in facts.observation_conflicts
            for item in previous.observation_conflicts
        ):
            raise ValueError('Retained observation evidence cannot be erased.')
        _writer(DurablePaymentState, self.using).filter(pk=state.pk).update(
            facts=dump_record(facts),
            reconciliation_required=facts.reconciliation_required,
        )

    def _write_operation(self, state, operation):
        rows = _writer(DurableOperation, self.using).filter(
            payment_id=state.pk, operation_id=operation.operation_id
        )
        previous = rows.first()
        values = dict(
            record=dump_record(operation),
            unresolved=operation.is_active
            or operation.reconciliation_required
            or operation.response_pending,
        )
        if previous is None:
            _insert(
                DurableOperation,
                self.using,
                payment_id=state.pk,
                operation_id=operation.operation_id,
                **values,
            )
        else:
            retained = load_record(previous.record, OperationRecord)
            for name in (
                'conflicting_outcomes',
                'recovery_evidence',
                'resolutions',
            ):
                if any(
                    item not in getattr(operation, name)
                    for item in getattr(retained, name)
                ):
                    raise ValueError(
                        'Retained operation evidence cannot be erased.'
                    )
            rows.update(**values)

    def reserve_operation_sync(self, payment_id, intent):
        with self._current(payment_id) as (state, facts, operations):
            plan = plan_reservation(facts, operations, intent)
            self._write_operation(state, plan.operation)
            if plan.facts is not None:
                self._write_facts(state, plan.facts)
            return plan.operation

    def claim_submission_sync(
        self,
        payment_id,
        operation_id,
        *,
        expected_attempt,
        now,
        retry_until=None,
        idempotency_scope=None,
    ):
        with self._current(payment_id) as (state, facts, operations):
            plan = plan_submission(
                facts,
                self._operation(operations, operation_id),
                expected_attempt=expected_attempt,
                now=now,
                retry_until=retry_until,
                idempotency_scope=idempotency_scope,
            )
            self._write_operation(state, plan.operation)
            return plan

    def _write_outcome(self, state, plan):
        self._write_facts(state, plan.facts)
        for operation in (plan.operation, *plan.related_operations):
            self._write_operation(state, operation)

    def record_operation_outcome_sync(
        self, payment_id, operation_id, outcome, *, response_attempt=None
    ):
        with self._current(payment_id) as (state, facts, operations):
            plan = plan_outcome(
                facts,
                self._operation(operations, operation_id),
                outcome,
                operations=operations,
                response_attempt=response_attempt,
            )
            self._write_outcome(state, plan)
            return plan

    def record_operation_failure_sync(self, payment_id, operation_id, evidence):
        with self._current(payment_id) as (state, _facts, operations):
            operation = plan_operation_failure(
                self._operation(operations, operation_id), evidence
            )
            self._write_operation(state, operation)
            return operation

    def apply_observation_sync(self, payment_id, update):
        with self._current(payment_id) as (state, facts, operations):
            replay = tuple(
                ReplayRecord(
                    facts.payment_id,
                    row.backend,
                    row.event_identity,
                    row.content_digest,
                )
                for row in DurableReplay.objects
                .using(self.using)
                .filter(payment_id=state.pk)
                .order_by('pk')
            )
            plan = plan_observation(
                facts, replay, update, operations=operations
            )
            self._write_facts(state, plan.facts)
            for operation in plan.operations:
                self._write_operation(state, operation)
            if plan.replay_record is not None:
                record = plan.replay_record
                _insert(
                    DurableReplay,
                    self.using,
                    payment_id=state.pk,
                    backend=record.backend,
                    event_identity=record.event_identity,
                    content_digest=record.content_digest,
                )
            return plan

    def resolve_operation_sync(
        self,
        payment_id,
        operation_id,
        resolution,
        *,
        expected_operation,
        expected_facts,
    ):
        with self._current(payment_id) as (state, facts, operations):
            plan = plan_resolution(
                facts,
                self._operation(operations, operation_id),
                resolution,
                expected_operation=expected_operation,
                expected_facts=expected_facts,
                operations=operations,
            )
            self._write_outcome(state, plan)
            return plan

    def list_payments_requiring_reconciliation_sync(self):
        return tuple(
            load_record(row.facts, PaymentFacts)
            for row in DurablePaymentState.objects
            .using(self.using)
            .filter(reconciliation_required=True)
            .order_by('pk')
        )

    def list_unresolved_operations_sync(self):
        return tuple(
            load_record(row.record, OperationRecord)
            for row in DurableOperation.objects
            .using(self.using)
            .filter(unresolved=True)
            .order_by('pk')
        )

    apply_observation = sync_to_async(
        apply_observation_sync, thread_sensitive=True
    )
    resolve_operation = sync_to_async(
        resolve_operation_sync, thread_sensitive=True
    )
    list_payments_requiring_reconciliation = sync_to_async(
        list_payments_requiring_reconciliation_sync, thread_sensitive=True
    )
    reserve_operation = sync_to_async(
        reserve_operation_sync, thread_sensitive=True
    )
    claim_submission = sync_to_async(
        claim_submission_sync, thread_sensitive=True
    )
    record_operation_outcome = sync_to_async(
        record_operation_outcome_sync, thread_sensitive=True
    )
    record_operation_failure = sync_to_async(
        record_operation_failure_sync, thread_sensitive=True
    )
    list_unresolved_operations = sync_to_async(
        list_unresolved_operations_sync, thread_sensitive=True
    )
    seed = sync_to_async(seed_sync, thread_sensitive=True)
    migrate_payment = sync_to_async(migrate_payment_sync, thread_sensitive=True)
    get_payment_facts = sync_to_async(
        get_payment_facts_sync, thread_sensitive=True
    )
    get_operation = sync_to_async(get_operation_sync, thread_sensitive=True)
