import zoneinfo

from django import template
from django.utils import timezone as dj_tz

register = template.Library()


def _get_user_tz(context):
    """Extract the logged-in user's ZoneInfo from template context."""
    request = context.get("request")
    if request and hasattr(request, "user") and request.user.is_authenticated:
        return request.user.get_timezone()
    return zoneinfo.ZoneInfo("Africa/Nairobi")


@register.filter(name="localtime")
def localtime_filter(dt, user=None):
    """
    Convert a UTC-aware datetime to the given user's preferred timezone.

    Usage in templates:
        {{ meeting.scheduled_date|localtime:request.user }}

    Falls back to Africa/Nairobi if user is None or unauthenticated.
    """
    if dt is None:
        return ""
    if dj_tz.is_naive(dt):
        dt = dj_tz.make_aware(dt, zoneinfo.ZoneInfo("UTC"))
    if user and hasattr(user, "get_timezone"):
        tz = user.get_timezone()
    else:
        tz = zoneinfo.ZoneInfo("Africa/Nairobi")
    return dt.astimezone(tz)


@register.filter(name="tz_abbr")
def tz_abbr(dt, user=None):
    """
    Return the timezone abbreviation for a datetime in the user's timezone.
    e.g. "EAT", "MUT", "WAT"

    Usage:
        {{ meeting.scheduled_date|localtime:request.user|tz_abbr:request.user }}
    """
    if dt is None:
        return ""
    if user and hasattr(user, "get_timezone"):
        tz = user.get_timezone()
    else:
        tz = zoneinfo.ZoneInfo("Africa/Nairobi")
    if dj_tz.is_naive(dt):
        dt = dj_tz.make_aware(dt, zoneinfo.ZoneInfo("UTC"))
    local_dt = dt.astimezone(tz)
    return local_dt.strftime("%Z")


@register.simple_tag(takes_context=True)
def meeting_time(context, dt, fmt="%d %b %Y, %I:%M %p"):
    """
    Render a meeting datetime in the current user's local timezone,
    with timezone abbreviation appended.

    Usage:
        {% meeting_time meeting.scheduled_date %}
        {% meeting_time meeting.scheduled_date fmt="%H:%M" %}

    Output example:
        "12 Jun 2025, 10:00 AM EAT"   (Kenya/Uganda member)
        "12 Jun 2025, 11:00 AM MUT"   (Mauritius member)
    """
    if dt is None:
        return ""
    tz = _get_user_tz(context)
    if dj_tz.is_naive(dt):
        dt = dj_tz.make_aware(dt, zoneinfo.ZoneInfo("UTC"))
    local_dt = dt.astimezone(tz)
    abbr = local_dt.strftime("%Z")
    return f"{local_dt.strftime(fmt)} {abbr}"


@register.simple_tag(takes_context=True)
def meeting_time_range(context, start, end, date_fmt="%d %b %Y", time_fmt="%I:%M %p"):
    """
    Render a start–end time range for a meeting in the user's local timezone.

    Usage:
        {% meeting_time_range meeting.scheduled_date meeting.scheduled_end_time %}

    Output example:
        "12 Jun 2025 · 10:00 AM – 12:00 PM EAT"
        "12 Jun 2025 · 11:00 AM – 01:00 PM MUT"
    """
    if start is None:
        return ""
    tz = _get_user_tz(context)
    if dj_tz.is_naive(start):
        start = dj_tz.make_aware(start, zoneinfo.ZoneInfo("UTC"))
    local_start = start.astimezone(tz)
    abbr = local_start.strftime("%Z")

    date_str = local_start.strftime(date_fmt)
    start_str = local_start.strftime(time_fmt)

    if end:
        if dj_tz.is_naive(end):
            end = dj_tz.make_aware(end, zoneinfo.ZoneInfo("UTC"))
        local_end = end.astimezone(tz)
        end_str = local_end.strftime(time_fmt)
        return f"{date_str} · {start_str} – {end_str} {abbr}"

    return f"{date_str} · {start_str} {abbr}"


@register.simple_tag(takes_context=True)
def user_timezone_label(context):
    """
    Render the current user's timezone name and offset for display.

    Usage:
        {% user_timezone_label %}

    Output example:
        "Indian/Mauritius (UTC+4)"
        "Africa/Nairobi (UTC+3)"
    """
    tz = _get_user_tz(context)
    now = dj_tz.now().astimezone(tz)
    offset = now.strftime("%z")  # e.g. "+0300" or "+0400"
    # Format as UTC+3 or UTC+4
    sign = offset[0]
    hours = int(offset[1:3])
    mins = int(offset[3:5])
    if mins:
        offset_str = f"UTC{sign}{hours}:{mins:02d}"
    else:
        offset_str = f"UTC{sign}{hours}"
    return f"{tz.key} ({offset_str})"


@register.inclusion_tag("meetings/partials/timezone_notice.html", takes_context=True)
def timezone_notice(context, branch_tz_name="Africa/Nairobi"):
    """
    Render a small notice when the user's timezone differs from the meeting's
    branch timezone.

    Usage (in meeting detail template):
        {% timezone_notice meeting.branch.timezone_name %}
    """
    user_tz = _get_user_tz(context)
    try:
        branch_tz = zoneinfo.ZoneInfo(branch_tz_name or "Africa/Nairobi")
    except Exception:
        branch_tz = zoneinfo.ZoneInfo("Africa/Nairobi")

    now = dj_tz.now()
    user_offset = now.astimezone(user_tz).utcoffset()
    branch_offset = now.astimezone(branch_tz).utcoffset()
    differs = user_offset != branch_offset

    def _fmt_offset(tz):
        offset = now.astimezone(tz).strftime("%z")
        sign = offset[0]
        h = int(offset[1:3])
        m = int(offset[3:5])
        return f"UTC{sign}{h}:{m:02d}" if m else f"UTC{sign}{h}"

    return {
        "differs": differs,
        "user_tz_name": user_tz.key,
        "user_tz_offset": _fmt_offset(user_tz),
        "branch_tz_name": branch_tz.key,
        "branch_tz_offset": _fmt_offset(branch_tz),
    }
