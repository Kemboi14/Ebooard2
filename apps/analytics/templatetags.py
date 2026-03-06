from django import template

register = template.Library()

@register.filter
def subtract(value, arg):
    """Subtract arg from value"""
    try:
        return int(value) - int(arg)
    except (ValueError, TypeError):
        return value

@register.filter
def add(value, arg):
    """Add arg to value"""
    try:
        return int(value) + int(arg)
    except (ValueError, TypeError):
        return value
