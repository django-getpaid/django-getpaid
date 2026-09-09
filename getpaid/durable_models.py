"""Durable storage, deliberately independent of unreleased core imports.

Public ORM access is read-only. Only the repository's private writer commits
planner results; raw SQL and private ORM internals are not a security boundary.
"""

import swapper
from django.db import models


class DurableStorageReadOnlyError(TypeError):
    """Use semantic repository methods, not arbitrary persistence."""


def _refuse_write(*args, **kwargs):
    raise DurableStorageReadOnlyError('Use DjangoDurablePaymentRepository.')


class DurableQuerySet(models.QuerySet):
    create = _refuse_write
    update = _refuse_write
    delete = _refuse_write
    bulk_create = _refuse_write
    bulk_update = _refuse_write
    get_or_create = _refuse_write
    update_or_create = _refuse_write


class DurableStorageModel(models.Model):
    # Django installs as_manager as a classmethod dynamically.
    objects = DurableQuerySet.as_manager()  # ty: ignore[missing-argument]
    save = _refuse_write
    save_base = _refuse_write
    delete = _refuse_write

    class Meta:
        abstract = True
        base_manager_name = 'objects'


class DurablePaymentState(DurableStorageModel):
    """Authoritative facts; legacy payment financial fields are retired snapshots."""

    payment = models.OneToOneField(
        swapper.get_model_name('getpaid', 'Payment'),
        on_delete=models.PROTECT,
        related_name='durable_state',
    )
    facts = models.JSONField()
    reconciliation_required = models.BooleanField(db_index=True)


class DurableOperation(DurableStorageModel):
    """Planner-controlled projection including complete retained audit/evidence."""

    payment = models.ForeignKey(DurablePaymentState, on_delete=models.PROTECT)
    operation_id = models.TextField()
    record = models.JSONField()
    unresolved = models.BooleanField(db_index=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=('payment', 'operation_id'),
                name='getpaid_durable_operation_identity',
            )
        ]


class DurableReplay(DurableStorageModel):
    """Immutable replay evidence, never upserted or stored in provider metadata."""

    payment = models.ForeignKey(DurablePaymentState, on_delete=models.PROTECT)
    backend = models.TextField()
    event_identity = models.TextField()
    content_digest = models.CharField(max_length=64)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=('payment', 'backend', 'event_identity'),
                name='getpaid_durable_replay_identity',
            )
        ]
