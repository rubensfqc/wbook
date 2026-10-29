from django import forms
from django.forms import inlineformset_factory
from django.utils.translation import gettext_lazy as _

from apps.clinic.models import Dentist, PatientProfile, Treatment
from apps.core.forms import DateTimeInput, StyledForm, StyledModelForm, TimeInput

from .models import AppointmentType, BookingSettings, TimeBlock, WorkingHours


class BookingSettingsForm(StyledModelForm):
    class Meta:
        model = BookingSettings
        fields = ["patient_auto_confirm", "visitor_booking_enabled", "change_cutoff_hours", "min_lead_hours",
                  "booking_horizon_days", "slot_step_min", "pending_hold_hours", "max_active_per_patient", "max_visible_slots"]


class WorkingHoursForm(StyledModelForm):
    class Meta:
        model = WorkingHours
        fields = ["weekday", "start", "end"]
        widgets = {"start": TimeInput(), "end": TimeInput()}


class AppointmentTypeForm(StyledModelForm):
    class Meta:
        model = AppointmentType
        fields = ["name", "duration_min", "buffer_min", "price", "show_price", "visitor_bookable", "colour", "is_active", "order"]
        widgets = {"colour": forms.TextInput(attrs={"type": "color"})}


class _HoursBase(forms.BaseInlineFormSet):
    def clean(self):
        super().clean()
        rows = []
        for f in self.forms:
            if not hasattr(f, "cleaned_data") or not f.cleaned_data or f.cleaned_data.get("DELETE"):
                continue
            c = f.cleaned_data
            if c.get("start") and c.get("end"):
                rows.append((c["weekday"], c["start"], c["end"]))
        rows.sort()
        for (wa, _sa, ea), (wb, sb, _eb) in zip(rows, rows[1:]):
            if wa == wb and sb < ea:
                raise forms.ValidationError(_("Há horários sobrepostos no mesmo dia."))


HoursFormSet = inlineformset_factory(Dentist, WorkingHours, form=WorkingHoursForm, formset=_HoursBase, extra=2, can_delete=True)
TypeFormSet = inlineformset_factory(Dentist, AppointmentType, form=AppointmentTypeForm, extra=1, can_delete=True)


class TimeBlockForm(StyledModelForm):
    class Meta:
        model = TimeBlock
        fields = ["start", "end", "reason"]
        widgets = {"start": DateTimeInput(), "end": DateTimeInput()}


class DentistAppointmentForm(StyledForm):
    patient = forms.ModelChoiceField(label=_("Paciente"), queryset=PatientProfile.objects.none())
    type = forms.ModelChoiceField(label=_("Tipo"), queryset=AppointmentType.objects.none())
    start = forms.DateTimeField(label=_("Início"), widget=DateTimeInput())
    treatment = forms.ModelChoiceField(label=_("Tratamento"), queryset=Treatment.objects.none(), required=False)
    note = forms.CharField(label=_("Anotação interna"), required=False, widget=forms.Textarea(attrs={"rows": 2}))

    def __init__(self, *args, dentist=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["patient"].queryset = PatientProfile.objects.for_dentist(dentist).select_related("user")
        self.fields["type"].queryset = dentist.appointment_types.filter(is_active=True)
        self.fields["treatment"].queryset = Treatment.objects.for_dentist(dentist).filter(status__in=["PLANNED", "IN_PROGRESS", "ON_HOLD"])


class RescheduleForm(StyledForm):
    start = forms.DateTimeField(label=_("Novo início"), widget=DateTimeInput())


class FeedForm(StyledModelForm):
    class Meta:
        model = Dentist
        fields = ["feed_detail"]


class VisitorRequestForm(StyledForm):
    name = forms.CharField(label=_("Nome completo"), max_length=120)
    email = forms.EmailField(label=_("E-mail"))
    whatsapp = forms.CharField(label=_("WhatsApp"), max_length=30)
    message = forms.CharField(label=_("Mensagem (opcional)"), required=False, max_length=1000, widget=forms.Textarea(attrs={"rows": 3}))
    consent = forms.BooleanField(label=_("Autorizo o consultório a usar estes dados para entrar em contato e agendar minha consulta."))
    company = forms.CharField(required=False, widget=forms.TextInput(attrs={"tabindex": "-1", "autocomplete": "off"}))  # honeypot
