from django import forms
from django.utils.translation import gettext_lazy as _

from apps.accounts.forms import UF_CHOICES
from apps.clinic.models import Dentist
from apps.core.forms import StyledForm, StyledModelForm
from apps.core.models import PlatformSettings


class PlatformSettingsForm(StyledModelForm):
    class Meta:
        model = PlatformSettings
        exclude = []


class DentistAddForm(StyledForm):
    name = forms.CharField(label=_("Nome"), max_length=120)
    display_name = forms.CharField(label=_("Nome profissional"), max_length=120, required=False)
    email = forms.EmailField(label=_("E-mail"))
    clinic_name = forms.CharField(label=_("Consultório"), max_length=120)
    slug = forms.CharField(label=_("Endereço da página"), max_length=50)
    whatsapp = forms.CharField(label=_("WhatsApp"), max_length=30, required=False)
    city = forms.CharField(label=_("Cidade"), max_length=80, required=False)
    state = forms.ChoiceField(label=_("Estado"), choices=[("", "—")] + UF_CHOICES, required=False)
    trial_days = forms.IntegerField(label=_("Dias de teste"), min_value=0, initial=14)

    def clean_email(self):
        from apps.accounts.models import User

        e = self.cleaned_data["email"].lower()
        if User.objects.filter(email=e).exists():
            raise forms.ValidationError(_("Já existe uma conta com este e-mail."))
        return e

    def clean_slug(self):
        from apps.core.slugs import validate_public_slug

        s = self.cleaned_data["slug"].lower().strip()
        validate_public_slug(s)
        if Dentist.objects.filter(slug=s).exists():
            raise forms.ValidationError(_("Este endereço já está em uso."))
        return s


class DentistEditForm(StyledModelForm):
    class Meta:
        model = Dentist
        fields = ["clinic_name", "display_name", "slug", "cro_number", "cro_state", "city", "state", "whatsapp", "trial_start_date",
                  "trial_days", "paid_until", "plan_name", "is_suspended"]
        widgets = {"trial_start_date": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
                   "paid_until": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d")}


class ExportForm(StyledForm):
    format = forms.ChoiceField(label=_("Formato"), choices=[("zip", _("ZIP (planilhas CSV + arquivos)")), ("toml", "TOML")])
    scope = forms.ChoiceField(label=_("O que exportar"), choices=[("all", _("Tudo")), ("some", _("Só os dentistas marcados"))],
                              widget=forms.RadioSelect, initial="all")
    dentists = forms.ModelMultipleChoiceField(label=_("Dentistas"), queryset=Dentist.objects.all(), required=False,
                                              widget=forms.CheckboxSelectMultiple)
    include_files = forms.BooleanField(label=_("Incluir arquivos (PDFs, fotos, logos)"), required=False, initial=True)
    include_passwords = forms.BooleanField(label=_("Incluir senhas (hash) para manter os logins"), required=False, initial=True)


class ImportForm(StyledForm):
    file = forms.FileField(label=_("Arquivo (.zip ou .toml)"))
