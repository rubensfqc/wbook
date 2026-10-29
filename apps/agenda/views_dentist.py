"""/app/agenda/ and /app/configuracoes/agenda/."""

from datetime import date, datetime, time, timedelta

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST

from apps.core.activity import log_action
from apps.core.permissions import dentist_required

from . import calendar_links, services, slots
from .forms import BookingSettingsForm, DentistAppointmentForm, FeedForm, HoursFormSet, RescheduleForm, TimeBlockForm, TypeFormSet
from .models import Appointment, TimeBlock

GRID_START, GRID_END = 7, 21


@dentist_required
def agenda_settings(request):
    d = request.dentist
    sform = BookingSettingsForm(request.POST or None, instance=d.booking, prefix="s")
    hours = HoursFormSet(request.POST or None, instance=d, prefix="h")
    types = TypeFormSet(request.POST or None, instance=d, prefix="t")
    if request.method == "POST":
        if sform.is_valid() and hours.is_valid() and types.is_valid():
            sform.save()
            hours.save()
            try:
                types.save()
            except Exception:  # noqa: BLE001 — protected FK (type in use)
                messages.error(request, _("Um tipo com consultas não pode ser apagado; desative-o."))
                return redirect("agenda:settings")
            if not d.onboarding_done:
                d.onboarding_done = True
                d.save(update_fields=["onboarding_done"])
            log_action(request, "settings", "Agenda e regras de agendamento salvas")
            messages.success(request, _("Agenda salva."))
            return redirect("agenda:settings")
        messages.error(request, _("Confira os campos destacados."))
    return render(request, "agenda/settings.html", {"sform": sform, "hours": hours, "types": types})


def _parse_date(value, d):
    try:
        return date.fromisoformat(value)
    except (TypeError, ValueError):
        return timezone.localtime(timezone.now(), d.tzinfo).date()


@dentist_required
def calendar(request):
    d = request.dentist
    view = request.GET.get("vista", "semana")
    day = _parse_date(request.GET.get("data"), d)
    days = [day] if view == "dia" else slots.week_of(day)
    start = datetime.combine(days[0], time(0), tzinfo=d.tzinfo)
    end = datetime.combine(days[-1], time(0), tzinfo=d.tzinfo) + timedelta(days=1)
    appts = (Appointment.objects.for_dentist(d).filter(start__gte=start, start__lt=end)
             .exclude(status__in=["RESCHEDULED", "REJECTED", "EXPIRED", "CANCELLED"]).select_related("type", "patient__user", "lead"))
    blocks = TimeBlock.objects.for_dentist(d).filter(start__lt=end, end__gt=start)
    step = 30
    rows = [(h, m) for h in range(GRID_START, GRID_END) for m in range(0, 60, step)]
    px_per_min = 1.2

    def place(s, e):
        ls, le = timezone.localtime(s, d.tzinfo), timezone.localtime(e, d.tzinfo)
        top = int(max(0, ((ls.hour - GRID_START) * 60 + ls.minute) * px_per_min))
        height = int(max(18, (le - ls).total_seconds() / 60 * px_per_min))
        return top, height, ls.date()

    cols = []
    for dd in days:
        items = []
        for a in appts:
            top, height, ld = place(a.start, a.end)
            if ld == dd:
                items.append({"a": a, "top": top, "height": height})
        bl = []
        for b in blocks:
            ds = datetime.combine(dd, time(GRID_START), tzinfo=d.tzinfo)
            de = datetime.combine(dd, time(GRID_END), tzinfo=d.tzinfo)
            s, e = max(b.start, ds), min(b.end, de)
            if s < e:
                top, height, _ld = place(s, e)
                bl.append({"b": b, "top": top, "height": height})
        hours_today = [(h.start, h.end) for h in d.working_hours.all() if h.weekday == dd.weekday()]
        cols.append({"day": dd, "items": items, "blocks": bl, "open": bool(hours_today), "is_today": dd == timezone.localdate()})
    delta = timedelta(days=1 if view == "dia" else 7)
    return render(request, "agenda/calendar.html", {
        "view": view, "day": day, "cols": cols, "rows": rows, "grid_height": int((GRID_END - GRID_START) * 60 * px_per_min),
        "row_height": int(step * px_per_min), "prev": (day - delta).isoformat(), "next": (day + delta).isoformat(),
        "today": timezone.localdate().isoformat(),
        "pending": Appointment.objects.for_dentist(d).filter(status="PENDING", start__gte=timezone.now()).select_related("type", "lead", "patient__user"),
    })


@dentist_required
def create(request):
    d = request.dentist
    initial = {}
    if request.GET.get("inicio"):
        dt = parse_datetime(request.GET["inicio"])
        if dt:
            initial["start"] = dt
    if request.GET.get("paciente"):
        initial["patient"] = request.GET["paciente"]
    if request.GET.get("tratamento"):
        initial["treatment"] = request.GET["tratamento"]
    form = DentistAppointmentForm(request.POST or None, dentist=d, initial=initial)
    if request.method == "POST" and form.is_valid():
        c = form.cleaned_data
        try:
            a = services.create_by_dentist(d, c["type"], c["start"], patient=c["patient"], treatment=c["treatment"], note=c["note"],
                                           actor=request)
        except ValidationError as exc:
            form.add_error("start", " ".join(exc.messages))
        else:
            messages.success(request, _("Consulta marcada."))
            return redirect(reverse("agenda:calendar") + f"?data={timezone.localtime(a.start, d.tzinfo).date().isoformat()}")
    return render(request, "agenda/create.html", {"form": form})


@dentist_required
def detail(request, pk):
    a = get_object_or_404(Appointment.objects.for_dentist(request.dentist).select_related("type", "patient__user", "lead", "treatment"), pk=pk)
    ctx = {"a": a, "links": calendar_links.links_for(a), "reschedule_form": RescheduleForm(initial={"start": a.start})}
    template = "agenda/_detail_panel.html" if request.headers.get("HX-Request") else "agenda/detail.html"
    return render(request, template, ctx)


@dentist_required
@require_POST
def action(request, pk, action):
    a = get_object_or_404(Appointment.objects.for_dentist(request.dentist), pk=pk)
    try:
        if action == "aprovar":
            services.approve(a, actor=request)
            messages.success(request, _("Consulta confirmada. O paciente foi avisado."))
        elif action == "recusar":
            services.reject(a, reason=request.POST.get("reason", "")[:200], actor=request)
            messages.success(request, _("Pedido recusado. O horário foi liberado."))
        elif action == "cancelar":
            services.cancel(a, by="DENTIST", note=request.POST.get("note", "")[:500], actor=request)
            messages.success(request, _("Consulta cancelada. O paciente foi avisado."))
        elif action == "manter":
            services.keep(a, actor=request)
            messages.success(request, _("Consulta mantida."))
        elif action == "concluir":
            services.complete(a, actor=request)
            messages.success(request, _("Consulta marcada como realizada."))
        elif action == "faltou":
            services.complete(a, no_show=True, actor=request)
            messages.success(request, _("Falta registrada."))
    except ValidationError as exc:
        messages.error(request, " ".join(exc.messages))
    nxt = request.POST.get("next")
    return redirect(nxt if nxt and nxt.startswith("/app/") else reverse("agenda:detail", args=[a.pk]))


@dentist_required
@require_POST
def reschedule(request, pk):
    a = get_object_or_404(Appointment.objects.for_dentist(request.dentist), pk=pk)
    form = RescheduleForm(request.POST)
    if form.is_valid():
        try:
            new = services.reschedule(a, form.cleaned_data["start"], by="DENTIST", actor=request)
            messages.success(request, _("Consulta remarcada. O paciente foi avisado."))
            return redirect("agenda:detail", pk=new.pk)
        except ValidationError as exc:
            messages.error(request, " ".join(exc.messages))
    return redirect("agenda:detail", pk=a.pk)


@dentist_required
def blocks(request):
    d = request.dentist
    form = TimeBlockForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        b = form.save(commit=False)
        b.dentist = d
        b.save()
        log_action(request, "agenda", "Bloqueio criado %(s)s – %(e)s", s=f"{timezone.localtime(b.start):%d/%m %H:%M}",
                   e=f"{timezone.localtime(b.end):%d/%m %H:%M}")
        messages.success(request, _("Horário bloqueado."))
        return redirect("agenda:blocks")
    upcoming = TimeBlock.objects.for_dentist(d).filter(end__gte=timezone.now())
    return render(request, "agenda/blocks.html", {"form": form, "blocks": upcoming})


@dentist_required
@require_POST
def block_delete(request, pk):
    b = get_object_or_404(TimeBlock.objects.for_dentist(request.dentist), pk=pk)
    b.delete()
    log_action(request, "agenda", "Bloqueio removido", level=30)
    messages.success(request, _("Bloqueio removido."))
    return redirect("agenda:blocks")


@dentist_required
def export(request):
    from apps.clinic.views_export import _csv, _xlsx, appointments_rows
    from apps.core import ics

    d = request.dentist
    if not request.GET.get("formato"):
        return render(request, "agenda/export.html", {"statuses": Appointment.Status.choices,
                                                      "default_from": timezone.localdate(), "default_to": timezone.localdate() + timedelta(days=60)})
    start = _parse_date(request.GET.get("de"), d)
    end = _parse_date(request.GET.get("ate"), d) if request.GET.get("ate") else start + timedelta(days=60)
    statuses = request.GET.getlist("status") or ["PENDING", "CONFIRMED", "COMPLETED"]
    fmt = request.GET.get("formato")
    log_action(request, "export", "Agenda exportada (%(f)s, %(a)s a %(b)s)", f=fmt, a=start, b=end)
    if fmt == "ics":
        qs = (Appointment.objects.for_dentist(d).filter(start__date__gte=start, start__date__lte=end, status__in=statuses)
              .select_related("type", "patient__user", "lead"))
        events = [calendar_links.event(a, summary=calendar_links.feed_summary(a, "FULL_NAME")) for a in qs]
        resp = HttpResponse(ics.calendar(events, name=d.clinic_name), content_type="text/calendar; charset=utf-8")
        resp["Content-Disposition"] = f'attachment; filename="agenda-{d.slug}.ics"'
        return resp
    header, rows = appointments_rows(d, start, end, statuses)
    name = f"agenda-{d.slug}-{start:%Y%m%d}"
    return _xlsx(name, header, rows) if fmt == "xlsx" else _csv(name, header, rows)


@dentist_required
def sync(request):
    d = request.dentist
    form = FeedForm(request.POST or None, instance=d)
    if request.method == "POST" and form.is_valid():
        form.save()
        log_action(request, "settings", "Detalhe do calendário sincronizado: %(v)s", v=d.feed_detail)
        messages.success(request, _("Preferência salva."))
        return redirect("agenda:sync")
    return render(request, "agenda/sync.html", {"form": form, "links": calendar_links.subscription_links(d)})


@dentist_required
@require_POST
def sync_rotate(request):
    import uuid

    d = request.dentist
    d.calendar_feed_token = uuid.uuid4()
    d.save(update_fields=["calendar_feed_token"])
    log_action(request, "settings", "Novo link do calendário sincronizado gerado", level=30)
    messages.success(request, _("Novo link gerado. O link antigo parou de funcionar; assine o novo no seu calendário."))
    return redirect("agenda:sync")

