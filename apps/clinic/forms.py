from django import forms
from django.utils.translation import gettext_lazy as _

from apps.accounts.forms import UF_CHOICES
from apps.core.forms import DateInput, DentistScopedForm, StyledForm, StyledModelForm

from .models import Dentist, Invoice, PatientProfile, Treatment, TreatmentFile


class DentistProfileForm(StyledModelForm):
    name = forms.CharField(label=_("Seu nome"), max_length=120)
    username = forms.CharField(label=_("Usuário (para login)"), max_length=60, required=False)
    cro_state = forms.ChoiceField(label=_("UF do CRO"), choices=[("", "—")] + UF_CHOICES, required=False)
    state = forms.ChoiceField(label=_("Estado"), choices=[("", "—")] + UF_CHOICES, required=False)

    class Meta:
        model = Dentist
        fields = [
            "display_name", "clinic_name", "cro_number", "cro_state", "specialties", "logo", "photo", "phone", "whatsapp",
            "address", "city", "state", "maps_url", "opening_hours_text", "pix_key", "payment_link", "payment_note",
        ]
        widgets = {"specialties": forms.Textarea(attrs={"rows": 3})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["name"].initial = self.instance.user.name
        self.fields["username"].initial = self.instance.user.username

    def clean_username(self):
        from apps.accounts.models import User

        u = (self.cleaned_data.get("username") or "").strip().lower()
        if u and User.objects.filter(username=u).exclude(pk=self.instance.user_id).exists():
            raise forms.ValidationError(_("Este usuário já está em uso."))
        if "@" in u:
            raise forms.ValidationError(_("O usuário não pode ter @."))
        return u

    def save(self, commit=True):
        dentist = super().save(commit)
        user = dentist.user
        user.name = self.cleaned_data["name"]
        if self.cleaned_data.get("username"):
            user.username = self.cleaned_data["username"]
        user.save()
        return dentist


class AlertsForm(StyledModelForm):
    class Meta:
        model = Dentist
        fields = Dentist.ALERT_FIELDS + Dentist.PATIENT_ALERT_FIELDS


class PatientForm(StyledForm):
    name = forms.CharField(label=_("Nome"), max_length=120)
    email = forms.EmailField(label=_("E-mail"))
    phone = forms.CharField(label=_("Telefone"), max_length=30, required=False)
    whatsapp = forms.CharField(label=_("WhatsApp"), max_length=30, required=False)
    birth_date = forms.DateField(label=_("Data de nascimento"), required=False, widget=DateInput())
    cpf = forms.CharField(label=_("CPF"), max_length=14, required=False)
    send_invite = forms.BooleanField(label=_("Enviar convite para o portal do paciente agora"), required=False, initial=True)


class PatientEditForm(StyledModelForm):
    name = forms.CharField(label=_("Nome"), max_length=120)
    phone = forms.CharField(label=_("Telefone"), max_length=30, required=False)

    class Meta:
        model = PatientProfile
        fields = ["whatsapp", "birth_date", "cpf", "notes"]
        widgets = {"birth_date": DateInput(), "notes": forms.Textarea(attrs={"rows": 4})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["name"].initial = self.instance.user.name
        self.fields["phone"].initial = self.instance.user.phone

    def save(self, commit=True):
        p = super().save(commit)
        p.user.name = self.cleaned_data["name"]
        p.user.phone = self.cleaned_data["phone"]
        p.user.save(update_fields=["name", "phone"])
        return p


class TreatmentForm(DentistScopedForm):
    scoped_fields = {"patient": lambda d: PatientProfile.objects.for_dentist(d).select_related("user")}

    class Meta:
        model = Treatment
        fields = ["patient", "title", "description", "region", "status", "progress", "estimated_sessions", "budget",
                  "start_date", "expected_end", "is_visible_to_patient"]
        widgets = {"start_date": DateInput(), "expected_end": DateInput(), "description": forms.Textarea(attrs={"rows": 4})}


class TreatmentStatusForm(StyledModelForm):
    class Meta:
        model = Treatment
        fields = ["status", "progress"]


class UploadForm(StyledForm):
    phase = forms.ChoiceField(label=_("Fase (fotos)"), choices=TreatmentFile.Phase.choices, initial="BEFORE", required=False)
    taken_on = forms.DateField(label=_("Data"), required=False, widget=DateInput())
    title = forms.CharField(label=_("Título / legenda"), max_length=150, required=False)
    region = forms.CharField(label=_("Dente / região"), max_length=80, required=False)
    shared = forms.BooleanField(label=_("Compartilhar com o paciente"), required=False)


class MessageForm(StyledForm):
    text = forms.CharField(label=_("Mensagem"), widget=forms.Textarea(attrs={"rows": 3, "data-submit-shortcut": "1"}), max_length=4000)


class InvoiceForm(StyledModelForm):
    send_email = forms.BooleanField(label=_("Enviar por e-mail ao paciente"), required=False, initial=True)

    class Meta:
        model = Invoice
        fields = ["title", "amount", "issued_date", "due_date", "notes"]
        widgets = {"issued_date": DateInput(), "due_date": DateInput(), "notes": forms.Textarea(attrs={"rows": 3})}


class PatientSettingsForm(StyledModelForm):
    class Meta:
        model = PatientProfile
        fields = ["opt_out_reminders", "opt_out_treatment_updates"]
