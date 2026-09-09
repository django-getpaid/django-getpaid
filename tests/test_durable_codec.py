"""Lossless normalized evidence, and fail-closed storage upgrades."""

import json
from datetime import UTC, datetime, timedelta, timezone
from decimal import Decimal

import pytest

pytest.importorskip(
    'getpaid_core.durable',
    reason='Requires next-major core development checkout',
)

from getpaid_core.durable import (
    ObservationConflict,
    OperationOutcome,
    OperationRecord,
    OperationState,
    OperationType,
    OperatorResolution,
    PaymentFacts,
    RecoveryEvidence,
)

from getpaid.durable_codec import dump_record, load_record


def test_recorded_money_codec_preserves_all_fields_and_refuses_changed_schema(
    monkeypatch,
):
    from dataclasses import make_dataclass
    from zoneinfo import ZoneInfo

    from getpaid_core.recorded_money import (
        RecordedMoneyCommand,
        RecordedMoneyEntry,
        RecordedMoneyKind,
        RecordingCorrectionReason,
    )

    import getpaid.durable_codec as codec

    command = RecordedMoneyCommand(
        'receipt',
        RecordedMoneyKind.RECEIPT,
        'actor',
        Decimal('1.2300'),
        datetime(
            2026,
            10,
            25,
            2,
            30,
            0,
            123456,
            tzinfo=ZoneInfo('Europe/Warsaw'),
            fold=1,
        ),
        note='safe note',
        evidence_reference='source:1',
    )
    audit = datetime(
        2026, 10, 25, 2, 30, 0, 123456, tzinfo=ZoneInfo('Europe/Warsaw'), fold=1
    )
    entry = RecordedMoneyEntry(
        'root',
        command,
        audit,
        Decimal('1.2300'),
        command.occurred_at,
        'source:1',
    )
    loaded = load_record(
        json.loads(json.dumps(dump_record(entry))), RecordedMoneyEntry
    )
    assert loaded == entry
    assert loaded.command.amount.as_tuple() == Decimal('1.2300').as_tuple()
    assert loaded.signed_amount.as_tuple() == Decimal('1.2300').as_tuple()
    assert (
        loaded.command.occurred_at.isoformat()
        == '2026-10-25T01:30:00.123456+00:00'
    )
    assert loaded.recorded_at.fold == 1
    assert loaded.recorded_at.tzinfo.key == 'Europe/Warsaw'
    correction = RecordedMoneyCommand(
        'correction',
        RecordedMoneyKind.CORRECTION,
        'reviewer',
        target_command_id='receipt',
        correction_reason=RecordingCorrectionReason.INCORRECT_REFERENCE,
    )
    inverse = RecordedMoneyEntry(
        'root',
        correction,
        audit,
        Decimal('-1.2300'),
        command.occurred_at,
        'source:1',
    )
    assert load_record(dump_record(inverse), RecordedMoneyEntry) == inverse
    for record in (command, entry):
        encoded = dump_record(record)
        for name in encoded['value'][2]:
            incomplete = json.loads(json.dumps(encoded))
            del incomplete['value'][2][name]
            with pytest.raises(
                ValueError, match='Invalid durable storage encoding'
            ):
                load_record(incomplete, type(record))
    encoded_entry = dump_record(entry)
    definition = codec._RECORDS['RecordedMoneyEntry']
    evolved = make_dataclass(
        'RecordedMoneyEntry',
        [('new_optional', str, 'default')],
        bases=(RecordedMoneyEntry,),
        frozen=True,
    )
    monkeypatch.setitem(
        codec._RECORDS, 'RecordedMoneyEntry', (evolved, definition[1])
    )
    with pytest.raises(ValueError, match='schema changed'):
        load_record(encoded_entry, evolved)


def test_complete_normalized_record_roundtrip():
    outcome = OperationOutcome(
        OperationState.SUCCEEDED,
        Decimal('1.2300'),
        'correlation',
        reconciliation_required=True,
        external_id='payment-handle',
    )
    evidence = RecoveryEvidence(
        OperationState.SUCCEEDED,
        Decimal('-1.2300'),
        'recovery',
        'payment-handle',
    )
    decision = OperatorResolution(
        'case',
        'actor',
        'Verified ledger',
        ('source:1', 'source:2'),
        datetime(2026, 9, 9, tzinfo=UTC),
        OperationOutcome(OperationState.REJECTED),
        clear_payment_reconciliation=True,
    )
    moment = datetime(
        2026,
        9,
        9,
        12,
        30,
        0,
        123456,
        tzinfo=timezone(timedelta(hours=2), 'named-offset'),
    )
    record = OperationRecord(
        payment_id='payment',
        operation_id='operation',
        operation_type=OperationType.CHARGE,
        state=OperationState.SUCCEEDED,
        resolved_amount=Decimal('4.5600'),
        parameters_digest='core-digest',
        starting_captured=Decimal(10),
        starting_refunded=Decimal(2),
        starting_authorization=Decimal(20),
        parameters={
            'nested': [Decimal('0.00100'), {'enabled': False, 'empty': None}]
        },
        backend='provider',
        reservation_sequence=7,
        submitted_at=moment,
        submission_attempts=2,
        pending_response_attempts=(1, 2),
        retry_until=moment + timedelta(hours=1),
        idempotency_scope='account',
        settled_amount=Decimal('1.2300'),
        correlation='correlation',
        reconciliation_required=True,
        conflicting_outcomes=(outcome,),
        recovery_evidence=(evidence,),
        resolutions=(decision,),
    )
    # The actual JSON roundtrip catches accidental storage of Python values.
    encoded = json.loads(json.dumps(dump_record(record)))
    recovered = load_record(encoded, OperationRecord)
    assert recovered == record
    assert recovered.submitted_at.tzname() == 'named-offset'
    assert recovered.resolved_amount.as_tuple() == Decimal('4.5600').as_tuple()
    assert isinstance(recovered.parameters['nested'], tuple)
    assert recovered.idempotency_key == record.idempotency_key
    for name in (
        'pending_response_attempts',
        'recovery_evidence',
        'resolutions',
        'conflicting_outcomes',
    ):
        incomplete = json.loads(json.dumps(encoded))
        del incomplete['value'][2][name]
        with pytest.raises(
            ValueError, match='Invalid durable storage encoding'
        ):
            load_record(incomplete, OperationRecord)


def test_metadata_tags_cannot_impersonate_evidence_and_no_fields_default():
    facts = PaymentFacts(
        'payment',
        Decimal('100.000'),
        provider_data={
            'record': ['decimal', '10'],
            'version': 1,
            'value': {'safe': [1, True, None]},
        },
        observation_conflicts=(
            ObservationConflict(
                'event', '["normalized"]', 'conflicting_identity'
            ),
        ),
    )
    encoded = json.loads(json.dumps(dump_record(facts)))
    assert load_record(encoded, PaymentFacts) == facts
    del encoded['value'][2]['observation_conflicts']
    with pytest.raises(ValueError, match='Invalid durable storage encoding'):
        load_record(encoded, PaymentFacts)


@pytest.mark.parametrize(
    'value',
    [
        Decimal('NaN'),
        Decimal('Infinity'),
        float('inf'),
        object(),
        datetime(2026, 1, 1, tzinfo=UTC).replace(tzinfo=None),
    ],
)
def test_unsupported_values_never_use_lossy_fallback(value):
    facts = PaymentFacts('payment', Decimal(100), provider_data={'bad': value})
    with pytest.raises(ValueError, match='Unsupported or nonfinite'):
        dump_record(facts)
