"""Dentist portal: /app/ (dashboard, settings, patients, treatments, files, invoices)."""

from datetime import timedelta

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.db.models import Count, Q, Sum
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy as _l
from django.views.decorators.http import require_POST

from apps.agenda.models import Appointment
from apps.core.activity import log_action
from apps.core.emails import absolute
from apps.core.notifications import notify_patient
from apps.core.permissions import dentist_required

from . import services
from .forms import (
    AlertsForm,
    DentistProfileForm,
    InvoiceForm,
    MessageForm,
    PatientEditForm,
    PatientForm,
    TreatmentForm,
    TreatmentStatusForm,
    UploadForm,
)
from .models import Invoice, PatientProfile, Treatment, TreatmentEntry, TreatmentFile


# ---------------------------------------------------------------- dashboard / settings
def _checklist(d):
    return [
        (_("Complete seu perfil e envie o logo"), bool(d.logo and d.address), reverse("clinic:settings")),
        (_("Defina seus horários e tipos de consulta"), d.working_hours.exists() and d.appointment_types.exists(),
         reverse("agenda:settings")),
        (_("Revise as regras de agendamento"), d.onboarding_done, reverse("agenda:settings")),
        (_("Publique sua página"), d.landing.is_published, reverse("landing:editor")),
        (_("Convide seu primeiro paciente"), d.patients.exists(), reverse("clinic:patient_create")),
    ]


@dentist_required
def dashboard(request):
    d = request.dentist
    now = timezone.now()
    today = timezone.localtime(now, d.tzinfo).date()
    from apps.agenda.slots import day_bounds

    ds, de = day_bounds(d, today)
    appts = Appointment.objects.for_dentist(d).select_related("type", "patient__user", "lead")
    from apps.quotes.models import QuoteVisit

    ctx = {
        "today_appts": appts.filter(start__gte=ds, start__lt=de).exclude(status__in=["RESCHEDULED", "REJECTED", "EXPIRED"]),
        "pending": appts.filter(status="PENDING", start__gte=now),
        "late_cancels": appts.filter(late_cancel_requested_at__isnull=False, status__in=Appointment.BLOCKING_STATUSES, start__gte=now),
        "new_leads": d.leads.filter(status="NEW")[:5],
        "open_invoices": Invoice.objects.for_dentist(d).filter(status="OPEN").select_related("treatment__patient__user")[:5],
        "open_total": Invoice.objects.for_dentist(d).filter(status="OPEN").aggregate(s=Sum("amount"))["s"] or 0,
        "quote_visits": QuoteVisit.objects.filter(quote__dentist=d).select_related("quote")[:6],
        "kpi_week": appts.filter(start__gte=ds, start__lt=ds + timedelta(days=7), status__in=Appointment.BLOCKING_STATUSES).count(),
        "kpi_patients": d.patients.count(),
        "kpi_treatments": Treatment.objects.for_dentist(d).filter(status__in=["PLANNED", "IN_PROGRESS"]).count(),
        "checklist": _checklist(d),
    }
    weeks = []
    for i in range(7, -1, -1):
        ws = ds - timedelta(days=today.weekday() + 7 * i)
        weeks.append({"label": f"{timezone.localtime(ws, d.tzinfo):%d/%m}",
                      "n": appts.filter(start__gte=ws, start__lt=ws + timedelta(days=7), status__in=["CONFIRMED", "COMPLETED"]).count()})
    ctx["chart"] = {"labels": [w["label"] for w in weeks], "values": [w["n"] for w in weeks]}
    ctx["show_checklist"] = not all(done for _t, done, _u in ctx["checklist"])
    return render(request, "clinic/dashboard.html", ctx)


@dentist_required
def onboarding(request):
    return render(request, "clinic/onboarding.html", {"checklist": _checklist(request.dentist)})


@dentist_required
def settings_view(request):
    d = request.dentist
    profile = DentistProfileForm(request.POST or None, request.FILES or None, instance=d, prefix="p")
    alerts = AlertsForm(request.POST or None, instance=d, prefix="a")
    if request.method == "POST":
        which = request.POST.get("form")
        form = profile if which == "profile" else alerts
        if form.is_valid():
            form.save()
            log_action(request, "settings", "Configurações salvas (%(f)s)", f=which)
            messages.success(request, _("Configurações salvas."))
            return redirect("clinic:settings")
    return render(request, "clinic/settings.html", {
        "profile": profile, "alerts": alerts,
        "dentist_alerts": [alerts[f] for f in d.ALERT_FIELDS], "patient_alerts": [alerts[f] for f in d.PATIENT_ALERT_FIELDS],
    })


def expired(request):
    if not request.user.is_authenticated or not request.user.is_dentist:
        return redirect("accounts:login")
    from apps.core.models import PlatformSettings

    return render(request, "clinic/expired.html", {"dentist": request.user.dentist_profile, "plans": PlatformSettings.get_solo().plans})


# ---------------------------------------------------------------- patients
@dentist_required
def patient_list(request):
    qs = PatientProfile.objects.for_dentist(request.dentist).select_related("user").annotate(
        n_treat=Count("treatments", filter=Q(treatments__status__in=["PLANNED", "IN_PROGRESS"]), distinct=True))
    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(Q(user__name__icontains=q) | Q(user__email__icontains=q) | Q(whatsapp__icontains=q))
    return render(request, "clinic/patient_list.html", {"patients": qs, "q": q})


@dentist_required
def patient_create(request):
    from apps.landing.models import Lead

    d = request.dentist
    lead = None
    if request.GET.get("lead"):
        lead = get_object_or_404(Lead.objects.for_dentist(d), pk=request.GET["lead"])
    initial = {"name": lead.name, "email": lead.email, "whatsapp": lead.whatsapp} if lead else {}
    form = PatientForm(request.POST or None, initial=initial)
    if request.method == "POST" and form.is_valid():
        c = form.cleaned_data
        try:
            patient = services.invite_patient(d, name=c["name"], email=c["email"], phone=c["phone"], whatsapp=c["whatsapp"],
                                              birth_date=c["birth_date"], cpf=c["cpf"], lead=lead, send=c["send_invite"])
        except ValueError as exc:
            form.add_error("email", str(exc))
        else:
            log_action(request, "patient", "Paciente cadastrado: %(e)s", e=patient.email)
            messages.success(request, _("Paciente cadastrado.") + (" " + _("Convite enviado.") if c["send_invite"] else ""))
            return redirect("clinic:patient_detail", pk=patient.pk)
    return render(request, "clinic/patient_form.html", {"form": form, "lead": lead})


@dentist_required
def patient_detail(request, pk):
    d = request.dentist
    p = get_object_or_404(PatientProfile.objects.for_dentist(d).select_related("user"), pk=pk)
    return render(request, "clinic/patient_detail.html", {
        "patient": p,
        "appointments": p.appointments.select_related("type").order_by("-start")[:30],
        "treatments": p.treatments.all(),
        "invoices": Invoice.objects.for_dentist(d).filter(treatment__patient=p),
        "quotes": p.quotes.all(),
    })


@dentist_required
def patient_edit(request, pk):
    p = get_object_or_404(PatientProfile.objects.for_dentist(request.dentist), pk=pk)
    form = PatientEditForm(request.POST or None, instance=p)
    if request.method == "POST" and form.is_valid():
        form.save()
        log_action(request, "patient", "Paciente editado: %(e)s", e=p.email)
        messages.success(request, _("Paciente atualizado."))
        return redirect("clinic:patient_detail", pk=p.pk)
    return render(request, "clinic/patient_edit.html", {"form": form, "patient": p})


@dentist_required
@require_POST
def patient_reinvite(request, pk):
    p = get_object_or_404(PatientProfile.objects.for_dentist(request.dentist), pk=pk)
    services.send_invite(p)
    log_action(request, "patient", "Convite reenviado: %(e)s", e=p.email)
    messages.success(request, _("Convite reenviado para %(e)s.") % {"e": p.email})
    return redirect("clinic:patient_detail", pk=p.pk)


@dentist_required
def patient_delete(request, pk):
    p = get_object_or_404(PatientProfile.objects.for_dentist(request.dentist), pk=pk)
    if request.method == "POST":
        records = bool(request.POST.get("delete_records"))
        email = p.email
        services.anonymise_patient(p, delete_records=records)
        log_action(request, "patient", "Paciente removido: %(e)s (registros clínicos %(r)s)", level=30, e=email,
                   r="apagados" if records else "mantidos")
        messages.success(request, _("Paciente removido."))
        return redirect("clinic:patient_list")
    return render(request, "clinic/patient_delete.html", {"patient": p})


@dentist_required
def patient_data_zip(request, pk):
    from .lgpd import patient_zip

    p = get_object_or_404(PatientProfile.objects.for_dentist(request.dentist), pk=pk)
    log_action(request, "export", "Exportação LGPD do paciente %(e)s", level=30, e=p.email)
    resp = HttpResponse(patient_zip(p, include_unshared=True), content_type="application/zip")
    resp["Content-Disposition"] = f'attachment; filename="paciente-{p.pk}.zip"'
    return resp


# ---------------------------------------------------------------- treatments
@dentist_required
def treatment_list(request):
    qs = Treatment.objects.for_dentist(request.dentist).select_related("patient__user")
    status = request.GET.get("status", "")
    if status:
        qs = qs.filter(status=status)
    return render(request, "clinic/treatment_list.html", {"treatments": qs, "status": status, "statuses": Treatment.Status.choices})


@dentist_required
def treatment_create(request):
    d = request.dentist
    initial = {}
    quote = None
    if request.GET.get("paciente"):
        initial["patient"] = get_object_or_404(PatientProfile.objects.for_dentist(d), pk=request.GET["paciente"]).pk
    if request.GET.get("orcamento"):
        from apps.quotes.models import Quote

        quote = get_object_or_404(Quote.objects.for_dentist(d), pk=request.GET["orcamento"])
        initial.update(title=quote.title, budget=quote.total, patient=quote.patient_id,
                       description="\n".join(f"- {i.description} {i.region}".strip() for i in quote.items.all()))
    if not d.patients.exists():
        return render(request, "clinic/treatment_form.html", {"no_patients": True})
    form = TreatmentForm(request.POST or None, dentist=d, initial=initial)
    if request.method == "POST" and form.is_valid():
        t = form.save(commit=False)
        t.dentist = d
        t.source_quote = quote
        t.save()
        services.add_event(t, _("Tratamento criado"), request.user)
        log_action(request, "treatment", "Tratamento criado: %(t)s", t=t.title)
        _notify_treatment(t, _("Novo tratamento: %(t)s") % {"t": t.title})
        messages.success(request, _("Tratamento criado."))
        return redirect("clinic:treatment_detail", pk=t.pk)
    return render(request, "clinic/treatment_form.html", {"form": form, "quote": quote})


def _notify_treatment(t, text):
    notify_patient(t.dentist, t.patient, "patient_alert_treatment", (_l("Novidade no seu tratamento: %(t)s"), {"t": t.title}),
                   "patient_treatment_activity",
                   {"treatment": t, "text": text, "link": absolute(reverse("patient:treatment", args=[t.pk]))},
                   opt_out="opt_out_treatment_updates", treatment=t)


@dentist_required
def treatment_detail(request, pk):
    t = get_object_or_404(Treatment.objects.for_dentist(request.dentist).select_related("patient__user"), pk=pk)
    files = list(t.files.all())
    return render(request, "clinic/treatment_detail.html", {
        "t": t,
        "photos": [f for f in files if f.is_photo],
        "docs": [f for f in files if not f.is_photo],
        "phases": TreatmentFile.Phase.choices,
        "entries": t.entries.select_related("author"),
        "sessions": t.appointments.select_related("type").order_by("start"),
        "invoices": t.invoices.all(),
        "upload_form": UploadForm(),
        "message_form": MessageForm(),
        "status_form": TreatmentStatusForm(instance=t),
    })


@dentist_required
def treatment_edit(request, pk):
    t = get_object_or_404(Treatment.objects.for_dentist(request.dentist), pk=pk)
    form = TreatmentForm(request.POST or None, instance=t, dentist=request.dentist)
    if request.method == "POST" and form.is_valid():
        form.save()
        log_action(request, "treatment", "Tratamento editado: %(t)s", t=t.title)
        messages.success(request, _("Tratamento atualizado."))
        return redirect("clinic:treatment_detail", pk=t.pk)
    return render(request, "clinic/treatment_form.html", {"form": form, "t": t})


@dentist_required
@require_POST
def treatment_status(request, pk):
    t = get_object_or_404(Treatment.objects.for_dentist(request.dentist), pk=pk)
    old = t.get_status_display()
    form = TreatmentStatusForm(request.POST, instance=t)
    if form.is_valid():
        t = form.save()
        if t.get_status_display() != old:
            services.add_event(t, _("Situação: %(a)s → %(b)s") % {"a": old, "b": t.get_status_display()}, request.user)
        log_action(request, "treatment", "Situação do tratamento %(t)s: %(s)s (%(p)s%%)", t=t.title, s=t.status, p=t.progress)
        messages.success(request, _("Situação atualizada."))
    return redirect("clinic:treatment_detail", pk=t.pk)


@dentist_required
@require_POST
def treatment_message(request, pk):
    t = get_object_or_404(Treatment.objects.for_dentist(request.dentist), pk=pk)
    form = MessageForm(request.POST)
    if form.is_valid():
        TreatmentEntry.objects.create(treatment=t, author=request.user, author_role="DENTIST", text=form.cleaned_data["text"])
        log_action(request, "treatment", "Mensagem no tratamento %(t)s", t=t.title)
        _notify_treatment(t, form.cleaned_data["text"])
    return redirect(reverse("clinic:treatment_detail", args=[t.pk]) + "#timeline")


@dentist_required
@require_POST
def treatment_upload(request, pk):
    from django.core.files.base import ContentFile

    from apps.core.files import validate_pdf

    from .photos import save_photo

    t = get_object_or_404(Treatment.objects.for_dentist(request.dentist), pk=pk)
    form = UploadForm(request.POST)
    form.is_valid()
    c = form.cleaned_data if form.is_valid() else {}
    ok, errors, shared_any = 0, [], False
    for up in request.FILES.getlist("files"):
        name = up.name
        is_pdf = name.lower().endswith(".pdf")
        f = TreatmentFile(treatment=t, uploaded_by=request.user, title=c.get("title") or (name if is_pdf else ""),
                          caption=c.get("title", "") if not is_pdf else "", region=c.get("region", ""),
                          taken_on=c.get("taken_on") or timezone.localdate())
        try:
            if is_pdf:
                validate_pdf(up)
                f.kind = TreatmentFile.Kind.PDF
                f.shared = True if "shared" not in request.POST else bool(c.get("shared"))
                f.file.save("doc.pdf", ContentFile(up.read()), save=False)
                f.size = up.size
            else:
                f.kind = TreatmentFile.Kind.PHOTO
                f.phase = c.get("phase") or "BEFORE"
                f.shared = bool(c.get("shared"))
                save_photo(f, up)
            f.save()
            ok += 1
            shared_any = shared_any or f.shared
            log_action(request, "file", "Arquivo %(k)s #%(id)s enviado no tratamento #%(t)s", k=f.kind, id=f.pk, t=t.pk)
        except ValidationError as exc:
            errors.append(f"{name}: {' '.join(exc.messages)}")
    if ok:
        services.add_event(t, _("%(n)s arquivo(s) adicionado(s)") % {"n": ok}, request.user)
        messages.success(request, _("%(n)s arquivo(s) enviado(s).") % {"n": ok})
        if shared_any:
            _notify_treatment(t, _("Novos arquivos foram compartilhados com você."))
    for e in errors:
        messages.error(request, e)
    return redirect(reverse("clinic:treatment_detail", args=[t.pk]) + "#arquivos")


@dentist_required
@require_POST
def phase_share(request, pk, phase):
    t = get_object_or_404(Treatment.objects.for_dentist(request.dentist), pk=pk)
    share = request.POST.get("share", "1") == "1"
    n = t.files.filter(kind="PHOTO", phase=phase).update(shared=share)
    log_action(request, "file", "Fase %(p)s do tratamento #%(t)s %(a)s (%(n)s fotos)", p=phase, t=t.pk,
               a="compartilhada" if share else "ocultada", n=n)
    if share and n:
        _notify_treatment(t, _("Novas fotos foram compartilhadas com você."))
    messages.success(request, _("Fotos atualizadas."))
    return redirect(reverse("clinic:treatment_detail", args=[t.pk]) + "#arquivos")


@dentist_required
def treatment_delete(request, pk):
    t = get_object_or_404(Treatment.objects.for_dentist(request.dentist), pk=pk)
    if request.method == "POST":
        title = t.title
        t.delete()
        log_action(request, "treatment", "Tratamento removido: %(t)s", level=30, t=title)
        messages.success(request, _("Tratamento removido."))
        return redirect("clinic:treatment_list")
    return render(request, "confirm_delete.html", {"object": t, "cancel_url": reverse("clinic:treatment_detail", args=[t.pk]),
                                                   "warning": _("Os arquivos, mensagens e faturas deste tratamento também serão apagados.")})


@dentist_required
@require_POST
def file_share(request, pk):
    f = get_object_or_404(TreatmentFile.objects.for_dentist(request.dentist), pk=pk)
    f.shared = not f.shared
    f.save(update_fields=["shared"])
    log_action(request, "file", "Arquivo #%(id)s %(a)s", id=f.pk, a="compartilhado" if f.shared else "ocultado")
    if f.shared:
        _notify_treatment(f.treatment, _("Um novo arquivo foi compartilhado com você."))
    if request.headers.get("HX-Request"):
        return render(request, "components/share_toggle.html", {"f": f})
    return redirect(reverse("clinic:treatment_detail", args=[f.treatment_id]) + "#arquivos")


@dentist_required
@require_POST
def file_delete(request, pk):
    f = get_object_or_404(TreatmentFile.objects.for_dentist(request.dentist), pk=pk)
    tid = f.treatment_id
    log_action(request, "file", "Arquivo #%(id)s removido do tratamento #%(t)s", level=30, id=f.pk, t=tid)
    f.delete()
    messages.success(request, _("Arquivo removido."))
    return redirect(reverse("clinic:treatment_detail", args=[tid]) + "#arquivos")


# ---------------------------------------------------------------- invoices
@dentist_required
def invoice_list(request):
    qs = Invoice.objects.for_dentist(request.dentist).select_related("treatment__patient__user")
    status = request.GET.get("status", "")
    if status:
        qs = qs.filter(status=status)
    return render(request, "clinic/invoice_list.html", {"invoices": qs, "status": status, "statuses": Invoice.Status.choices})


def _send_invoice(inv):
    t = inv.treatment
    return notify_patient(inv.dentist, t.patient, "patient_alert_invoice",
                          (_l("Nova fatura %(n)s — %(d)s"), {"n": inv.display_number, "d": inv.dentist.name}), "invoice_new",
                          {"invoice": inv, "link": absolute(reverse("patient:invoice", args=[inv.pk]))}, treatment=t)


@dentist_required
def invoice_create(request, pk):
    t = get_object_or_404(Treatment.objects.for_dentist(request.dentist), pk=pk)
    form = InvoiceForm(request.POST or None, initial={"title": t.title, "amount": t.budget})
    if request.method == "POST" and form.is_valid():
        inv = form.save(commit=False)
        inv.treatment = t
        inv.dentist = request.dentist
        inv.save()
        log_action(request, "invoice", "Fatura %(n)s criada (%(v)s)", n=inv.display_number, v=inv.amount)
        if form.cleaned_data["send_email"]:
            _send_invoice(inv)
        messages.success(request, _("Fatura %(n)s criada.") % {"n": inv.display_number})
        return redirect("clinic:invoice_detail", pk=inv.pk)
    return render(request, "clinic/invoice_form.html", {"form": form, "t": t})


@dentist_required
def invoice_detail(request, pk):
    inv = get_object_or_404(Invoice.objects.for_dentist(request.dentist).select_related("treatment__patient__user"), pk=pk)
    return render(request, "clinic/invoice_detail.html", {"inv": inv})


@dentist_required
@require_POST
def invoice_action(request, pk, action):
    inv = get_object_or_404(Invoice.objects.for_dentist(request.dentist), pk=pk)
    if action == "pago":
        inv.status, inv.paid_at = Invoice.Status.PAID, timezone.now()
    elif action == "cancelar":
        inv.status = Invoice.Status.CANCELLED
    elif action == "reabrir":
        inv.status, inv.paid_at = Invoice.Status.OPEN, None
    elif action == "enviar":
        _send_invoice(inv)
        messages.success(request, _("Fatura enviada por e-mail."))
        log_action(request, "invoice", "Fatura %(n)s enviada", n=inv.display_number)
        return redirect("clinic:invoice_detail", pk=inv.pk)
    inv.save()
    log_action(request, "invoice", "Fatura %(n)s: %(s)s", level=30 if action == "cancelar" else 20, n=inv.display_number, s=inv.status)
    messages.success(request, _("Fatura atualizada."))
    return redirect("clinic:invoice_detail", pk=inv.pk)
