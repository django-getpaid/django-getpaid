"""Versioned, tagged JSON for normalized core values, never object deserialization.

Only explicitly named record types/fields and finite scalar values are accepted.
Tags occur outside user mappings, so metadata cannot impersonate a typed value.
Unknown versions/fields fail closed rather than erase retained evidence.
"""

import math
from collections.abc import Mapping
from dataclasses import fields
from datetime import datetime
from decimal import Decimal
from enum import Enum

from getpaid_core.durable import ObservationConflict, PaymentFacts
from getpaid_core.enums import FraudStatus, PaymentStatus

_RECORDS = {
    'PaymentFacts': (
        PaymentFacts,
        'payment_id amount_required backend captured_funds refunded_funds remaining_authorization status external_id fraud_status fraud_message reconciliation_required provider_data observation_conflicts',
    ),
    'ObservationConflict': (
        ObservationConflict,
        'event_identity semantic_content reason',
    ),
}
_ENUMS = {cls.__name__: cls for cls in (PaymentStatus, FraudStatus)}


def encode(value):
    """Encode a complete supported value with no fallback or repr coercion."""
    if isinstance(value, Enum):
        if _ENUMS.get(type(value).__name__) is not type(value):
            raise ValueError('Unsupported enum in durable storage.')
        return ['enum', type(value).__name__, value.value]
    if value is None or type(value) in (bool, int, str):
        return ['scalar', value]
    if type(value) is float and math.isfinite(value):
        return ['scalar', value]
    if type(value) is Decimal and value.is_finite():
        return ['decimal', str(value)]
    if type(value) is datetime and value.utcoffset() is not None:
        return ['datetime', value.isoformat(), value.fold]
    if isinstance(value, Mapping):
        if any(type(key) is not str for key in value):
            raise ValueError('Durable mapping keys must be strings.')
        return ['mapping', [[key, encode(item)] for key, item in value.items()]]
    if type(value) in (tuple, list):
        return [type(value).__name__, [encode(item) for item in value]]
    definition = _RECORDS.get(type(value).__name__)
    if definition is not None and definition[0] is type(value):
        names = definition[1].split()
        if set(names) != {field.name for field in fields(value)}:
            raise ValueError(
                'Core record schema changed; upgrade storage codec.'
            )
        return [
            'record',
            type(value).__name__,
            {name: encode(getattr(value, name)) for name in names},
        ]
    raise ValueError('Unsupported or nonfinite value in durable storage.')


def decode(value):
    """Read only this codec's allowlisted tagged tree."""
    tag, *parts = value
    if tag == 'scalar' and len(parts) == 1:
        result = parts[0]
        if (
            result is None
            or type(result) in (str, bool, int)
            or (type(result) is float and math.isfinite(result))
        ):
            return result
    if tag == 'decimal' and len(parts) == 1:
        result = Decimal(parts[0])
        if result.is_finite():
            return result
    if tag == 'datetime' and len(parts) == 2:
        result = datetime.fromisoformat(parts[0]).replace(fold=parts[1])
        if result.utcoffset() is not None:
            return result
    if tag == 'enum' and len(parts) == 2:
        return _ENUMS[parts[0]](parts[1])
    if tag == 'mapping' and len(parts) == 1:
        result = {key: decode(item) for key, item in parts[0]}
        if len(result) == len(parts[0]) and all(
            type(key) is str for key in result
        ):
            return result
    if tag in ('tuple', 'list') and len(parts) == 1:
        items = [decode(item) for item in parts[0]]
        return tuple(items) if tag == 'tuple' else items
    if tag == 'record' and len(parts) == 2:
        cls, names = _RECORDS[parts[0]]
        if set(parts[1]) == set(names.split()):
            return cls(**{key: decode(item) for key, item in parts[1].items()})
    raise ValueError('Invalid durable storage encoding.')


def dump_record(record):
    return {'version': 1, 'value': encode(record)}


def load_record(payload, expected_type):
    if set(payload) != {'version', 'value'} or payload['version'] != 1:
        raise ValueError('Unsupported durable storage version.')
    value = decode(payload['value'])
    if type(value) is not expected_type:
        raise ValueError('Unexpected durable record type.')
    return value
