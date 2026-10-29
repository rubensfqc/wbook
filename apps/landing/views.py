from django.contrib import messages
from django.core.files.base import ContentFile
from django.db.models import Q
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST

from apps.clinic.models import Dentist
from apps.core.activity import log_action
from apps.core.notifications import notify_dentist
from apps.core.permissions import dentist_required
from apps.core.utils import ip_hash, rate_limited

from .forms import ContactForm, GalleryForm, LandingPageForm, LeadFollowForm, LeadForm
from .models import GalleryImage, Lead


# ---------------------------------------------------------------- dentist: page editor
@dentist_required
def editor(request):
    landing = request.dentist.landing
    form = LandingPageForm(request.POST or None, request.FILES or None, instance=landing)
    if request.method == "POST" and form.is_valid():
        form.save()
        log_action(request, "settings", "Página pública salva (publicada: %(p)s)", p=landing.is_published)
        messages.success(request, _("Página salva."))
        return redirect("landing:editor")
    return render(request, "landing/editor.html", {"form": form, "landing": landing, "gallery": landing.gallery.all(),
                                                   "gallery_form": GalleryForm()})


@dentist_required
@require_POST
def gallery_add(request):
    from apps.core.files import validate_image

    landing = request.dentist.landing
    if landing.gallery.count() >= GalleryImage.MAX:
        messages.error(request, _("Limite de %(n)s fotos na galeria.") % {"n": GalleryImage.MAX})
        return redirect("landing:editor")
    up = request.FILES.get("image")
    if not up:
        messages.error(request, _("Escolha uma imagem."))
        return redirect("landing:editor")
    try:
        validate_image(up)
        from PIL import Image

        Image.open(up).verify()
        up.seek(0)
    except Exception:  # noqa: BLE001
        messages.error(request, _("Imagem inválida."))
        return redirect("landing:editor")
    img = GalleryImage(landing=landing, caption=request.POST.get("caption", "")[:120], order=landing.gallery.count())
    img.image.save(up.name, ContentFile(up.read()), save=True)
    log_action(request, "settings", "Foto adicionada à galeria")
    messages.success(request, _("Foto adicionada."))
    return redirect(reverse("landing:editor") + "#galeria")


@dentist_required
@require_POST
def gallery_delete(request, pk):
    img = get_object_or_404(GalleryImage, pk=pk, landing__dentist=request.dentist)
    img.delete()
    log_action(request, "settings", "Foto removida da galeria", level=30)
    return redirect(reverse("landing:editor") + "#galeria")


# ---------------------------------------------------------------- dentist: leads
@dentist_required
def lead_list(request):
    qs = Lead.objects.for_dentist(request.dentist)
    status = request.GET.get("status", "")
    q = request.GET.get("q", "").strip()
    if status:
        qs = qs.filter(status=status)
    if q:
        qs = qs.filter(Q(name__icontains=q) | Q(email__icontains=q) | Q(whatsapp__icontains=q))
    counts = {s: Lead.objects.for_dentist(request.dentist).filter(status=s).count() for s, _l in Lead.Status.choices}
    return render(request, "landing/lead_list.html", {"leads": qs, "status": status, "q": q, "statuses": Lead.Status.choices,
                                                      "counts": counts})


@dentist_required
def lead_create(request):
    form = LeadForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        lead = form.save(commit=False)
        lead.dentist = request.dentist
        lead.source = Lead.Source.MANUAL
        lead.consent = True
        lead.save()
        log_action(request, "lead", "Lead cadastrado: %(e)s", e=lead.email)
        messages.success(request, _("Lead cadastrado."))
        return redirect("landing:lead_detail", pk=lead.pk)
    return render(request, "landing/lead_form.html", {"form": form})


@dentist_required
def lead_detail(request, pk):
    lead = get_object_or_404(Lead.objects.for_dentist(request.dentist), pk=pk)
    form = LeadFollowForm(request.POST or None, instance=lead)
    if request.method == "POST" and form.is_valid():
        form.save()
        log_action(request, "lead", "Lead %(e)s: %(s)s", e=lead.email, s=lead.status)
        if request.headers.get("HX-Request"):
            return render(request, "landing/_lead_follow.html", {"lead": lead, "form": form, "saved": True})
        messages.success(request, _("Lead atualizado."))
        return redirect("landing:lead_detail", pk=lead.pk)
    return render(request, "landing/lead_detail.html", {
        "lead": lead, "form": form, "appointments": lead.appointments.select_related("type").order_by("-start"),
        "quotes": lead.quotes.all(),
    })


@dentist_required
def lead_delete(request, pk):
    lead = get_object_or_404(Lead.objects.for_dentist(request.dentist), pk=pk)
    if request.method == "POST":
        email = lead.email
        lead.delete()
        log_action(request, "lead", "Lead removido: %(e)s", level=30, e=email)
        messages.success(request, _("Lead removido."))
        return redirect("landing:lead_list")
    return render(request, "confirm_delete.html", {"object": lead, "cancel_url": reverse("landing:lead_detail", args=[lead.pk]),
                                                   "warning": _("Os pedidos de consulta deste lead também serão apagados.")})


@dentist_required
def lead_export(request):
    from apps.clinic.views_export import _csv, leads_rows

    header, rows = leads_rows(request.dentist)
    log_action(request, "export", "Leads exportados (%(n)s)", n=len(rows))
    return _csv(f"leads-{request.dentist.slug}", header, rows)


# ---------------------------------------------------------------- public page
def _dentist(slug):
    return get_object_or_404(Dentist.objects.select_related("landing", "booking", "user"), slug=slug)


def public_page(request, slug):
    from apps.agenda.forms import VisitorRequestForm
    from apps.agenda.views_public import week_context

    d = _dentist(slug)
    landing = d.landing
    is_owner = request.user.is_authenticated and getattr(request.user, "dentist_profile", None) == d
    if not landing.is_live and not is_owner:
        raise Http404
    ctx = {"dentist": d, "landing": landing, "is_owner": is_owner, "gallery": landing.gallery.all(),
           "form": VisitorRequestForm(), "contact_form": ContactForm(),
           "is_my_patient": request.user.is_authenticated and getattr(getattr(request.user, "patient_profile", None), "dentist_id", None) == d.pk,
           "times_url": reverse("booking_public:times", args=[slug])}
    if landing.show_calendar and d.booking.visitor_booking_enabled:
        ctx.update(week_context(d, request))
    return render(request, "landing/public.html", ctx)


@require_POST
def contact(request, slug):
    d = _dentist(slug)
    if not d.landing.is_live:
        raise Http404
    form = ContactForm(request.POST)
    back = reverse("landing_public:page", args=[slug]) + "#contato"
    if form.data.get("company"):
        return redirect(back)
    if not form.is_valid():
        messages.error(request, _("Confira os campos do formulário de contato."))
        return redirect(back)
    if rate_limited(request, f"contact-{d.pk}", 5, 3600):
        messages.error(request, _("Muitas mensagens seguidas. Tente de novo mais tarde."))
        return redirect(back)
    c = form.cleaned_data
    lead = Lead.objects.create(dentist=d, name=c["name"], email=c["email"].lower(), whatsapp=c["whatsapp"], message=c["message"],
                               consent=True, source=Lead.Source.LANDING, ip_hash=ip_hash(request), language=request.LANGUAGE_CODE)
    log_action(None, "lead", "Contato pela página de %(d)s: %(e)s", d=d.slug, e=lead.email)
    from django.utils.translation import gettext_lazy as _l

    from apps.core.emails import absolute, send_templated

    notify_dentist(d, "alert_new_lead", (_l("Novo contato pela sua página: %(n)s"), {"n": lead.name}), "lead_new_dentist",
                   {"lead": lead, "link": absolute(reverse("landing:lead_detail", args=[lead.pk]))}, reply_to=lead.email)
    send_templated(lead.email, (_l("Recebemos sua mensagem — %(d)s"), {"d": d.name}), "lead_confirmation", {"lead": lead, "dentist": d},
                   reply_to=d.user.email, language=lead.language)
    messages.success(request, d.landing.thank_you_message or _("Mensagem enviada! A clínica vai responder em breve."))
    return redirect(back)


def branded_login(request, slug):
    from apps.accounts.views import LoginView

    d = _dentist(slug)
    return LoginView.as_view(dentist=d, template_name="accounts/login.html")(request)
