# Customization

django-getpaid is designed to be highly customizable. This document covers
the Payment and Order APIs.

## Order API

```{eval-rst}
.. autoclass:: getpaid.abstracts.AbstractOrder
   :members:
```

## Payment API

`AbstractPayment` defines the minimal set of fields expected by the
`BaseProcessor` API. If you want full control, make sure your custom
model provides properties linking your field names to expected names.

```{eval-rst}
.. autoclass:: getpaid.abstracts.AbstractPayment
   :members:
```

### Payment Fields

| Field | Type | Description |
|-------|------|-------------|
| `id` | `UUIDField` | Primary key (UUID to hide volume) |
| `order` | `ForeignKey` | Link to the (swappable) Order model |
| `amount_required` | `DecimalField` | Total amount to pay |
| `currency` | `CharField` | ISO 4217 currency code |
| `status` | `CharField` | Payment status — one of `PaymentStatus` values |
| `backend` | `CharField` | Backend processor identifier |
| `created_on` | `DateTimeField` | Auto-set on creation |
| `last_payment_on` | `DateTimeField` | When payment completed (nullable) |
| `amount_locked` | `DecimalField` | Pre-authorized amount |
| `amount_paid` | `DecimalField` | Actually paid amount |
| `amount_refunded` | `DecimalField` | Refunded amount |
| `external_id` | `CharField` | Payment ID in gateway's system |
| `description` | `CharField` | Payment description (max 128 chars) |
| `fraud_status` | `CharField` | Fraud check result |
| `fraud_message` | `TextField` | Message from fraud check |

### Payment Status

In v3, the `status` field is a plain `CharField` (not an FSMField). The
state machine is attached at runtime using `create_payment_machine()` from
getpaid-core. This means:

- No `django-fsm` dependency
- FSM transitions are enforced at runtime, not at the field level
- Use `payment.may_trigger("confirm_payment")` to check if a transition
  is allowed (replaces `can_proceed()`)

### Custom Payment Model

To provide your own Payment model:

1. Create a model that subclasses `AbstractPayment`
2. Set `GETPAID_PAYMENT_MODEL` in settings before running migrations

```python
# yourapp/models.py
from getpaid.abstracts import AbstractPayment

class CustomPayment(AbstractPayment):
    # Add extra fields
    notes = models.TextField(blank=True)
```

```python
# settings.py
GETPAID_PAYMENT_MODEL = "yourapp.CustomPayment"
```
