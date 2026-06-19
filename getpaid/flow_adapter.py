"""Thin sync adapter that delegates to the core PaymentFlow.

Replicates the core flow's orchestration sequence (validate -> processor
call -> FSM -> persist) but splits async processor calls from sync ORM
access, keeping ORM on the main thread for SQLite compatibility.

The core PaymentFlow is used for processor resolution and as the
orchestration reference; this adapter owns the sync/async boundary.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from getpaid.bridge import bridge
from getpaid_core.enums import PaymentEvent, PaymentStatus
from getpaid_core.exceptions import InvalidTransitionError
from getpaid_core.fsm import apply_payment_update
from getpaid_core.types import PaymentUpdate

from getpaid.registry import registry as django_registry
from getpaid.repository import DjangoPaymentRepository


def _resolve_backend_config(
    processor_class,
    backend_key: str,
    *,
    aliases: set[str],
) -> dict:
    """Resolve GETPAID_BACKEND_SETTINGS for a backend path."""
    from django.conf import settings as django_settings

    backend_settings = getattr(
        django_settings, "GETPAID_BACKEND_SETTINGS", {}
    )
    slug = getattr(processor_class, "slug", "")
    class_module = processor_class.__module__

    candidate_keys: list[str] = []
    if slug:
        candidate_keys.extend([slug, f"getpaid.backends.{slug}"])

    candidate_keys.extend(
        key
        for key in (
            backend_key,
            *sorted(aliases),
            class_module,
            f"{class_module}.{processor_class.__name__}",
        )
        if key not in candidate_keys
    )

    if class_module.endswith(".processor"):
        backend_module = class_module.rsplit(".", 1)[0]
        if backend_module not in candidate_keys:
            candidate_keys.append(backend_module)

    for key in candidate_keys:
        if key in backend_settings:
            return backend_settings[key]
    return {}


def _get_processor(payment, model_class):
    """Resolve processor instance using Django registry and config."""
    from importlib import import_module

    backend_key = str(payment.backend)
    if payment.backend in django_registry:
        processor_class = django_registry[backend_key]
        config = _resolve_backend_config(
            processor_class,
            backend_key,
            aliases=django_registry.get_aliases(backend_key),
        )
    else:
        module = import_module(backend_key)
        processor_class = module.PaymentProcessor
        config = _resolve_backend_config(
            processor_class,
            backend_key,
            aliases={backend_key},
        )
    return processor_class(payment, config=config)


def _save(payment, model_class) -> None:
    """Persist via sync repository (main thread)."""
    DjangoPaymentRepository(model_class)._save(payment)


class DjangoPaymentFlowAdapter:
    """Sync adapter over the core PaymentFlow.

    Each method mirrors the core flow's orchestration sequence but
    runs processor calls via the AsyncRunner bridge and ORM on the
    main thread.

    Usage::

        adapter = DjangoPaymentFlowAdapter(payment, PaymentModel)
        result = adapter.charge(amount=Decimal("50.00"))
    """

    def __init__(self, payment, model_class) -> None:
        self.payment = payment
        self.model_class = model_class

    def prepare(self, **kwargs: Any) -> Any:
        """Prepare transaction."""
        processor = _get_processor(self.payment, self.model_class)
        result = bridge.call(processor, processor.prepare_transaction, **kwargs)
        apply_payment_update(
            self.payment,
            PaymentUpdate(
                payment_event=PaymentEvent.PREPARED,
                external_id=result.external_id,
                provider_data=result.provider_data,
            ),
        )
        _save(self.payment, self.model_class)
        return result

    def fetch_status(self):
        """PULL flow: fetch status from gateway."""
        processor = _get_processor(self.payment, self.model_class)
        update = bridge.call(processor, processor.fetch_payment_status)
        if update is not None:
            apply_payment_update(self.payment, update)
            _save(self.payment, self.model_class)
        return update

    def charge(self, amount: Decimal | None = None, **kwargs: Any):
        """Charge a pre-authorized payment."""
        if self.payment.status not in {
            PaymentStatus.PRE_AUTH,
            PaymentStatus.IN_CHARGE,
        }:
            raise InvalidTransitionError(
                f"Cannot charge payment in {self.payment.status!r} status. "
                "Payment must be PRE_AUTH or IN_CHARGE."
            )
        processor = _get_processor(self.payment, self.model_class)
        result = bridge.call(processor, processor.charge, amount=amount, **kwargs)
        if result.success:
            if result.async_call:
                update = PaymentUpdate(
                    payment_event=PaymentEvent.CHARGE_REQUESTED,
                    provider_data=result.provider_data,
                )
            else:
                update = PaymentUpdate(
                    payment_event=PaymentEvent.PAYMENT_CAPTURED,
                    paid_amount=self.payment.amount_paid + result.amount_charged,
                    provider_data=result.provider_data,
                )
            apply_payment_update(self.payment, update)
            _save(self.payment, self.model_class)
        return result

    def release_lock(self, **kwargs: Any) -> Decimal:
        """Release a pre-authorized lock."""
        if self.payment.status != PaymentStatus.PRE_AUTH:
            raise InvalidTransitionError(
                f"Cannot release lock for payment in {self.payment.status!r} "
                "status. Payment must be PRE_AUTH."
            )
        processor = _get_processor(self.payment, self.model_class)
        amount = bridge.call(processor, processor.release_lock, **kwargs)
        apply_payment_update(
            self.payment,
            PaymentUpdate(payment_event=PaymentEvent.LOCK_RELEASED),
        )
        _save(self.payment, self.model_class)
        return amount

    def start_refund(
        self, amount: Decimal | None = None, **kwargs: Any
    ):
        """Start a refund."""
        if self.payment.status not in {
            PaymentStatus.PAID,
            PaymentStatus.PARTIAL,
            PaymentStatus.REFUND_STARTED,
        }:
            raise InvalidTransitionError(
                f"Cannot start refund for payment in {self.payment.status!r} "
                "status. Payment must be PAID, PARTIAL, or REFUND_STARTED."
            )
        processor = _get_processor(self.payment, self.model_class)
        result = bridge.call(
            processor, processor.start_refund, amount=amount, **kwargs
        )
        apply_payment_update(
            self.payment,
            PaymentUpdate(
                payment_event=PaymentEvent.REFUND_REQUESTED,
                provider_data=result.provider_data,
            ),
        )
        _save(self.payment, self.model_class)
        return result

    def cancel_refund(self, **kwargs: Any) -> bool:
        """Cancel an in-progress refund."""
        processor = _get_processor(self.payment, self.model_class)
        success = bridge.call(processor, processor.cancel_refund, **kwargs)
        if success:
            apply_payment_update(
                self.payment,
                PaymentUpdate(payment_event=PaymentEvent.REFUND_CANCELLED),
            )
            _save(self.payment, self.model_class)
        return success


def prepare_transaction(payment, request=None, view=None, **kwargs):
    """Prepare a transaction and build an HTTP response.

    Calls the adapter to run the operation, then constructs
    the appropriate Django response (redirect or POST form).
    """
    from django.core.exceptions import ImproperlyConfigured
    from django.http import HttpResponseRedirect
    from django.template.response import TemplateResponse

    from getpaid_core.enums import BackendMethod

    result = DjangoPaymentFlowAdapter(payment, type(payment)).prepare(
        request=request, view=view, **kwargs
    )
    if isinstance(result, HttpResponseRedirect):
        return result
    if result.method is BackendMethod.POST:
        processor = _get_processor(payment, type(payment))
        if not hasattr(processor, "get_form") or not hasattr(
            processor, "get_template_names"
        ):
            raise ImproperlyConfigured(
                "POST-based payments require a Django-aware processor."
            )
        form = processor.get_form(result.form_data or {})
        return TemplateResponse(
            request=request,
            template=processor.get_template_names(view=view),
            context={
                "form": form,
                "paywall_url": result.redirect_url or "#",
            },
        )
    redirect_url = result.redirect_url or _get_processor(
        payment, type(payment)
    ).get_our_baseurl(request)
    return HttpResponseRedirect(redirect_url)
