from django import forms
from django.utils.translation import gettext_lazy as _
from .models import DoctorProfile, PatientProfile, BlockedPeriod, Appointment
from accounts.models import Seller


# ── Doctor ────────────────────────────────────────────────────────────────────

class DoctorProfileForm(forms.ModelForm):
    class Meta:
        model  = DoctorProfile
        fields = [
            'specialty', 'license_number', 'clinic_name', 'clinic_address',
            'bio', 'logo',
            'slot_duration_minutes', 'slots_visible_per_day',
            'work_start_time', 'work_end_time', 'cancel_hours_before',
            'reminder_hours_before',
        ]
        widgets = {
            'work_start_time': forms.TimeInput(attrs={'type': 'time'}),
            'work_end_time':   forms.TimeInput(attrs={'type': 'time'}),
            'bio':             forms.Textarea(attrs={'rows': 3}),
            'clinic_address':  forms.Textarea(attrs={'rows': 2}),
        }


WEEKDAY_CHOICES = [
    (0, 'Monday'), (1, 'Tuesday'), (2, 'Wednesday'),
    (3, 'Thursday'), (4, 'Friday'), (5, 'Saturday'), (6, 'Sunday'),
]


class WorkingDaysForm(forms.Form):
    working_days = forms.MultipleChoiceField(
        choices=WEEKDAY_CHOICES,
        widget=forms.CheckboxSelectMultiple,
        required=False,
        label=_('Working Days'),
    )

    def __init__(self, *args, doctor=None, **kwargs):
        super().__init__(*args, **kwargs)
        if doctor and doctor.working_days:
            self.fields['working_days'].initial = [str(d) for d in doctor.working_days]


# ── Patient ───────────────────────────────────────────────────────────────────

class PatientInviteForm(forms.Form):
    name     = forms.CharField(max_length=150, label=_('Full Name'))
    email    = forms.EmailField(label=_('Email'))
    notes    = forms.CharField(widget=forms.Textarea(attrs={'rows': 2}), required=False, label=_('Notes'))

    def clean_email(self):
        email = self.cleaned_data['email']
        if Seller.objects.filter(email=email).exists():
            raise forms.ValidationError(_('A user with this email already exists.'))
        return email


class PatientUpdateForm(forms.ModelForm):
    name  = forms.CharField(max_length=150)
    email = forms.EmailField()

    class Meta:
        model  = PatientProfile
        fields = ['date_of_birth', 'notes', 'is_active']
        widgets = {
            'date_of_birth': forms.DateInput(attrs={'type': 'date'}),
            'notes': forms.Textarea(attrs={'rows': 2}),
        }

    def __init__(self, *args, **kwargs):
        self.patient_user = kwargs.pop('patient_user', None)
        super().__init__(*args, **kwargs)
        if self.patient_user:
            self.fields['name'].initial  = self.patient_user.name
            self.fields['email'].initial = self.patient_user.email

    def save(self, commit=True):
        profile = super().save(commit=False)
        if self.patient_user:
            self.patient_user.name  = self.cleaned_data['name']
            self.patient_user.email = self.cleaned_data['email']
            if commit:
                self.patient_user.save()
        if commit:
            profile.save()
        return profile


# ── Blocked Period ────────────────────────────────────────────────────────────

class BlockedPeriodForm(forms.ModelForm):
    class Meta:
        model  = BlockedPeriod
        fields = ['start_date', 'end_date', 'reason']
        widgets = {
            'start_date': forms.DateInput(attrs={'type': 'date'}),
            'end_date':   forms.DateInput(attrs={'type': 'date'}),
        }


# ── Appointment (public booking) ──────────────────────────────────────────────

class PublicBookingForm(forms.Form):
    """Used by unregistered patients to request an appointment."""
    name  = forms.CharField(max_length=150, label=_('Full Name'))
    email = forms.EmailField(label=_('Email'))
    phone = forms.CharField(max_length=20, required=False, label=_('Phone (optional)'))
    notes = forms.CharField(widget=forms.Textarea(attrs={'rows': 2}), required=False, label=_('Notes'))


class AppointmentNoteForm(forms.ModelForm):
    class Meta:
        model  = Appointment
        fields = ['doctor_notes']
        widgets = {'doctor_notes': forms.Textarea(attrs={'rows': 3})}


# ── Operator: add/edit doctor ─────────────────────────────────────────────────

class OperatorDoctorForm(forms.ModelForm):
    """Operator creates / edits a doctor user."""
    name     = forms.CharField(max_length=150)
    email    = forms.EmailField()
    username = forms.CharField(max_length=150)
    password = forms.CharField(widget=forms.PasswordInput, required=False,
                               help_text=_('Leave blank to keep current password.'))

    class Meta:
        model  = DoctorProfile
        fields = ['specialty', 'clinic_name', 'trial_days', 'is_suspended']

    def __init__(self, *args, doctor_user=None, **kwargs):
        self.doctor_user = doctor_user
        super().__init__(*args, **kwargs)
        if doctor_user:
            self.fields['name'].initial     = doctor_user.name
            self.fields['email'].initial    = doctor_user.email
            self.fields['username'].initial = doctor_user.username
