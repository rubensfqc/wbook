from django import forms
from django.contrib import messages
from django.contrib.sitemaps import Sitemap
from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy as _l
from django.views.decorators.http import require_POST

from apps.core.activity import log_action
from apps.core.forms import StyledModelForm
from apps.core.models import PlatformSettings
from apps.core.notifications import notify_operator
from apps.core.utils import rate_limited

from .models import PlatformLead


class PlatformLeadForm(StyledModelForm):
    company = forms.CharField(required=False, widget=forms.TextInput(attrs={"tabindex": "-1", "autocomplete": "off"}))

    class Meta:
        model = PlatformLead
        fields = ["name", "email", "whatsapp", "clinic_name", "city", "message"]
        widgets = {"message": forms.Textarea(attrs={"rows": 3})}


def home(request):
    ps = PlatformSettings.get_solo()
    return render(request, "website/home.html", {"ps": ps, "form": PlatformLeadForm(), "plans": ps.plans})


def plans(request):
    ps = PlatformSettings.get_solo()
    return render(request, "website/plans.html", {"plans": ps.plans, "ps": ps})


@require_POST
def contact(request):
    form = PlatformLeadForm(request.POST)
    if form.data.get("company"):
        return redirect("website:thanks")
    if rate_limited(request, "platform-contact", 5, 3600):
        messages.error(request, _("Muitas mensagens seguidas. Tente de novo mais tarde."))
        return redirect(reverse("website:home") + "#contato")
    if form.is_valid():
        lead = form.save()
        log_action(None, "lead", "Interessado no wbook: %(e)s", e=lead.email)
        notify_operator("alert_platform_lead", (_l("Novo interessado no wbook: %(n)s"), {"n": lead.name}), "platform_lead",
                        {"lead": lead}, reply_to=lead.email)
        return redirect("website:thanks")
    messages.error(request, _("Confira os campos do formulário."))
    return redirect(reverse("website:home") + "#contato")


def thanks(request):
    return render(request, "website/thanks.html")


def terms(request):
    return render(request, "website/terms.html")


def privacy(request):
    return render(request, "website/privacy.html")


def favicon(request):
    """Browsers and crawlers ask for /favicon.ico directly; point them at the (hashed) static file."""
    from django.shortcuts import redirect
    from django.templatetags.static import static

    return redirect(static("img/favicon.ico"))


def robots(request):
    from django.conf import settings

    body = f"User-agent: *\nDisallow: /app/\nDisallow: /paciente/\nDisallow: /operador/\nDisallow: /conta/\nDisallow: /arquivos/\n" \
           f"Disallow: /calendario/\nSitemap: {settings.SITE_URL}/sitemap.xml\n"
    return HttpResponse(body, content_type="text/plain")


class StaticSitemap(Sitemap):
    def items(self):
        return ["website:home", "website:plans", "website:terms", "website:privacy"]

    def location(self, item):
        return reverse(item)


class DentistSitemap(Sitemap):
    changefreq = "weekly"

    def items(self):
        from apps.landing.models import LandingPage

        return [lp for lp in LandingPage.objects.filter(is_published=True).select_related("dentist") if lp.is_live]

    def location(self, lp):
        return reverse("landing_public:page", args=[lp.dentist.slug])


SITEMAPS = {"static": StaticSitemap, "dentists": DentistSitemap}
