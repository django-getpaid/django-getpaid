from django.dispatch import Signal

new_payment_query = Signal(providing_args=['order', 'payment'])
new_payment_query.__doc__ = """
Sent to ask for filling Payment object with additional data:
    payment.amount:			total amount of an order
    payment.currency:		amount currency

This data cannot be filled by ``getpaid`` because it is Order structure
agnostic. After filling values just do return.
"""

user_data_query = Signal(providing_args=['order', 'user_data'])
new_payment_query.__doc__ = """
Sent to ask for filling user additional data:
    user_data['email']:		user email
    user_data['lang']:      lang code in ISO 2-char format

This data cannot be filled by ``getpaid`` because it is Order structure
agnostic. After filling values just do return.
"""

new_payment = Signal(providing_args=['order', 'payment'])
new_payment.__doc__ = """Sent after creating new payment."""


payment_status_changed = Signal(providing_args=['old_status', 'new_status'])
payment_status_changed.__doc__ = """Sent when Payment status changes."""


redirecting_to_payment_gateway_signal = Signal(providing_args=['request', 'order', 'payment', 'backend'])
redirecting_to_payment_gateway_signal.__doc__ = """
Sent just a moment before redirecting. A hook for analytics tools.
"""