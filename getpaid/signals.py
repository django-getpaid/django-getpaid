from django.dispatch import Signal

payment_status_changed = Signal(providing_args=["instance", "old_status", "new_status"])
payment_status_changed.__doc__ = """Sent when Payment status changes."""

payment_fraud_changed = Signal(
    providing_args=["instance", "old_status", "new_status", "message"]
)
payment_fraud_changed.__doc__ = """Sent when Payment fraud status changes."""
