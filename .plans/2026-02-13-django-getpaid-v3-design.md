# django-getpaid v3 Design

## Goal

Rewrite django-getpaid as a thin adapter over `getpaid-core`, replacing
`django-fsm` with core's `transitions`-based FSM while preserving Django
model/view/form/admin integration.

## Key Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Architecture | Thin adapter over getpaid-core | Thick core, thin adapters (from brainstorming) |
| FSM | Replace django-fsm with core's transitions | Single FSM implementation across all adapters |
| Model swapping | Keep swapper | Backward compatible, proven pattern |
| Backend discovery | AppConfig.ready() + core registry | Backward compatible with existing backends |
| Python/Django | Python 3.12+, Django 5.2+ | Matches current pyproject.toml |
| Async | Sync-first, async optional | Django still primarily sync; use asgiref.async_to_sync |
| Working directory | In-place rewrite | Preserve git history |

## Architecture Overview

```
django-getpaid v3
    │
    ├── Django-specific layer
    │   ├── Models (AbstractOrder, AbstractPayment)
    │   ├── Views (CreatePayment, Callback, Success, Failure)
    │   ├── Forms (PaymentMethodForm)
    │   ├── Admin (PaymentAdmin)
    │   ├── Template tags
    │   ├── URL routing
    │   ├── Settings integration
    │   ├── DjangoPaymentRepository (new)
    │   └── Migrations
    │
    └── getpaid-core (dependency)
        ├── Enums (PaymentStatus, FraudStatus, etc.)
        ├── Types (BuyerInfo, ItemInfo, ChargeResponse, etc.)
        ├── Exceptions (GetPaidException hierarchy)
        ├── Protocols (Order, Payment, PaymentRepository)
        ├── BaseProcessor ABC
        ├── FSM (transitions library)
        ├── PluginRegistry
        ├── Validators (run_validators)
        └── PaymentFlow orchestrator
```

## Model Layer

### AbstractOrder

Minimal changes. Methods already match core's `Order` protocol:
- `get_total_amount()`, `get_buyer_info()`, `get_description()`
- `get_currency()`, `get_items()`, `get_return_url()`

**Removed from model**: `is_ready_for_payment()` — becomes a validator.

### AbstractPayment

Major refactoring:

| v2 (django-fsm) | v3 (getpaid-core) |
|---|---|
| `ConcurrentTransitionMixin` base | Plain `models.Model` |
| `FSMField` for status/fraud_status | `CharField` with choices |
| `@transition` decorators | FSM attached at runtime via `create_payment_machine()` |
| Inline business logic | Delegates to `PaymentFlow` |
| `ALLOWED_CALLBACKS` on model | Imported from `getpaid_core.fsm` |
| `processor` property (lazy) | Processor via `PaymentFlow._get_processor()` |

**Fields preserved** (identical DB schema):
- `id` (UUID PK), `order` (FK), `amount_required`, `currency`
- `status`, `backend`, `created_on`, `last_payment_on`
- `amount_locked`, `amount_paid`, `refunded_on`, `amount_refunded`
- `external_id`, `description`, `fraud_status`, `fraud_message`

**Methods kept on model**:
- `get_unique_id()`, `get_items()`, `get_buyer_info()`
- `is_fully_paid()`, `is_fully_refunded()` (needed by core FSM guards)
- `get_return_redirect_url()` (Django-specific, reads settings)
- `__str__()`, Meta class

**Methods moved to PaymentFlow/views**:
- `charge()`, `release_lock()`, `start_refund()`, `cancel_refund()`
- `confirm_refund()`, `prepare_transaction()`, `handle_paywall_callback()`
- `fetch_and_update_status()`
- All FSM transition methods (attached dynamically by core)

## Repository Pattern

New `getpaid/repository.py`:

```python
class DjangoPaymentRepository:
    """Implements getpaid_core.protocols.PaymentRepository using Django ORM."""

    async def create(self, **kwargs) -> Payment:
        return await sync_to_async(Payment.objects.create)(**kwargs)

    async def save(self, payment) -> Payment:
        await sync_to_async(payment.save)()
        return payment

    async def get_by_id(self, payment_id):
        return await sync_to_async(Payment.objects.get)(pk=payment_id)

    async def update_status(self, payment_id, status, **fields):
        payment = await self.get_by_id(payment_id)
        payment.status = status
        for k, v in fields.items():
            setattr(payment, k, v)
        await sync_to_async(payment.save)()
        return payment

    async def list_by_order(self, order_id):
        return await sync_to_async(list)(
            Payment.objects.filter(order_id=order_id)
        )
```

## Views

Views call `PaymentFlow` methods via `async_to_sync`:

- `CreatePaymentView.form_valid()` → `flow.create_payment()` + `flow.prepare()`
- `CallbackDetailView.post()` → `flow.handle_callback()`
- `SuccessView` / `FailureView` — unchanged

## Settings

Same structure, mapped to core:
- `GETPAID_ORDER_MODEL` → swapper (unchanged)
- `GETPAID_PAYMENT_MODEL` → swapper (unchanged)
- `GETPAID_BACKEND_SETTINGS` → `PaymentFlow(config=...)`
- `GETPAID` → global settings dict

## Registry

`getpaid/registry.py` becomes a re-export:
```python
from getpaid_core.registry import registry
```

Backends still register via `AppConfig.ready()` calling
`registry.register(ProcessorClass)`.

## Dependencies

**Removed**: `django-fsm`
**Added**: `getpaid-core>=0.1.0`
**Kept**: `swapper>=1.4`, `Django>=5.2`

## Migration Strategy

Single migration: `FSMField` → `CharField`. Since `FSMField` is a CharField
subclass, the DB column is already varchar. The migration is a no-op at the
database level but updates Django's field tracking.

## Backward Compatibility

### For users
- Settings format unchanged
- Payment model fields unchanged (same DB schema)
- View URLs unchanged
- Template tags unchanged
- Forms unchanged (same `PaymentMethodForm`)

### Breaking changes
- `payment.processor` property removed (use `PaymentFlow`)
- Direct FSM transition calls on payment removed (use `PaymentFlow`)
- `django-fsm`'s `post_transition` signal no longer fires
  - Replacement: Django's standard `post_save` signal on Payment model
  - Users should check `payment.status` in `post_save` handler

### For backend authors
- Must subclass `getpaid_core.processor.BaseProcessor` instead of `getpaid.processor.BaseProcessor`
- `prepare_transaction()` returns `TransactionResult` dict instead of `HttpResponse`
- `handle_paywall_callback()` → `handle_callback()` (dict + headers instead of HttpRequest)
- Methods are now `async def`

## File Structure (after rewrite)

```
getpaid/
├── __init__.py          # Version, convenience re-exports
├── abstracts.py         # AbstractOrder, AbstractPayment (simplified)
├── models.py            # Concrete Payment (swapper)
├── repository.py        # NEW: DjangoPaymentRepository
├── views.py             # Views using PaymentFlow
├── urls.py              # URL patterns
├── forms.py             # PaymentMethodForm
├── admin.py             # PaymentAdmin
├── apps.py              # GetpaidConfig
├── exceptions.py        # Re-export from core
├── types.py             # Re-export from core
├── status.py            # Compat shim
├── validators.py        # Django-specific validator helpers
├── utils.py             # recursive dict update
├── templatetags/
│   └── getpaid.py       # get_backends tag
├── migrations/
│   └── 0003_...py       # FSMField → CharField
└── backends/
    └── dummy/           # Updated for core
```
