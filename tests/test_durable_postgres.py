"""Independent-process checks; SQLite does not prove database serialization.

Run against compose.test.yml's isolated testdb through TEST_DATABASE_URL.
No provider, web server, or browser participates.
"""

import multiprocessing
import traceback
from datetime import UTC, datetime
from decimal import Decimal
from time import monotonic, sleep

import pytest
from django.db import connection

pytest.importorskip(
    'getpaid_core.durable',
    reason='Requires next-major core development checkout',
)

from getpaid_core.durable import (
    OperationIntent,
    OperationOutcome,
    OperationState,
    OperationType,
)
from getpaid_core.enums import PaymentStatus

pytestmark = pytest.mark.django_db(transaction=True)


def _worker(database, identity, action, value, barrier, output):
    # spawn starts with no Django app registry or connection inherited.
    import django

    django.setup()
    from django.db import connections
    from getpaid_core.exceptions import OperationConflictError
    from getpaid_core.types import PaymentUpdate

    from getpaid.durable_repository import DjangoDurablePaymentRepository

    connections['default'].settings_dict['NAME'] = database
    repository = DjangoDurablePaymentRepository()
    try:
        # Detached, independent snapshot before either worker may mutate.
        repository.get_payment_facts_sync(identity)
        barrier.wait(timeout=30)
        if action == 'observe':
            amount, event = value
            result = repository.apply_observation_sync(
                identity,
                PaymentUpdate(
                    paid_amount=Decimal(amount), provider_event_id=event
                ),
            ).applied
        elif action == 'reserve':
            try:
                repository.reserve_operation_sync(
                    identity, OperationIntent(value, OperationType.CHARGE)
                )
                result = 'reserved'
            except OperationConflictError:
                result = 'conflict'
        elif action == 'claim':
            result = repository.claim_submission_sync(
                identity,
                'capture',
                expected_attempt=0,
                now=datetime(2026, 9, 9, tzinfo=UTC),
            ).granted
        elif action == 'dispute':
            repository.record_operation_outcome_sync(
                identity,
                'capture',
                OperationOutcome(
                    OperationState.SUCCEEDED, Decimal(value), 'capture-1'
                ),
            )
            result = 'retained'
        else:
            raise ValueError('Unknown test action')  # noqa: TRY301
        output.put(('ok', result))
    except BaseException:
        output.put(('error', traceback.format_exc()))
        raise
    finally:
        connections.close_all()


def _run_race(identity, action, values):
    context = multiprocessing.get_context('spawn')
    barrier = context.Barrier(2)
    output = context.Queue()
    workers = [
        context.Process(
            target=_worker,
            args=(
                connection.settings_dict['NAME'],
                identity,
                action,
                value,
                barrier,
                output,
            ),
        )
        for value in values
    ]
    try:
        for worker in workers:
            worker.start()
        results = [output.get(timeout=60) for _ in workers]
        for worker in workers:
            worker.join(timeout=60)
            assert worker.exitcode == 0, results
        assert all(kind == 'ok' for kind, _value in results), results
        return [value for _kind, value in results]
    finally:
        for worker in workers:
            if worker.is_alive():
                worker.terminate()
                worker.join(timeout=10)
        output.close()


@pytest.fixture
def postgres_payment(payment_factory):
    if connection.vendor != 'postgresql':
        pytest.skip('Requires PostgreSQL; SQLite cannot prove row locking.')
    from getpaid.durable_repository import DjangoDurablePaymentRepository

    payment = payment_factory(
        amount_required=Decimal(100),
        amount_locked=Decimal(100),
        status=PaymentStatus.PRE_AUTH,
    )
    repository = DjangoDurablePaymentRepository()
    repository.migrate_payment_sync(str(payment.pk))
    return repository, str(payment.pk)


@pytest.mark.parametrize(
    ('values', 'expected_count', 'reconciliation'),
    [
        ((('40', 'partial'), ('100', 'full')), 2, False),
        ((('40', 'same'), ('40', 'same')), 1, False),
        ((('40', 'same'), ('100', 'same')), 1, True),
    ],
)
def test_observation_process_races(
    postgres_payment, values, expected_count, reconciliation
):
    from getpaid.durable_models import DurableReplay

    repository, identity = postgres_payment
    applied = _run_race(identity, 'observe', values)
    assert sum(applied) == expected_count
    facts = repository.get_payment_facts_sync(identity)
    assert facts.reconciliation_required is reconciliation
    assert DurableReplay.objects.count() == expected_count
    if expected_count == 2:
        assert facts.captured_funds == Decimal(100)
    if reconciliation:
        assert len(facts.observation_conflicts) == 1


def test_distinct_reservations_cannot_both_see_empty_history(postgres_payment):
    repository, identity = postgres_payment
    assert sorted(_run_race(identity, 'reserve', ('first', 'second'))) == [
        'conflict',
        'reserved',
    ]
    assert len(repository.list_unresolved_operations_sync()) == 1


def test_same_intent_and_submission_claim_races(postgres_payment):
    repository, identity = postgres_payment
    assert _run_race(identity, 'reserve', ('capture', 'capture')) == [
        'reserved',
        'reserved',
    ]
    assert sum(_run_race(identity, 'claim', (None, None))) == 1
    assert repository.get_operation_sync(
        identity, 'capture'
    ).pending_response_attempts == (1,)


def test_concurrent_disputes_preserve_both_claims(postgres_payment):
    repository, identity = postgres_payment
    repository.reserve_operation_sync(
        identity, OperationIntent('capture', OperationType.CHARGE)
    )
    repository.record_operation_outcome_sync(
        identity,
        'capture',
        OperationOutcome(OperationState.SUCCEEDED, Decimal(20), 'capture-1'),
    )
    _run_race(identity, 'dispute', ('30', '40'))
    record = repository.get_operation_sync(identity, 'capture')
    assert {item.settled_amount for item in record.conflicting_outcomes} == {
        Decimal(30),
        Decimal(40),
    }
    assert repository.get_payment_facts_sync(
        identity
    ).captured_funds == Decimal(20)


def _lock_worker(database, identity, output):
    import django

    django.setup()
    from django.db import connections

    from getpaid.durable_repository import DjangoDurablePaymentRepository

    database_connection = connections['default']
    database_connection.settings_dict['NAME'] = database
    try:
        with database_connection.cursor() as cursor:
            cursor.execute('SELECT pg_backend_pid()')
            output.put(cursor.fetchone()[0])
        DjangoDurablePaymentRepository().reserve_operation_sync(
            identity, OperationIntent('blocked', OperationType.CHARGE)
        )
    finally:
        connections.close_all()


def test_repeatable_read_refused_before_reservation(postgres_payment):
    from django.db import NotSupportedError

    repository, identity = postgres_payment
    with repository.atomic():
        with connection.cursor() as cursor:
            cursor.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ')
        with pytest.raises(NotSupportedError, match='READ COMMITTED'):
            repository.reserve_operation_sync(
                identity,
                OperationIntent('unsafe-snapshot', OperationType.CHARGE),
            )


def test_mutation_waits_for_existing_payment_row_lock(postgres_payment):
    repository, identity = postgres_payment
    context = multiprocessing.get_context('spawn')
    output = context.Queue()
    worker = context.Process(
        target=_lock_worker,
        args=(connection.settings_dict['NAME'], identity, output),
    )
    try:
        with repository.atomic():
            repository.model_class.objects.select_for_update(of=('self',)).get(
                pk=identity
            )
            worker.start()
            pid = output.get(timeout=30)
            deadline = monotonic() + 10
            blocked = False
            while not blocked and monotonic() < deadline:
                with connection.cursor() as cursor:
                    cursor.execute(
                        'SELECT cardinality(pg_blocking_pids(%s)) > 0', [pid]
                    )
                    blocked = cursor.fetchone()[0]
                if not blocked:
                    sleep(0.01)
            assert blocked, 'Mutation did not wait for the payment row lock'
        worker.join(timeout=30)
        assert worker.exitcode == 0
        assert repository.get_operation_sync(identity, 'blocked') is not None
    finally:
        if worker.is_alive():
            worker.terminate()
            worker.join(timeout=10)
        output.close()
