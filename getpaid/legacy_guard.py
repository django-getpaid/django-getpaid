"""Ordinary legacy-use refusal, independent of upcoming core APIs.

This is not a cutover lock: stop and drain legacy writers before ownership
changes. Raw SQL/private ORM and already-dispatched provider I/O are outside it.
"""

from django.db import models, router

from getpaid.durable_models import (
    DurablePaymentState,
    DurableStorageReadOnlyError,
)


def _ownership(payment, using):
    """Build a fresh lookup shared by sync and native async entrypoints."""
    if not isinstance(payment, models.Model) or payment.pk is None:
        return None
    configured = DurablePaymentState._meta.get_field(
        'payment'
    ).remote_field.model
    if payment._meta.concrete_model is not configured._meta.concrete_model:
        return None
    alias = (
        using
        or payment._state.db
        or router.db_for_write(type(payment), instance=payment)
    )
    return DurablePaymentState.objects.using(alias).filter(
        payment_id=payment.pk
    )


def require_legacy_payment(payment, *, using=None):
    """Check persisted ownership on the payment alias, never a cached relation."""
    ownership = _ownership(payment, using)
    if ownership is not None and ownership.exists():
        raise DurableStorageReadOnlyError(
            'Durable payment cannot use legacy entrypoints.'
        )


async def arequire_legacy_payment(payment, *, using=None):
    """Native async lookup with the same ownership rules."""
    ownership = _ownership(payment, using)
    if ownership is not None and await ownership.aexists():
        raise DurableStorageReadOnlyError(
            'Durable payment cannot use legacy entrypoints.'
        )
