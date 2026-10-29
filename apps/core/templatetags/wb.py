"""Template helpers loaded as builtins (no {% load %} needed)."""

from django import template
from django.urls import resolve
from django.utils import formats, timezone
from django.utils.html import format_html
from django.utils.safestring import mark_safe
from django.utils.translation import gettext as _

from apps.core import utils
from apps.core.whatsapp import wa_link as _wa_link

register = template.Library()

# 24x24 stroke icons (Lucide-style paths, MIT)
ICONS = {
    "calendar": '<rect x="3" y="4" width="18" height="18" rx="2"/><path d="M16 2v4M8 2v4M3 10h18"/>',
    "clock": '<circle cx="12" cy="12" r="10"/><path d="M12 6v6l4 2"/>',
    "users": '<path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M22 21v-2a4 4 0 0 0-3-3.87M16 3.13a4 4 0 0 1 0 7.75"/>',
    "user": '<path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/>',
    "home": '<path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/><path d="M9 22V12h6v10"/>',
    "tooth": '<path d="M7 3c-2.5 0-4 2-4 4.5 0 3 1.5 4.5 2 7 .5 3 1 6.5 2.5 6.5S9.5 17 12 17s3 4 4.5 4 2-3.5 2.5-6.5c.5-2.5 2-4 2-7C21 5 19.5 3 17 3c-2 0-3 1-5 1S9 3 7 3z"/>',
    "file": '<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><path d="M14 2v6h6"/>',
    "image": '<rect x="3" y="3" width="18" height="18" rx="2"/><circle cx="9" cy="9" r="2"/><path d="M21 15l-5-5L5 21"/>',
    "receipt": '<path d="M4 2v20l3-2 3 2 3-2 3 2 3-2 1 .5V2l-1 .5-3-2-3 2-3-2-3 2z"/><path d="M8 8h8M8 12h8M8 16h5"/>',
    "quote": '<path d="M9 11H5a2 2 0 0 1-2-2V5h6v6zm0 0c0 4-2 6-5 7M21 11h-4a2 2 0 0 1-2-2V5h6v6zm0 0c0 4-2 6-5 7"/>',
    "inbox": '<path d="M22 12h-6l-2 3h-4l-2-3H2"/><path d="M5.45 5.11L2 12v6a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2v-6l-3.45-6.89A2 2 0 0 0 16.76 4H7.24a2 2 0 0 0-1.79 1.11z"/>',
    "settings": '<circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 1 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 1 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 1 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 1 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"/>',
    "download": '<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4M7 10l5 5 5-5M12 15V3"/>',
    "upload": '<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4M17 8l-5-5-5 5M12 3v12"/>',
    "plus": '<path d="M12 5v14M5 12h14"/>',
    "check": '<path d="M20 6L9 17l-5-5"/>',
    "x": '<path d="M18 6L6 18M6 6l12 12"/>',
    "trash": '<path d="M3 6h18M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6M10 11v6M14 11v6M9 6V4a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v2"/>',
    "edit": '<path d="M12 20h9"/><path d="M16.5 3.5a2.12 2.12 0 0 1 3 3L7 19l-4 1 1-4z"/>',
    "eye": '<path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/>',
    "eye-off": '<path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19M1 1l22 22"/>',
    "phone": '<path d="M22 16.92v3a2 2 0 0 1-2.18 2 19.79 19.79 0 0 1-8.63-3.07 19.5 19.5 0 0 1-6-6A19.79 19.79 0 0 1 2.12 4.18 2 2 0 0 1 4.11 2h3a2 2 0 0 1 2 1.72c.13.96.36 1.9.7 2.81a2 2 0 0 1-.45 2.11L8.09 9.91a16 16 0 0 0 6 6l1.27-1.27a2 2 0 0 1 2.11-.45c.91.34 1.85.57 2.81.7A2 2 0 0 1 22 16.92z"/>',
    "whatsapp": '<path d="M21 11.5a8.38 8.38 0 0 1-.9 3.8 8.5 8.5 0 0 1-7.6 4.7 8.38 8.38 0 0 1-3.8-.9L3 21l1.9-5.7a8.38 8.38 0 0 1-.9-3.8 8.5 8.5 0 0 1 4.7-7.6 8.38 8.38 0 0 1 3.8-.9h.5a8.48 8.48 0 0 1 8 8v.5z"/>',
    "map": '<path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z"/><circle cx="12" cy="10" r="3"/>',
    "mail": '<path d="M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2z"/><path d="M22 6l-10 7L2 6"/>',
    "link": '<path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71"/><path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71"/>',
    "copy": '<rect x="9" y="9" width="13" height="13" rx="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/>',
    "alert": '<path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0zM12 9v4M12 17h.01"/>',
    "chart": '<path d="M18 20V10M12 20V4M6 20v-6"/>',
    "log": '<path d="M8 6h13M8 12h13M8 18h13M3 6h.01M3 12h.01M3 18h.01"/>',
    "database": '<ellipse cx="12" cy="5" rx="9" ry="3"/><path d="M21 12c0 1.66-4 3-9 3s-9-1.34-9-3"/><path d="M3 5v14c0 1.66 4 3 9 3s9-1.34 9-3V5"/>',
    "logout": '<path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4M16 17l5-5-5-5M21 12H9"/>',
    "menu": '<path d="M3 12h18M3 6h18M3 18h18"/>',
    "chevron-left": '<path d="M15 18l-6-6 6-6"/>',
    "chevron-right": '<path d="M9 18l6-6-6-6"/>',
    "external": '<path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6M15 3h6v6M10 14L21 3"/>',
    "refresh": '<path d="M23 4v6h-6M1 20v-6h6"/><path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15"/>',
    "lock": '<rect x="3" y="11" width="18" height="11" rx="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/>',
    "star": '<path d="M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01z"/>',
    "send": '<path d="M22 2L11 13M22 2l-7 20-4-9-9-4z"/>',
    "globe": '<circle cx="12" cy="12" r="10"/><path d="M2 12h20M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"/>',
}


@register.simple_tag
def icon(name, css="h-4 w-4"):
    path = ICONS.get(name, ICONS["file"])
    return mark_safe(
        f'<svg class="{css}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" '
        f'stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">{path}</svg>'
    )


@register.filter
def brl(value):
    return utils.brl(value)


@register.filter
def wa_link(number, text=""):
    return _wa_link(number, text)


@register.filter
def duration(seconds):
    s = int(seconds or 0)
    if s < 60:
        return f"{s}s"
    m, s = divmod(s, 60)
    if m < 60:
        return f"{m}min {s:02d}s"
    h, m = divmod(m, 60)
    return f"{h}h {m:02d}min"


PILL = {
    "PENDING": "pill-amber", "CONFIRMED": "pill-green", "COMPLETED": "pill-sky", "CANCELLED": "pill-gray",
    "REJECTED": "pill-red", "EXPIRED": "pill-gray", "RESCHEDULED": "pill-violet", "NO_SHOW": "pill-red",
    "PLANNED": "pill-gray", "IN_PROGRESS": "pill-brand", "ON_HOLD": "pill-amber",
    "DRAFT": "pill-gray", "SENT": "pill-sky", "VIEWED": "pill-violet", "ACCEPTED": "pill-green", "DECLINED": "pill-red",
    "OPEN": "pill-amber", "PAID": "pill-green",
    "NEW": "pill-sky", "CONTACTED": "pill-violet", "SCHEDULED": "pill-brand", "QUOTE": "pill-amber", "WON": "pill-green", "LOST": "pill-gray",
}


@register.filter
def pill(status):
    return PILL.get(str(status), "pill-gray")


@register.filter
def lines(text):
    return [line.strip() for line in str(text or "").splitlines() if line.strip()]


@register.filter
def get_item(d, key):
    try:
        return d.get(key)
    except AttributeError:
        return None


@register.simple_tag(takes_context=True)
def active(context, prefix):
    request = context.get("request")
    if not request:
        return ""
    try:
        match = resolve(request.path_info)
    except Exception:  # noqa: BLE001
        return ""
    full = f"{match.namespace}:{match.url_name}" if match.namespace else match.url_name
    return "active" if full.startswith(prefix) else ""


def _local(value, dentist=None):
    if value is None:
        return None
    tz = getattr(dentist, "tzinfo", None) if dentist else None
    return timezone.localtime(value, tz) if timezone.is_aware(value) else value


@register.filter
def local_dt(value, dentist=None):
    v = _local(value, dentist)
    if v is None:
        return ""
    return f"{formats.date_format(v, 'l')}, {v:%d/%m/%Y}, {v:%H:%M}"


@register.filter
def local_time(value, dentist=None):
    v = _local(value, dentist)
    return f"{v:%H:%M}" if v else ""


@register.filter
def local_date(value, dentist=None):
    v = _local(value, dentist)
    return f"{v:%d/%m/%Y}" if v else ""


@register.filter
def weekday_long(value):
    return formats.date_format(value, "l")


@register.filter
def mask_cpf(value):
    d = "".join(c for c in str(value or "") if c.isdigit())
    if len(d) != 11:
        return value or ""
    return f"***.{d[3:6]}.***-{d[9:]}"


@register.filter
def yesno_i18n(value):
    return _("sim") if value else _("não")


@register.simple_tag
def pct_bar(value, css="bg-brand-600"):
    v = max(0, min(100, int(value or 0)))
    return format_html(
        '<div class="h-2 w-full rounded-full bg-slate-200"><div class="h-2 rounded-full {}" style="width:{}%"></div></div>', css, v
    )
