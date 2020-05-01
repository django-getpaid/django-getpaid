from django import template

from getpaid.registry import registry

register = template.Library()


@register.simple_tag
def get_backends(currency):
    """
    Get all backends supporting given currency into template's context in raw form.
    This way you can use all fields to render backend chooser.
    """
    return registry.get_backends(currency)
