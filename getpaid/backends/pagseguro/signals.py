from django.dispatch import Signal

shopping_cart_items_query = Signal(providing_args=['order', 'shopping_cart_items'])
shopping_cart_items_query.__doc__ = """
Sent to ask for filling the shopping cart with items.
shopping_cart_items should be an array of dictionaries, with each entry being an item
containing at least the following keys: id, description, quantity and value. Optional
keys are weight and shipping.

example:
    item = {
        'id': 1,
        'description': order.__unicode__(),
        'quantity': 1,
        'value': order.total,
    }
    shopping_cart_items.append(item)
"""