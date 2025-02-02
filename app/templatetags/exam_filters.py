from django import template
from django.template.defaultfilters import stringfilter

register = template.Library()

@register.filter
@stringfilter
def filter_logs(logs, action_types):
    """
    Filter logs by action types.
    Usage: {% with filtered_logs=logs|filter_logs:"action1,action2,action3" %}
    """
    try:
        if not logs or not action_types:
            return []
        action_list = [action.strip() for action in action_types.split(',')]
        return [log for log in logs if log.action in action_list]
    except Exception as e:
        print(f"Error in filter_logs: {e}")  # Debug logging
        return []

@register.filter
def divisibleby(value, arg):
    """
    Returns the integer division of value by arg
    """
    try:
        return int(int(value) / int(arg))
    except (ValueError, ZeroDivisionError):
        return 0

@register.filter
def modulo(value, arg):
    """
    Returns the remainder of value divided by arg
    """
    try:
        return int(int(value) % int(arg))
    except (ValueError, ZeroDivisionError):
        return 0 