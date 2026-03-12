from django import template

register = template.Library()


@register.filter
def lookup(obj, key):
    """
    Look up a value in a dict by key.
    Usage: {{ my_dict|lookup:key }}
    """
    if obj is None:
        return None
    if isinstance(obj, dict):
        return obj.get(key)
    try:
        return obj[key]
    except (KeyError, IndexError, TypeError):
        return None
