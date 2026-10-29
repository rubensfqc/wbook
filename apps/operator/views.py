"""/operador/ — wbook staff."""

from datetime import timedelta

from django.conf import settings
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.http import FileResponse, Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST

from apps.accounts.tokens import set_password_link
from apps.agenda.models import Appointment
from apps.clinic.models import Dentist
from apps.clinic.services import create_dentist
from apps.core import activity
from apps.core.activity import log_action
from apps.core.emails import send_templated
from apps.core.models import PlatformSettings
from apps.core.permissions import operator_required
from apps.website.models import PlatformLead

from .forms import DentistAddForm, DentistEditForm, ExportForm, ImportForm, PlatformSettingsForm


@operator_required
def dashboard(request):
    today = timezone.localdate()
    dentists = list(Dentist.objects.select_related("user"))
    return render(request, "operator/dashboard.html", {
        "n_dentists": len(dentists),
        "n_active": sum(1 for d in dentists if d.can_access),
        "n_paying": sum(1 for d in dentists if d.is_paying),
        "n_trial": sum(1 for d in dentists if d.can_access and not d.is_paying),
        "expiring": [d for d in dentists if d.can_access and 0 <= d.days_remaining <= 7],
        "recent": sorted(dentists, key=lambda d: d.created_at, reverse=True)[:6],
        "leads": PlatformLead.objects.filter(contacted=False)[:6],
        "appts_week": Appointment.objects.filter(created_at__date__gte=today - timedelta(days=7)).count(),
    })


@operator_required
def dentist_list(request):
    qs = Dentist.objects.select_related("user", "landing").annotate(n_patients=Count("patients", distinct=True))
    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(Q(clinic_name__icontains=q) | Q(user__email__icontains=q) | Q(slug__icontains=q) | Q(city__icontains=q))
    items = list(qs.order_by("-created_at"))
    situacao = request.GET.get("situacao", "")
    if situacao == "pagante":
        items = [d for d in items if d.is_paying]
    elif situacao == "teste":
        items = [d for d in items if d.can_access and not d.is_paying]
    elif situacao == "expirado":
        items = [d for d in items if not d.can_access and not d.is_suspended]
    elif situacao == "suspenso":
        items = [d for d in items if d.is_suspended]
    page = Paginator(items, 30).get_page(request.GET.get("pagina"))
    return render(request, "operator/dentist_list.html", {"page": page, "q": q, "situacao": situacao})


@operator_required
def dentist_add(request):
    form = DentistAddForm(request.POST or None, initial={"trial_days": PlatformSettings.get_solo().default_trial_days})
    if request.method == "POST" and form.is_valid():
        c = form.cleaned_data
        d = create_dentist(email=c["email"], name=c["name"], clinic_name=c["clinic_name"], slug=c["slug"],
                           display_name=c["display_name"], whatsapp=c["whatsapp"], city=c["city"], state=c["state"],
                           trial_days=c["trial_days"])
        send_templated(d.user.email, _("Bem-vindo ao wbook — defina sua senha"), "dentist_welcome_set_password",
                       {"dentist": d, "link": set_password_link(d.user)})
        log_action(request, "operator", "Dentista criado pelo operador: %(s)s", s=d.slug)
        messages.success(request, _("Dentista criado. Enviamos o e-mail para definir a senha."))
        return redirect("operator:dentist_edit", pk=d.pk)
    return render(request, "operator/dentist_add.html", {"form": form})


@operator_required
def dentist_edit(request, pk):
    d = get_object_or_404(Dentist.objects.select_related("user"), pk=pk)
    form = DentistEditForm(request.POST or None, instance=d)
    if request.method == "POST" and form.is_valid():
        form.save()
        log_action(request, "operator", "Dentista editado: %(s)s", s=d.slug)
        messages.success(request, _("Dados salvos."))
        return redirect("operator:dentist_edit", pk=d.pk)
    stats = {"patients": d.patients.count(), "appointments": d.appointments.count(), "treatments": d.treatments.count(),
             "leads": d.leads.count(), "quotes": d.quotes.count()}
    return render(request, "operator/dentist_edit.html", {"form": form, "d": d, "stats": stats})


@operator_required
@require_POST
def dentist_extend(request, pk):
    d = get_object_or_404(Dentist, pk=pk)
    days = int(request.POST.get("days", 30))
    base = max(d.paid_until or timezone.localdate(), timezone.localdate())
    d.paid_until = base + timedelta(days=days)
    d.is_suspended = False
    d.save(update_fields=["paid_until", "is_suspended"])
    log_action(request, "operator", "Acesso de %(s)s liberado por %(n)s dias (até %(u)s)", s=d.slug, n=days, u=d.paid_until)
    messages.success(request, _("Acesso liberado até %(d)s.") % {"d": f"{d.paid_until:%d/%m/%Y}"})
    return redirect("operator:dentist_edit", pk=d.pk)


@operator_required
@require_POST
def dentist_suspend(request, pk):
    d = get_object_or_404(Dentist, pk=pk)
    d.is_suspended = not d.is_suspended
    d.save(update_fields=["is_suspended"])
    log_action(request, "operator", "Dentista %(s)s %(a)s", level=30, s=d.slug, a="suspenso" if d.is_suspended else "reativado")
    messages.success(request, _("Dentista suspenso.") if d.is_suspended else _("Dentista reativado."))
    return redirect("operator:dentist_edit", pk=d.pk)


@operator_required
def dentist_delete(request, pk):
    d = get_object_or_404(Dentist.objects.select_related("user"), pk=pk)
    if request.method == "POST":
        if request.POST.get("confirm") != d.slug:
            messages.error(request, _("Digite o endereço exato para confirmar."))
            return redirect("operator:dentist_delete", pk=d.pk)
        slug = d.slug
        from apps.accounts.models import User

        patient_users = User.objects.filter(patient_profile__dentist=d)
        n = patient_users.count()
        patient_users.delete()
        d.user.delete()
        log_action(request, "operator", "Dentista %(s)s apagado com %(n)s pacientes", level=30, s=slug, n=n)
        messages.success(request, _("Dentista apagado."))
        return redirect("operator:dentist_list")
    return render(request, "operator/dentist_delete.html", {"d": d})


@operator_required
def platform_leads(request):
    if request.method == "POST":
        lead = get_object_or_404(PlatformLead, pk=request.POST.get("pk"))
        lead.contacted = not lead.contacted
        lead.save(update_fields=["contacted"])
        log_action(request, "operator", "Interessado %(e)s: contatado=%(c)s", e=lead.email, c=lead.contacted)
        return redirect("operator:platform_leads")
    qs = PlatformLead.objects.all()
    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(Q(name__icontains=q) | Q(email__icontains=q) | Q(clinic_name__icontains=q) | Q(city__icontains=q))
    return render(request, "operator/platform_leads.html", {"leads": qs, "q": q})


@operator_required
def settings_view(request):
    ps = PlatformSettings.get_solo()
    form = PlatformSettingsForm(request.POST or None, instance=ps)
    if request.method == "POST" and form.is_valid():
        form.save()
        log_action(request, "settings", "Configurações da plataforma salvas")
        messages.success(request, _("Configurações salvas."))
        return redirect("operator:settings")
    return render(request, "operator/settings.html", {
        "form": form,
        "alert_fields": [form[f] for f in PlatformSettings.ALERT_FIELDS],
        "recipients": ps.alert_recipients,
    })


@operator_required
def activity_view(request):
    rows = activity.read_lines(settings.ACTIVITY_LOG_FILE)
    f = {k: request.GET.get(k, "").strip() for k in ("q", "categoria", "quem", "periodo", "dia", "nivel")}
    now = timezone.localtime()
    if f["periodo"] in ("1", "7", "30"):
        since = (now - timedelta(days=int(f["periodo"]))).strftime("%Y-%m-%d %H:%M:%S")
        rows = [r for r in rows if r["when"] >= since]
    if f["dia"]:
        rows = [r for r in rows if r["when"].startswith(f["dia"])]
    if f["categoria"]:
        rows = [r for r in rows if r["category"] == f["categoria"]]
    if f["nivel"]:
        rows = [r for r in rows if r["level"] == f["nivel"]]
    if f["quem"]:
        rows = [r for r in rows if f["quem"].lower() in r["who"].lower()]
    if f["q"]:
        rows = [r for r in rows if f["q"].lower() in r["message"].lower()]
    page = Paginator(rows, 100).get_page(request.GET.get("pagina"))
    return render(request, "operator/activity.html", {"page": page, "f": f, "categories": activity.CATEGORIES,
                                                      "levels": ["INFO", "WARNING", "ERROR"]})


@operator_required
def activity_download(request):
    import os

    path = settings.ACTIVITY_LOG_FILE
    if not os.path.exists(path):
        raise Http404
    log_action(request, "operator", "Log de atividade baixado")
    return FileResponse(open(path, "rb"), as_attachment=True, filename="activity.log", content_type="text/plain")


# ---------------------------------------------------------------- data export / import
@operator_required
def data(request):
    from apps.dataio.exporter import export_bundle

    form = ExportForm(request.POST or None, prefix="x")
    if request.method == "POST" and form.is_valid():
        c = form.cleaned_data
        dentists = list(c["dentists"]) if c["scope"] == "some" else None
        payload = export_bundle(fmt=c["format"], dentists=dentists, include_files=c["include_files"],
                                include_passwords=c["include_passwords"], include_platform=dentists is None)
        log_action(request, "export", "Exportação de dados (%(f)s, %(s)s)", level=30, f=c["format"],
                   s="tudo" if dentists is None else ",".join(d.slug for d in dentists))
        ext = "zip" if c["format"] == "zip" else "toml"
        resp = HttpResponse(payload, content_type="application/zip" if ext == "zip" else "application/toml")
        resp["Content-Disposition"] = f'attachment; filename="wbook-{timezone.localdate():%Y%m%d}.{ext}"'
        return resp
    return render(request, "operator/data.html", {"form": form, "import_form": ImportForm()})


@operator_required
@require_POST
def data_import(request):
    import secrets
    from pathlib import Path

    from apps.dataio.importer import run_import

    form = ImportForm(request.POST, request.FILES)
    if not form.is_valid():
        messages.error(request, _("Escolha um arquivo."))
        return redirect("operator:data")
    raw = form.cleaned_data["file"].read()
    token = secrets.token_hex(12)
    folder = Path(settings.BASE_DIR) / "var" / "imports"
    folder.mkdir(parents=True, exist_ok=True)
    (folder / f"{token}.bin").write_bytes(raw)
    request.session["pending_import"] = token
    report = run_import(raw, dry_run=True)
    log_action(request, "operator", "Prévia de importação (%(ok)s)", ok="ok" if report.ok else "com erros")
    return render(request, "operator/data_report.html", {"report": report, "preview": True})


def _pending_path(request):
    from pathlib import Path

    token = request.session.get("pending_import")
    if not token or not token.isalnum():
        return None
    p = Path(settings.BASE_DIR) / "var" / "imports" / f"{token}.bin"
    return p if p.exists() else None


@operator_required
@require_POST
def data_import_confirm(request):
    from apps.core.notifications import notify_operator
    from apps.dataio.importer import run_import

    p = _pending_path(request)
    if p is None:
        messages.error(request, _("Nenhuma importação pendente."))
        return redirect("operator:data")
    report = run_import(p.read_bytes(), dry_run=False)
    p.unlink(missing_ok=True)
    request.session.pop("pending_import", None)
    log_action(request, "operator", "Importação de dados %(r)s", level=30, r="concluída" if report.ok else "falhou")
    if report.ok:
        notify_operator("alert_data_import", "Importação de dados concluída", "operator_data_import", {"report": report})
    return render(request, "operator/data_report.html", {"report": report, "preview": False})


@operator_required
@require_POST
def data_import_cancel(request):
    p = _pending_path(request)
    if p is not None:
        p.unlink(missing_ok=True)
    request.session.pop("pending_import", None)
    messages.success(request, _("Importação cancelada."))
    return redirect("operator:data")
