from django import template
from django.utils import timezone

register = template.Library()


@register.filter
def relative_time(value):
    now = timezone.now()
    diff = now - value

    if diff.days == 0:
        hours = diff.seconds // 3600
        if hours > 0:
            return f"{hours} hour{'s' if hours != 1 else ''} ago"
        minutes = diff.seconds // 60
        if minutes > 0:
            return f"{minutes} minute{'s' if minutes != 1 else ''} ago"
        return "Just now"

    if diff.days == 1:
        return "Yesterday"

    if diff.days < 7:
        return f"{diff.days} days ago"

    return value.strftime("%d %b %Y")