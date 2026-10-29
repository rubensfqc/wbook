"""Public booking for visitors: /<slug>/horarios/, /<slug>/agendar/, /<slug>/consulta/<uuid>/ and the calendar feed."""

from datetime import timedelta

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST

from apps.clinic.models import Dentist
from apps.core import ics
from apps.core.utils import ip_hash, rate_limited

from . import calendar_links, services, slots
from .forms import VisitorRequestForm
from .models import Appointment


def _live_dentist(slug):
    d = get_object_or_404(Dentist.objects.select_related("landing", "booking", "user"), slug=slug)
    if not d.landing.is_live:
        raise Http404
    return d


def _types(d):
    return d.appointment_types.filter(is_active=True, visitor_bookable=True)


def week_context(d, request):
    types = list(_types(d))
    if not types:
        return {"types": []}
    type_id = request.GET.get("tipo") or request.POST.get("type")
    appt_type = next((t for t in types if str(t.pk) == str(type_id)), types[0])
    week = slots.parse_week(request.GET.get("semana"), d)
    days = slots.week_visible(d, appt_type, week)
    monday = days[0][0]
    today = timezone.localtime(timezone.now(), d.tzinfo).date()
    return {"types": types, "appt_type": appt_type, "days": days, "dentist": d, "this_week": monday,
            "prev_week": (monday - timedelta(days=7)).isoformat(), "next_week": (monday + timedelta(days=7)).isoformat(),
            "can_prev": monday > today - timedelta(days=6), "any_time": any(t for _dd, t in days)}


def times(request, slug):
    d = _live_dentist(slug)
    ctx = week_context(d, request)
    from django.urls import reverse

    ctx["times_url"] = reverse("booking_public:times", args=[slug])
    return render(request, "components/slot_picker.html", ctx)


@require_POST
def request_view(request, slug):
    from django.urls import reverse

    d = _live_dentist(slug)
    form = VisitorRequestForm(request.POST)
    back = reverse("landing_public:page", args=[slug]) + "#agendar"
    if form.data.get("company"):
        return redirect("landing_public:page", slug=slug)  # honeypot: silently ignore
    if not form.is_valid():
        messages.error(request, _("Confira seus dados: ") + "; ".join(f"{form.fields[k].label}: {' '.join(v)}" for k, v in form.errors.items()
                                                                       if k in form.fields))
        return redirect(back)
    if rate_limited(request, f"book-{d.pk}", 5, 3600):
        messages.error(request, _("Muitos pedidos seguidos. Tente de novo mais tarde ou fale pelo WhatsApp."))
        return redirect(back)
    appt_type = get_object_or_404(_types(d), pk=request.POST.get("type"))
    start = parse_datetime(request.POST.get("start", ""))
    c = form.cleaned_data
    try:
        if start is None:
            raise ValidationError(_("Escolha um horário."))
        appt = services.request_booking(d, appt_type, start, name=c["name"], email=c["email"], whatsapp=c["whatsapp"],
                                        message=c["message"], consent=c["consent"], ip_hash=ip_hash(request),
                                        language=request.LANGUAGE_CODE)
    except ValidationError as exc:
        messages.error(request, " ".join(exc.messages))
        return redirect(back)
    return redirect("booking_public:thanks", slug=slug, token=appt.public_token)


def _by_token(slug, token):
    return get_object_or_404(Appointment.objects.select_related("dentist__landing", "dentist__booking", "type", "lead", "patient__user"),
                             public_token=token, dentist__slug=slug)


def thanks(request, slug, token):
    a = _by_token(slug, token)
    return render(request, "agenda/public_thanks.html", {"a": a, "dentist": a.dentist, "links": calendar_links.links_for(a)})


def status(request, slug, token):
    a = _by_token(slug, token)
    return render(request, "agenda/public_status.html", {"a": a, "dentist": a.dentist, "links": calendar_links.links_for(a)})


@require_POST
def cancel(request, slug, token):
    a = _by_token(slug, token)
    try:
        services.cancel(a, by="PATIENT", note=request.POST.get("note", "")[:500])
        messages.success(request, _("Consulta cancelada."))
    except ValidationError as exc:
        messages.error(request, " ".join(exc.messages))
    return redirect("booking_public:status", slug=slug, token=token)


@require_POST
def late_cancel(request, slug, token):
    a = _by_token(slug, token)
    if rate_limited(request, f"late-{a.pk}", 5, 3600):
        messages.error(request, _("Muitas tentativas. Fale com a clínica pelo telefone."))
        return redirect("booking_public:status", slug=slug, token=token)
    try:
        url = services.request_late_cancel(a, note=request.POST.get("note", "")[:500])
    except ValidationError as exc:
        messages.error(request, " ".join(exc.messages))
        return redirect("booking_public:status", slug=slug, token=token)
    if url:
        return redirect(url)
    messages.success(request, _("Avisamos a clínica. Ligue para confirmar o cancelamento."))
    return redirect("booking_public:status", slug=slug, token=token)


def ics_view(request, slug, token):
    a = _by_token(slug, token)
    resp = HttpResponse(calendar_links.ics_bytes(a, cancel=a.status in ("CANCELLED", "REJECTED", "EXPIRED")),
                        content_type="text/calendar; charset=utf-8")
    resp["Content-Disposition"] = 'attachment; filename="consulta.ics"'
    return resp


def feed(request, token):
    d = get_object_or_404(Dentist, calendar_feed_token=token)
    since = timezone.now() - timedelta(days=30)
    until = timezone.now() + timedelta(days=d.booking.booking_horizon_days + 1)
    qs = (Appointment.objects.for_dentist(d).filter(start__gte=since, start__lte=until, status__in=["PENDING", "CONFIRMED", "COMPLETED"])
          .select_related("type", "patient__user", "lead"))
    events = []
    for a in qs:
        ev = calendar_links.event(a, summary=calendar_links.feed_summary(a, d.feed_detail))
        ev["alarm_minutes"] = None
        if d.feed_detail == "BUSY":
            ev["description"] = ""
        events.append(ev)
    resp = HttpResponse(ics.calendar(events, name=f"wbook – {d.clinic_name}"), content_type="text/calendar; charset=utf-8")
    resp["Cache-Control"] = "private, max-age=900"
    return resp
