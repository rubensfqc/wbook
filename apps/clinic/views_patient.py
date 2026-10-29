"""Patient portal: /paciente/."""

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST

from apps.agenda import calendar_links, services, slots
from apps.agenda.models import Appointment
from apps.core.activity import log_action
from apps.core.emails import absolute
from apps.core.notifications import notify_dentist
from apps.core.permissions import patient_required

from .forms import MessageForm, PatientSettingsForm
from .models import Invoice, Treatment, TreatmentEntry, TreatmentFile


@patient_required
def dashboard(request):
    p = request.patient
    now = timezone.now()
    upcoming = Appointment.objects.for_patient(p).filter(status__in=Appointment.BLOCKING_STATUSES, start__gte=now).select_related("type")
    from apps.quotes.models import Quote

    return render(request, "patient/dashboard.html", {
        "upcoming": upcoming,
        "next": upcoming.first(),
        "treatments": Treatment.objects.for_patient(p),
        "invoices": Invoice.objects.for_patient(p).filter(status="OPEN"),
        "quotes": Quote.objects.for_patient(p),
    })


def _types(dentist):
    return dentist.appointment_types.filter(is_active=True)


@patient_required
def book(request):
    d = request.dentist
    types = list(_types(d))
    if not types:
        messages.info(request, _("A agenda online ainda não está aberta. Fale com a clínica."))
        return redirect("patient:dashboard")
    reschedule_of = None
    if request.GET.get("remarcar"):
        reschedule_of = get_object_or_404(Appointment.objects.for_patient(request.patient), pk=request.GET["remarcar"])
    type_id = request.GET.get("tipo") or (reschedule_of.type_id if reschedule_of else types[0].pk)
    appt_type = next((t for t in types if str(t.pk) == str(type_id)), types[0])
    week = slots.parse_week(request.GET.get("semana"), d)
    ctx = _week_ctx(d, appt_type, week, exclude=reschedule_of)
    ctx.update({"types": types, "appt_type": appt_type, "reschedule_of": reschedule_of,
                "times_url": reverse("patient:book_times")})
    if request.headers.get("HX-Request"):
        return render(request, "components/slot_picker.html", ctx)
    return render(request, "patient/book.html", ctx)


def _week_ctx(dentist, appt_type, week, exclude=None):
    from datetime import timedelta

    days = slots.week_visible(dentist, appt_type, week, exclude=exclude)
    monday = days[0][0]
    return {"days": days, "prev_week": (monday - timedelta(days=7)).isoformat(), "next_week": (monday + timedelta(days=7)).isoformat(),
            "this_week": monday, "dentist": dentist,
            "can_prev": monday > timezone.localtime(timezone.now(), dentist.tzinfo).date() - timedelta(days=6)}


@patient_required
def book_times(request):
    return book(request)


@patient_required
@require_POST
def book_confirm(request):
    p = request.patient
    d = request.dentist
    appt_type = get_object_or_404(_types(d), pk=request.POST.get("type"))
    start = parse_datetime(request.POST.get("start", ""))
    resched = request.POST.get("reschedule_of")
    try:
        if start is None:
            raise ValidationError(_("Escolha um horário."))
        if resched:
            old = get_object_or_404(Appointment.objects.for_patient(p), pk=resched)
            appt = services.reschedule(old, start, by="PATIENT", actor=request)
            messages.success(request, _("Consulta remarcada."))
        else:
            appt = services.book(p, appt_type, start, note=request.POST.get("note", "")[:1000], actor=request)
            if appt.status == "CONFIRMED":
                messages.success(request, _("Consulta confirmada!"))
            else:
                messages.success(request, _("Pedido enviado. A clínica vai confirmar por e-mail."))
    except ValidationError as exc:
        messages.error(request, " ".join(exc.messages))
        return redirect(reverse("patient:book") + (f"?remarcar={resched}" if resched else ""))
    return redirect("patient:appointment", pk=appt.pk)


@patient_required
def appointments(request):
    qs = Appointment.objects.for_patient(request.patient).select_related("type").exclude(status="RESCHEDULED")
    now = timezone.now()
    return render(request, "patient/appointments.html", {
        "upcoming": qs.filter(start__gte=now, status__in=Appointment.BLOCKING_STATUSES),
        "history": qs.exclude(start__gte=now, status__in=Appointment.BLOCKING_STATUSES).order_by("-start")[:50],
    })


@patient_required
def appointment(request, pk):
    a = get_object_or_404(Appointment.objects.for_patient(request.patient).select_related("type", "dentist"), pk=pk)
    return render(request, "patient/appointment.html", {"a": a, "links": calendar_links.links_for(a)})


@patient_required
@require_POST
def appointment_cancel(request, pk):
    a = get_object_or_404(Appointment.objects.for_patient(request.patient), pk=pk)
    try:
        services.cancel(a, by="PATIENT", note=request.POST.get("note", "")[:500], actor=request)
        messages.success(request, _("Consulta cancelada."))
    except ValidationError as exc:
        messages.error(request, " ".join(exc.messages))
    return redirect("patient:appointment", pk=a.pk)


@patient_required
@require_POST
def appointment_late_cancel(request, pk):
    from apps.core.utils import rate_limited

    a = get_object_or_404(Appointment.objects.for_patient(request.patient), pk=pk)
    if rate_limited(request, f"late-{a.pk}", 5, 3600):
        messages.error(request, _("Muitas tentativas. Fale com a clínica pelo telefone."))
        return redirect("patient:appointment", pk=a.pk)
    try:
        url = services.request_late_cancel(a, note=request.POST.get("note", "")[:500], actor=request)
    except ValidationError as exc:
        messages.error(request, " ".join(exc.messages))
        return redirect("patient:appointment", pk=a.pk)
    if url:
        return redirect(url)
    messages.success(request, _("Avisamos a clínica. Ligue para confirmar o cancelamento."))
    return redirect("patient:appointment", pk=a.pk)


@patient_required
def appointment_ics(request, pk):
    a = get_object_or_404(Appointment.objects.for_patient(request.patient), pk=pk)
    resp = HttpResponse(calendar_links.ics_bytes(a, cancel=a.status in ("CANCELLED", "REJECTED", "EXPIRED")),
                        content_type="text/calendar; charset=utf-8")
    resp["Content-Disposition"] = 'attachment; filename="consulta.ics"'
    return resp


@patient_required
def appointments_ics(request):
    from apps.core import ics

    qs = Appointment.objects.for_patient(request.patient).filter(status__in=Appointment.BLOCKING_STATUSES,
                                                                 start__gte=timezone.now()).select_related("type", "dentist")
    resp = HttpResponse(ics.calendar([calendar_links.event(a) for a in qs]), content_type="text/calendar; charset=utf-8")
    resp["Content-Disposition"] = 'attachment; filename="minhas-consultas.ics"'
    return resp


@patient_required
def treatment(request, pk):
    t = get_object_or_404(Treatment.objects.for_patient(request.patient), pk=pk)
    files = list(TreatmentFile.objects.for_patient(request.patient).filter(treatment=t))
    return render(request, "patient/treatment.html", {
        "t": t,
        "photos": [f for f in files if f.is_photo],
        "docs": [f for f in files if not f.is_photo],
        "phases": TreatmentFile.Phase.choices,
        "entries": t.entries.select_related("author"),
        "sessions": t.appointments.exclude(status="RESCHEDULED").select_related("type").order_by("start"),
        "invoices": Invoice.objects.for_patient(request.patient).filter(treatment=t),
        "message_form": MessageForm(),
    })


@patient_required
@require_POST
def treatment_message(request, pk):
    t = get_object_or_404(Treatment.objects.for_patient(request.patient), pk=pk)
    form = MessageForm(request.POST)
    if form.is_valid():
        TreatmentEntry.objects.create(treatment=t, author=request.user, author_role="PATIENT", text=form.cleaned_data["text"])
        log_action(request, "treatment", "Mensagem do paciente no tratamento #%(t)s", t=t.pk)
        notify_dentist(t.dentist, "alert_patient_message", f"{request.patient.name}: {t.title}",
                       "dentist_treatment_message",
                       {"treatment": t, "patient": request.patient, "text": form.cleaned_data["text"],
                        "link": absolute(reverse("clinic:treatment_detail", args=[t.pk]))}, reply_to=request.user.email)
        messages.success(request, _("Mensagem enviada."))
    return redirect(reverse("patient:treatment", args=[t.pk]) + "#timeline")


@patient_required
def invoice(request, pk):
    inv = get_object_or_404(Invoice.objects.for_patient(request.patient).select_related("treatment"), pk=pk)
    return render(request, "patient/invoice.html", {"inv": inv})


@patient_required
@require_POST
def invoice_paid(request, pk):
    from django.utils.translation import gettext_lazy as _l

    inv = get_object_or_404(Invoice.objects.for_patient(request.patient), pk=pk)
    if inv.status == "OPEN" and not inv.patient_notified_paid_at:
        inv.patient_notified_paid_at = timezone.now()
        inv.save(update_fields=["patient_notified_paid_at"])
        log_action(request, "invoice", "Paciente avisou pagamento da fatura %(n)s", n=inv.display_number)
        notify_dentist(inv.dentist, "alert_invoice_paid",
                       (_l("%(p)s avisou que pagou a fatura %(n)s"), {"p": request.patient.name, "n": inv.display_number}),
                       "invoice_patient_paid", {"invoice": inv, "link": absolute(reverse("clinic:invoice_detail", args=[inv.pk]))})
    messages.success(request, _("Obrigado! Avisamos a clínica."))
    return redirect("patient:invoice", pk=inv.pk)


@patient_required
def my_data(request):
    from .lgpd import patient_zip

    if request.method == "POST":
        log_action(request, "export", "Paciente baixou os próprios dados", level=30)
        resp = HttpResponse(patient_zip(request.patient), content_type="application/zip")
        resp["Content-Disposition"] = 'attachment; filename="meus-dados-wbook.zip"'
        return resp
    return render(request, "patient/my_data.html")


@patient_required
def settings_view(request):
    form = PatientSettingsForm(request.POST or None, instance=request.patient)
    if request.method == "POST" and form.is_valid():
        form.save()
        log_action(request, "settings", "Paciente alterou preferências de e-mail")
        messages.success(request, _("Preferências salvas."))
        return redirect("patient:settings")
    return render(request, "patient/settings.html", {"form": form})
