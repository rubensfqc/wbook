from django import forms
from django.utils.translation import gettext_lazy as _

from apps.core.forms import StyledForm, StyledModelForm

from .models import LandingPage, Lead


class LandingPageForm(StyledModelForm):
    class Meta:
        model = LandingPage
        fields = ["is_published", "headline", "subheadline", "about", "services", "hero_image", "accent", "instagram", "website",
                  "insurance_note", "show_whatsapp_button", "show_calendar", "show_prices", "thank_you_message"]
        widgets = {"about": forms.Textarea(attrs={"rows": 5}), "services": forms.Textarea(attrs={"rows": 5})}


class GalleryForm(StyledForm):
    caption = forms.CharField(label=_("Legenda"), max_length=120, required=False)


class LeadForm(StyledModelForm):
    class Meta:
        model = Lead
        fields = ["name", "email", "whatsapp", "message", "notes"]
        widgets = {"message": forms.Textarea(attrs={"rows": 3}), "notes": forms.Textarea(attrs={"rows": 3})}


class LeadFollowForm(StyledModelForm):
    class Meta:
        model = Lead
        fields = ["status", "notes"]
        widgets = {"notes": forms.Textarea(attrs={"rows": 4})}


class ContactForm(StyledForm):
    name = forms.CharField(label=_("Nome"), max_length=120)
    email = forms.EmailField(label=_("E-mail"))
    whatsapp = forms.CharField(label=_("WhatsApp"), max_length=30, required=False)
    message = forms.CharField(label=_("Mensagem"), widget=forms.Textarea(attrs={"rows": 3}), max_length=2000)
    consent = forms.BooleanField(label=_("Autorizo o consultório a usar estes dados para entrar em contato."))
    company = forms.CharField(required=False, widget=forms.TextInput(attrs={"tabindex": "-1", "autocomplete": "off"}))
