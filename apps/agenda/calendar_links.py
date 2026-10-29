"""Add-to-calendar links, .ics building and WhatsApp share text (one way: wbook → calendars)."""

from urllib.parse import urlencode

from django.urls import reverse
from django.utils import formats, timezone
from django.utils.translation import gettext as _

from apps.core import ics
from apps.core.emails import absolute
from apps.core.whatsapp import wa_share


def _gdate(dt):
    from datetime import UTC

    return dt.astimezone(UTC).strftime("%Y%m%dT%H%M%SZ")


def _iso(dt):
    from datetime import UTC

    return dt.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def title(appt):
    return f"{appt.type.name} — {appt.dentist.name}"


def page_url(appt):
    if appt.patient_id:
        return absolute(reverse("patient:appointments"))
    return absolute(reverse("booking_public:status", args=[appt.dentist.slug, appt.public_token]))


def ics_url(appt):
    if appt.patient_id:
        return absolute(reverse("patient:appointment_ics", args=[appt.pk]))
    return absolute(reverse("booking_public:ics", args=[appt.dentist.slug, appt.public_token]))


def details(appt):
    d = appt.dentist
    bits = [d.clinic_name]
    if d.contact_phone:
        bits.append(_("Telefone: %(p)s") % {"p": d.contact_phone})
    bits.append(page_url(appt))
    return "\n".join(bits)


def when_text(appt):
    s = timezone.localtime(appt.start, appt.dentist.tzinfo)
    e = timezone.localtime(appt.end, appt.dentist.tzinfo)
    weekday = formats.date_format(s, "l")
    return _("%(weekday)s, %(date)s, das %(start)s às %(end)s") % {
        "weekday": weekday.capitalize(), "date": f"{s:%d/%m/%Y}", "start": f"{s:%H:%M}", "end": f"{e:%H:%M}"
    }


def google_link(appt):
    q = {
        "action": "TEMPLATE",
        "text": title(appt),
        "dates": f"{_gdate(appt.start)}/{_gdate(appt.end)}",
        "details": details(appt),
        "location": appt.dentist.full_address,
    }
    return "https://calendar.google.com/calendar/render?" + urlencode(q)


def _outlook(base, appt):
    q = {
        "path": "/calendar/action/compose",
        "rru": "addevent",
        "subject": title(appt),
        "startdt": _iso(appt.start),
        "enddt": _iso(appt.end),
        "body": details(appt),
        "location": appt.dentist.full_address,
    }
    return f"{base}/calendar/0/deeplink/compose?" + urlencode(q)


def share_text(appt):
    status = _("Consulta confirmada") if appt.status == "CONFIRMED" else _("Consulta solicitada")
    lines = [
        _("%(status)s: %(type)s com %(dentist)s") % {"status": status, "type": appt.type.name, "dentist": appt.dentist.name},
        when_text(appt),
    ]
    if appt.dentist.full_address:
        lines.append(appt.dentist.full_address)
    lines.append(_("Adicionar à agenda: %(url)s") % {"url": google_link(appt)})
    return "\n".join(lines)


def links_for(appt):
    return {
        "google": google_link(appt),
        "outlook": _outlook("https://outlook.live.com", appt),
        "office": _outlook("https://outlook.office.com", appt),
        "ics": ics_url(appt),
        "whatsapp": wa_share(share_text(appt)),
    }


STATUS_MAP = {"CONFIRMED": "CONFIRMED", "PENDING": "TENTATIVE", "COMPLETED": "CONFIRMED"}


def event(appt, summary=None):
    return {
        "uid": appt.ics_uid,
        "sequence": appt.ics_sequence,
        "start": appt.start,
        "end": appt.end,
        "summary": summary or title(appt),
        "location": appt.dentist.full_address,
        "description": details(appt),
        "url": page_url(appt),
        "status": STATUS_MAP.get(appt.status, "CANCELLED"),
        "alarm_minutes": 120,
    }


def ics_bytes(appt, cancel=False):
    ev = event(appt)
    if cancel:
        ev["status"] = "CANCELLED"
    return ics.calendar([ev], method="CANCEL" if cancel else "PUBLISH")


def ics_attachment(appt, cancel=False):
    return [("consulta.ics", ics_bytes(appt, cancel=cancel), "text/calendar; charset=utf-8")]


def feed_summary(appt, detail):
    if detail == "BUSY":
        return _("Ocupado")
    name = appt.person_name if detail == "FULL_NAME" else appt.person_first_name
    prefix = _("[Pendente] ") if appt.status == "PENDING" else ""
    return f"{prefix}{name} — {appt.type.name}"


def subscription_links(dentist):
    from urllib.parse import quote

    https_url = absolute(reverse("agenda_feed:feed", args=[dentist.calendar_feed_token]))
    webcal = "webcal://" + https_url.split("://", 1)[1]
    name = f"wbook – {dentist.clinic_name}"
    return {
        "url": https_url,
        "webcal": webcal,
        "google": "https://calendar.google.com/calendar/r?cid=" + quote(webcal, safe=""),
        "outlook": "https://outlook.live.com/calendar/0/addfromweb?" + urlencode({"url": https_url, "name": name}),
        "office": "https://outlook.office.com/calendar/0/addfromweb?" + urlencode({"url": https_url, "name": name}),
    }
