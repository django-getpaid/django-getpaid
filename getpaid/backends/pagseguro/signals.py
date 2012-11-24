from django.dispatch import Signal

shopping_cart_items_query = Signal(providing_args=['order', 'shopping_cart_items'])
shopping_cart_items_query.__doc__ = """Sent to ask for filling the shopping cart with items"""