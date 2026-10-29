"""Quotes (orçamentos): dentist pages under /app/orcamentos/ and the tracked public page /<slug>/orcamento/<uuid>/."""

import json
from datetime import timedelta

from django.contrib import messages
from django.db import IntegrityError, transaction
from django.db.models import Count, Max
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy as _l
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from apps.clinic.models import PatientProfile, Treatment
from apps.core.activity import log_action
from apps.core.emails import absolute, send_templated
from apps.core.files import stream_file
from apps.core.notifications import notify_dentist
from apps.core.permissions import dentist_required
from apps.core.utils import describe_user_agent, ip_hash, is_bot
from apps.core.whatsapp import wa_link, wa_share

from .forms import ItemFormSet, QuoteForm
from .models import Quote, QuoteEvent, QuoteItem, QuoteVisit


def _public_url(q):
    return absolute(reverse("quote_public:page", args=[q.dentist.slug, q.uuid]))


# ---------------------------------------------------------------- dentist
@dentist_required
def quote_list(request):
    qs = Quote.objects.for_dentist(request.dentist).annotate(n_visits=Count("visits"), last_visit=Max("visits__started_at"))
    return render(request, "quotes/list.html", {"quotes": qs})


def _form_view(request, quote=None):
    d = request.dentist
    initial = {}
    if quote is None:
        initial["valid_until"] = timezone.localdate() + timedelta(days=30)
        if request.GET.get("lead"):
            lead = get_object_or_404(d.leads.all(), pk=request.GET["lead"])
            initial.update(lead=lead.pk, recipient_name=lead.name, recipient_email=lead.email, recipient_whatsapp=lead.whatsapp)
        if request.GET.get("paciente"):
            p = get_object_or_404(PatientProfile.objects.for_dentist(d), pk=request.GET["paciente"])
            initial.update(patient=p.pk, recipient_name=p.name, recipient_email=p.email, recipient_whatsapp=p.contact_whatsapp)
        if request.GET.get("tratamento"):
            t = get_object_or_404(Treatment.objects.for_dentist(d), pk=request.GET["tratamento"])
            initial.update(treatment=t.pk, patient=t.patient_id, recipient_name=t.patient.name, recipient_email=t.patient.email,
                           title=t.title)
    form = QuoteForm(request.POST or None, request.FILES or None, instance=quote, dentist=d, initial=initial)
    items = ItemFormSet(request.POST or None, instance=quote or Quote(), prefix="items")
    if request.method == "POST" and form.is_valid() and items.is_valid():
        with transaction.atomic():
            q = form.save(commit=False)
            q.dentist = d
            if q.patient and not q.recipient_email:
                q.recipient_email = q.patient.email
            q.save()
            items.instance = q
            items.save()
        log_action(request, "quote", "Orçamento salvo: %(t)s", t=q.title)
        messages.success(request, _("Orçamento salvo."))
        return redirect("quotes:detail", pk=q.pk)
    return render(request, "quotes/form.html", {"form": form, "items": items, "quote": quote})


@dentist_required
def quote_create(request):
    return _form_view(request)


@dentist_required
def quote_edit(request, pk):
    return _form_view(request, get_object_or_404(Quote.objects.for_dentist(request.dentist), pk=pk))


@dentist_required
def quote_detail(request, pk):
    q = get_object_or_404(Quote.objects.for_dentist(request.dentist).prefetch_related("items"), pk=pk)
    visits = list(q.visits.prefetch_related("events"))
    total_time = sum(v.duration_s for v in visits)
    today = timezone.localdate()
    per_day = []
    for i in range(13, -1, -1):
        day = today - timedelta(days=i)
        per_day.append({"label": f"{day:%d/%m}", "n": sum(1 for v in visits if timezone.localtime(v.started_at).date() == day)})
    first = min((v.started_at for v in visits), default=None)
    text = _("Olá %(n)s! Segue seu orçamento: %(u)s") % {"n": q.recipient_name.split(" ")[0], "u": _public_url(q)}
    ctx = {
        "q": q, "visits": visits, "public_url": _public_url(q),
        "kpi": {
            "visits": len(visits), "unique": len({v.ip_hash for v in visits}), "total_time": total_time,
            "avg_time": total_time // len(visits) if visits else 0, "max_scroll": max((v.max_scroll_pct for v in visits), default=0),
            "first": first, "last": max((v.last_seen_at for v in visits), default=None),
            "since_sent": (first - q.sent_at) if first and q.sent_at else None,
        },
        "chart": {"labels": [p["label"] for p in per_day], "values": [p["n"] for p in per_day]},
        "wa_url": wa_link(q.recipient_whatsapp, text) if q.recipient_whatsapp else wa_share(text),
    }
    return render(request, "quotes/detail.html", ctx)


@dentist_required
@require_POST
def quote_send(request, pk):
    q = get_object_or_404(Quote.objects.for_dentist(request.dentist), pk=pk)
    if q.status == Quote.Status.DRAFT:
        q.status = Quote.Status.SENT
        q.sent_at = timezone.now()
        q.save(update_fields=["status", "sent_at", "updated_at"])
        if q.lead_id:
            q.lead.advance("QUOTE")
    if request.POST.get("email") == "1" and q.recipient_email:
        lang = q.patient.user.language if q.patient_id else (q.lead.language if q.lead_id else "pt-br")
        send_templated(q.recipient_email, (_l("Seu orçamento — %(d)s"), {"d": q.dentist.name}), "quote_sent",
                       {"q": q, "dentist": q.dentist, "link": _public_url(q)}, reply_to=q.dentist.user.email, language=lang)
        messages.success(request, _("Orçamento enviado por e-mail para %(e)s.") % {"e": q.recipient_email})
    else:
        messages.success(request, _("Orçamento liberado. Copie o link ou envie pelo WhatsApp."))
    log_action(request, "quote", "Orçamento enviado: %(t)s", t=q.title)
    return redirect("quotes:detail", pk=q.pk)


@dentist_required
@require_POST
def quote_link(request, pk):
    q = get_object_or_404(Quote.objects.for_dentist(request.dentist), pk=pk)
    q.is_active = not q.is_active
    q.save(update_fields=["is_active", "updated_at"])
    log_action(request, "quote", "Link do orçamento %(t)s %(a)s", t=q.title, a="ativado" if q.is_active else "desativado")
    return redirect("quotes:detail", pk=q.pk)


@dentist_required
@require_POST
def quote_duplicate(request, pk):
    q = get_object_or_404(Quote.objects.for_dentist(request.dentist), pk=pk)
    items = list(q.items.all())
    import uuid

    q.pk = None
    q.ref, q.uuid = uuid.uuid4(), uuid.uuid4()
    q.status, q.sent_at, q.responded_at, q.response_note = Quote.Status.DRAFT, None, None, ""
    q.title = _("%(t)s (cópia)") % {"t": q.title}
    q.attachment = ""  # never share a stored file between two rows (deleting one would delete it)
    q.save()
    for it in items:
        QuoteItem.objects.create(quote=q, description=it.description, region=it.region, quantity=it.quantity,
                                 unit_amount=it.unit_amount, order=it.order)
    log_action(request, "quote", "Orçamento duplicado: %(t)s", t=q.title)
    messages.success(request, _("Cópia criada como rascunho."))
    return redirect("quotes:edit", pk=q.pk)


@dentist_required
def quote_delete(request, pk):
    q = get_object_or_404(Quote.objects.for_dentist(request.dentist), pk=pk)
    if request.method == "POST":
        t = q.title
        q.delete()
        log_action(request, "quote", "Orçamento removido: %(t)s", level=30, t=t)
        messages.success(request, _("Orçamento removido."))
        return redirect("quotes:list")
    return render(request, "confirm_delete.html", {"object": q, "cancel_url": reverse("quotes:detail", args=[q.pk])})


@dentist_required
@require_POST
def quote_to_treatment(request, pk):
    from apps.clinic.services import add_event

    q = get_object_or_404(Quote.objects.for_dentist(request.dentist), pk=pk)
    if q.treatment_id:
        t = q.treatment
        t.budget = q.total
        t.save(update_fields=["budget", "updated_at"])
        add_event(t, _("Orçamento aceito: %(t)s") % {"t": q.title}, request.user)
        messages.success(request, _("Valor do tratamento atualizado com o orçamento."))
        return redirect("clinic:treatment_detail", pk=t.pk)
    if not q.patient_id:
        messages.error(request, _("Cadastre o paciente primeiro."))
        return redirect("quotes:detail", pk=q.pk)
    t = Treatment.objects.create(
        dentist=q.dentist, patient=q.patient, title=q.title, budget=q.total, source_quote=q,
        description="\n".join(f"- {i.description}" + (f" ({i.region})" if i.region else "") for i in q.items.all()),
    )
    q.treatment = t
    q.save(update_fields=["treatment", "updated_at"])
    add_event(t, _("Tratamento criado a partir do orçamento aceito"), request.user)
    log_action(request, "treatment", "Tratamento criado do orçamento %(q)s", q=q.title)
    messages.success(request, _("Tratamento criado."))
    return redirect("clinic:treatment_detail", pk=t.pk)


# ---------------------------------------------------------------- public
def _public_quote(slug, uuid_):
    return get_object_or_404(Quote.objects.select_related("dentist__landing", "dentist__user").prefetch_related("items"),
                             uuid=uuid_, dentist__slug=slug)


def _is_owner(request, q):
    return request.user.is_authenticated and getattr(request.user, "dentist_profile", None) == q.dentist


def public_page(request, slug, uuid):
    q = _public_quote(slug, uuid)
    owner = _is_owner(request, q)
    if q.status == Quote.Status.DRAFT and not owner:
        raise Http404
    if not q.is_active and not owner:
        return render(request, "quotes/public_inactive.html", {"q": q, "dentist": q.dentist}, status=410)
    visit = None
    if not owner and not is_bot(request):
        h = ip_hash(request)
        device, browser, os_name = describe_user_agent(request.META.get("HTTP_USER_AGENT", ""))
        returning = q.visits.filter(ip_hash=h).exists()
        visit = QuoteVisit.objects.create(quote=q, device=device, browser=browser, os=os_name, ip_hash=h, is_returning=returning,
                                          referrer=request.META.get("HTTP_REFERER", "")[:300])
        if q.status == Quote.Status.SENT:
            q.status = Quote.Status.VIEWED
            q.save(update_fields=["status", "updated_at"])
            notify_dentist(q.dentist, "alert_quote_viewed", (_l("%(n)s abriu seu orçamento"), {"n": q.recipient_name}),
                           "quote_first_view", {"q": q, "link": absolute(reverse("quotes:detail", args=[q.pk]))})
    text = _("Olá! Tenho uma dúvida sobre o orçamento \"%(t)s\".") % {"t": q.title}
    resp = render(request, "quotes/public.html", {"q": q, "dentist": q.dentist, "visit": visit, "owner": owner,
                                                   "wa_url": wa_link(q.dentist.whatsapp, text)})
    resp["Referrer-Policy"] = "same-origin"
    return resp


def public_pdf(request, slug, uuid):
    q = _public_quote(slug, uuid)
    if not q.attachment or (q.status == Quote.Status.DRAFT and not _is_owner(request, q)) or not q.is_active:
        raise Http404
    return stream_file(request, q.attachment, f"orcamento-{q.pk}.pdf", "application/pdf")


def _payload(request):
    try:
        return json.loads(request.body.decode("utf-8") or "{}")
    except (ValueError, UnicodeDecodeError):
        return {}


@csrf_exempt
@require_POST
def beacon(request, slug, uuid):
    data = _payload(request)
    try:
        v = QuoteVisit.objects.get(token=data.get("visit"), quote__uuid=uuid, quote__dentist__slug=slug)
    except (QuoteVisit.DoesNotExist, ValueError, Exception):  # noqa: BLE001
        return HttpResponse(status=204)
    try:
        dur = max(0, min(int(data.get("duration", 0)), 4 * 3600))
        scroll = max(0, min(int(data.get("scroll", 0)), 100))
    except (TypeError, ValueError):
        return HttpResponse(status=204)
    QuoteVisit.objects.filter(pk=v.pk).update(
        duration_s=max(v.duration_s, dur), max_scroll_pct=max(v.max_scroll_pct, scroll), last_seen_at=timezone.now())
    return HttpResponse(status=204)


@csrf_exempt
@require_POST
def event(request, slug, uuid):
    data = _payload(request)
    kind = data.get("kind")
    if kind not in ("pdf", "download", "whatsapp"):
        return HttpResponse(status=204)
    try:
        v = QuoteVisit.objects.get(token=data.get("visit"), quote__uuid=uuid, quote__dentist__slug=slug)
        QuoteEvent.objects.get_or_create(visit=v, kind=kind)
    except (QuoteVisit.DoesNotExist, IntegrityError, ValueError, Exception):  # noqa: BLE001
        pass
    return HttpResponse(status=204)


@require_POST
def respond(request, slug, uuid):
    q = _public_quote(slug, uuid)
    if not q.can_respond:
        messages.error(request, _("Este orçamento não pode mais ser respondido. Fale com a clínica."))
        return redirect("quote_public:page", slug=slug, uuid=uuid)
    accepted = request.POST.get("decision") == "accept"
    q.status = Quote.Status.ACCEPTED if accepted else Quote.Status.DECLINED
    q.responded_at = timezone.now()
    q.response_note = request.POST.get("note", "")[:2000]
    q.save(update_fields=["status", "responded_at", "response_note", "updated_at"])
    token = request.POST.get("visit")
    if token:
        v = q.visits.filter(token=token).first()
        if v:
            QuoteEvent.objects.get_or_create(visit=v, kind="accepted" if accepted else "declined")
    if accepted and q.lead_id:
        q.lead.advance("WON")
    log_action(None, "quote", "Orçamento %(t)s %(a)s pelo paciente", t=q.title, a="aceito" if accepted else "recusado")
    notify_dentist(q.dentist, "alert_quote_response",
                   ((_l("%(n)s aceitou o orçamento") if accepted else _l("%(n)s recusou o orçamento")), {"n": q.recipient_name}),
                   "quote_response", {"q": q, "accepted": accepted, "link": absolute(reverse("quotes:detail", args=[q.pk]))})
    messages.success(request, _("Obrigado! A clínica foi avisada.") if accepted else _("Resposta enviada. Obrigado!"))
    return redirect("quote_public:page", slug=slug, uuid=uuid)

