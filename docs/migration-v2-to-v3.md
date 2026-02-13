# Migrating from v2 to v3

django-getpaid v3 is a major rewrite that replaces `django-fsm` with a
framework-agnostic core library (`getpaid-core`). This guide covers all
breaking changes and how to update your code.

## What Changed

| Aspect | v2 | v3 |
|--------|----|----|
| FSM | django-fsm + `FSMField` | `transitions` via getpaid-core, plain `CharField` |
| State checks | `can_proceed(payment.method)` | `payment.may_trigger("method")` |
| Transitions | `@transition` decorators on model | Runtime-attached via `create_payment_machine()` |
| Dependencies | django-fsm, poetry | getpaid-core, uv |
| Python | 3.6+ | 3.12+ |
| Django | 2.2+ | 5.2+ |

## Step-by-Step Migration

### 1. Update dependencies

Remove django-fsm, add getpaid-core:

```bash
# If using pip:
pip install 'django-getpaid>=3.0.0a1'

# If using uv:
uv add 'django-getpaid>=3.0.0a1'
```

django-fsm is no longer needed — uninstall it if nothing else uses it:

```bash
pip uninstall django-fsm
```

### 2. Update INSTALLED_APPS

Remove `django_fsm` if it was in `INSTALLED_APPS`:

```python
INSTALLED_APPS = [
    # ...
    # "django_fsm",  # REMOVE THIS
    "getpaid",
    "getpaid_payu",
]
```

### 3. Run migrations

The v3 package includes migrations that convert `FSMField` to plain
`CharField`. Run:

```bash
./manage.py migrate
```

### 4. Update custom Payment model

If you subclass `AbstractPayment`, remove any django-fsm imports and
decorators:

```python
# BEFORE (v2):
from django_fsm import transition, can_proceed
from getpaid.abstracts import AbstractPayment

class MyPayment(AbstractPayment):
    @transition(field='status', source='new', target='prepared')
    def prepare(self):
        pass

# AFTER (v3):
from getpaid.abstracts import AbstractPayment

class MyPayment(AbstractPayment):
    # No @transition decorators needed.
    # FSM is attached at runtime via create_payment_machine().
    pass
```

### 5. Replace `can_proceed()` with `may_trigger()`

```python
# BEFORE (v2):
from django_fsm import can_proceed

if can_proceed(payment.confirm_payment):
    payment.confirm_payment()

# AFTER (v3):
from getpaid_core.fsm import create_payment_machine

create_payment_machine(payment)
if payment.may_trigger("confirm_payment"):
    payment.confirm_payment()
```

### 6. Update signal handlers

If you used django-fsm signals (`pre_transition`, `post_transition`),
replace them with Django's standard signals:

```python
# BEFORE (v2):
from django_fsm.signals import post_transition

@receiver(post_transition, sender=Payment)
def on_status_change(sender, instance, **kwargs):
    ...

# AFTER (v3):
from django.db.models.signals import post_save

@receiver(post_save, sender=Payment)
def on_payment_save(sender, instance, **kwargs):
    if instance.status == PaymentStatus.PAID:
        ...
```

### 7. Update custom processors

If you wrote a custom payment backend, update the processor:

```python
# BEFORE (v2):
from django_fsm import can_proceed

class PaymentProcessor(BaseProcessor):
    def handle_callback(self, request, **kwargs):
        if can_proceed(self.payment.confirm_payment):
            self.payment.confirm_payment()

# AFTER (v3):
from getpaid_core.fsm import create_payment_machine

class PaymentProcessor(BaseProcessor):
    def handle_paywall_callback(self, request, **kwargs):
        create_payment_machine(self.payment)
        if self.payment.may_trigger("confirm_payment"):
            self.payment.confirm_payment()
```

## Enum Values Are Unchanged

All `PaymentStatus` and `FraudStatus` enum values are identical to v2.
Your database data requires no migration beyond the field type change
(FSMField -> CharField), which preserves all existing values.

| Status | v2 value | v3 value |
|--------|----------|----------|
| `NEW` | `"new"` | `"new"` |
| `PREPARED` | `"prepared"` | `"prepared"` |
| `PRE_AUTH` | `"pre-auth"` | `"pre-auth"` |
| `IN_CHARGE` | `"charge_started"` | `"charge_started"` |
| `PARTIAL` | `"partially_paid"` | `"partially_paid"` |
| `PAID` | `"paid"` | `"paid"` |
| `FAILED` | `"failed"` | `"failed"` |
| `REFUND_STARTED` | `"refund_started"` | `"refund_started"` |
| `REFUNDED` | `"refunded"` | `"refunded"` |
