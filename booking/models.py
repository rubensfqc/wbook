from datetime import timedelta, date, time, datetime
from django.db import models
from django.conf import settings
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django.core.validators import MinValueValidator, MaxValueValidator


# ─────────────────────────────────────────────────────────────────────────────
# Platform (Singleton)
# ─────────────────────────────────────────────────────────────────────────────

class PlatformSettings(models.Model):
    default_trial_days = models.PositiveIntegerField(
        default=14,
        help_text=_('Default trial duration for new doctors.'),
    )
    platform_name = models.CharField(max_length=100, default='wbook365')
    support_email = models.EmailField(default='support@wbook365.com')

    class Meta:
        verbose_name = _('Platform Settings')

    @classmethod
    def get_solo(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    def __str__(self):
        return f'Platform Settings (trial: {self.default_trial_days}d)'


# ─────────────────────────────────────────────────────────────────────────────
# DoctorProfile  (extends Seller via OneToOne)
# ─────────────────────────────────────────────────────────────────────────────

class DoctorProfile(models.Model):
    DAYS = [
        (0, _('Monday')), (1, _('Tuesday')), (2, _('Wednesday')),
        (3, _('Thursday')), (4, _('Friday')), (5, _('Saturday')), (6, _('Sunday')),
    ]

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='doctor_profile',
    )

    # Profile
    specialty        = models.CharField(max_length=120, blank=True)
    license_number   = models.CharField(max_length=60, blank=True)
    clinic_name      = models.CharField(max_length=200, blank=True)
    clinic_address   = models.TextField(blank=True)
    bio              = models.TextField(blank=True)
    logo             = models.ImageField(upload_to='doctor_logos/', null=True, blank=True)
    email_verified   = models.BooleanField(default=False)

    # Trial / SaaS access
    trial_start_date = models.DateField(null=True, blank=True)
    trial_days       = models.PositiveIntegerField(default=14)
    is_suspended     = models.BooleanField(default=False)

    # Schedule config
    slot_duration_minutes = models.PositiveIntegerField(
        default=30,
        help_text=_('Duration of each appointment slot in minutes.'),
    )
    slots_visible_per_day = models.PositiveIntegerField(
        default=3,
        help_text=_('Max slots shown to patients per day.'),
    )
    work_start_time = models.TimeField(default=time(8, 0))
    work_end_time   = models.TimeField(default=time(17, 0))
    working_days    = models.JSONField(
        default=list,
        help_text=_('List of weekday numbers (0=Mon … 6=Sun).'),
    )

    # Cancellation policy
    cancel_hours_before = models.PositiveIntegerField(
        default=24,
        choices=[(24, '24 hours'), (48, '48 hours')],
        help_text=_('Minimum hours before appointment that patient can cancel.'),
    )

    # Notifications
    reminder_hours_before = models.PositiveIntegerField(
        default=24,
        choices=[(1, '1 hour'), (2, '2 hours'), (6, '6 hours'), (12, '12 hours'), (24, '24 hours'), (48, '48 hours')],
    )

    # ── Trial helpers ─────────────────────────────────────────────────────────

    @property
    def trial_expires_on(self):
        if self.trial_start_date:
            return self.trial_start_date + timedelta(days=self.trial_days)
        return None

    @property
    def trial_is_active(self):
        if not self.trial_start_date:
            return True
        return timezone.now().date() <= self.trial_expires_on

    @property
    def days_remaining(self):
        if not self.trial_start_date:
            return None
        return max(0, (self.trial_expires_on - timezone.now().date()).days)

    @property
    def can_access(self):
        return not self.is_suspended and self.trial_is_active

    def save(self, *args, **kwargs):
        if not self.trial_start_date:
            self.trial_start_date = timezone.now().date()
            try:
                self.trial_days = PlatformSettings.get_solo().default_trial_days
            except Exception:
                self.trial_days = 14
        if not self.working_days:
            self.working_days = [0, 1, 2, 3, 4]  # Mon–Fri default
        super().save(*args, **kwargs)

    def __str__(self):
        return f'Dr. {self.user.name or self.user.email}'

    def get_all_slots_for_date(self, target_date):
        """
        Return every theoretical slot for target_date (ignores taken/count).
        Returns [] if the day is not a working day.
        """
        if target_date.weekday() not in (self.working_days or [0, 1, 2, 3, 4]):
            return []
        slots   = []
        current = datetime.combine(target_date, self.work_start_time)
        end     = datetime.combine(target_date, self.work_end_time)
        delta   = timedelta(minutes=self.slot_duration_minutes)
        while current + delta <= end:
            slots.append(current)
            current += delta
        return slots

    def spread_slots(self, available_slots):
        """
        From a list of available (not-taken) slots, pick exactly
        slots_visible_per_day entries spread evenly across the day.
        e.g. 4 wanted from 16 available -> indices 0, 5, 10, 15
        """
        n    = self.slots_visible_per_day
        pool = available_slots
        if not pool:
            return []
        if len(pool) <= n:
            return pool
        step   = (len(pool) - 1) / (n - 1) if n > 1 else 0
        chosen = [pool[round(i * step)] for i in range(n)]
        seen, result = set(), []
        for s in chosen:
            if s not in seen:
                seen.add(s)
                result.append(s)
        return result

    def get_slots_for_date(self, target_date):
        """Convenience: theoretical slots capped to slots_visible_per_day (no spread, no taken filter)."""
        return self.get_all_slots_for_date(target_date)[:self.slots_visible_per_day]


# ─────────────────────────────────────────────────────────────────────────────
# PatientProfile
# ─────────────────────────────────────────────────────────────────────────────

class PatientProfile(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='patient_profile',
    )
    doctor = models.ForeignKey(
        DoctorProfile,
        on_delete=models.CASCADE,
        related_name='patients',
    )
    date_of_birth = models.DateField(null=True, blank=True)
    notes         = models.TextField(blank=True, help_text=_('Doctor-visible notes about this patient.'))
    is_active     = models.BooleanField(default=True)
    created_at    = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'{self.user.name or self.user.email} → {self.doctor}'


# ─────────────────────────────────────────────────────────────────────────────
# OperatorProfile
# ─────────────────────────────────────────────────────────────────────────────

class OperatorProfile(models.Model):
    user         = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='operator_profile',
    )
    department   = models.CharField(max_length=100, blank=True)
    access_level = models.IntegerField(default=1)

    def __str__(self):
        return f'Operator: {self.user.email}'


# ─────────────────────────────────────────────────────────────────────────────
# BlockedPeriod
# ─────────────────────────────────────────────────────────────────────────────

class BlockedPeriod(models.Model):
    doctor     = models.ForeignKey(DoctorProfile, on_delete=models.CASCADE, related_name='blocked_periods')
    start_date = models.DateField()
    end_date   = models.DateField()
    reason     = models.CharField(max_length=200, blank=True)

    def __str__(self):
        return f'{self.doctor} blocked {self.start_date} – {self.end_date}'

    def contains(self, d: date) -> bool:
        return self.start_date <= d <= self.end_date


# ─────────────────────────────────────────────────────────────────────────────
# Lead  (walk-in visitor who filled Step 1 of the public booking page)
# ─────────────────────────────────────────────────────────────────────────────

class Lead(models.Model):
    class Status(models.TextChoices):
        NEW        = 'NEW',        _('New')
        CONTACTED  = 'CONTACTED',  _('Contacted')
        CONVERTED  = 'CONVERTED',  _('Converted')   # became an Appointment
        LOST       = 'LOST',       _('Lost')

    doctor     = models.ForeignKey(
        DoctorProfile, on_delete=models.CASCADE, related_name='leads'
    )

    # Walk-in identity — captured at Step 1
    name       = models.CharField(max_length=150)
    email      = models.EmailField()
    phone      = models.CharField(max_length=30, blank=True)
    notes      = models.TextField(blank=True, help_text=_('Reason for visit entered by the patient.'))

    status     = models.CharField(
        max_length=20, choices=Status.choices, default=Status.NEW
    )

    # Set when the lead books a slot and converts to an appointment
    appointment = models.OneToOneField(
        'Appointment',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='lead',
    )

    created_at  = models.DateTimeField(auto_now_add=True)
    updated_at  = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'Lead: {self.name} <{self.email}> -> {self.doctor} [{self.status}]'

    @property
    def is_converted(self):
        return self.status == self.Status.CONVERTED


# ─────────────────────────────────────────────────────────────────────────────
# Appointment
# ─────────────────────────────────────────────────────────────────────────────

class Appointment(models.Model):
    class Status(models.TextChoices):
        PENDING   = 'PENDING',   _('Pending')
        CONFIRMED = 'CONFIRMED', _('Confirmed')
        REJECTED  = 'REJECTED',  _('Rejected')
        CANCELLED = 'CANCELLED', _('Cancelled')
        COMPLETED = 'COMPLETED', _('Completed')

    doctor      = models.ForeignKey(DoctorProfile,  on_delete=models.CASCADE, related_name='appointments')
    # patient_user can be NULL for unregistered walk-ins
    patient_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='appointments',
    )
    # For unregistered patients
    patient_name  = models.CharField(max_length=150, blank=True)
    patient_email = models.EmailField(blank=True)
    patient_phone = models.CharField(max_length=20, blank=True)

    start_time = models.DateTimeField()
    end_time   = models.DateTimeField()
    status     = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    notes      = models.TextField(blank=True)
    doctor_notes = models.TextField(blank=True)

    created_at  = models.DateTimeField(auto_now_add=True)
    updated_at  = models.DateTimeField(auto_now=True)

    reminder_sent = models.BooleanField(default=False)

    class Meta:
        ordering = ['start_time']

    def __str__(self):
        name = self.patient_user.name if self.patient_user else self.patient_name
        return f'{name} @ {self.start_time:%Y-%m-%d %H:%M} [{self.status}]'

    @property
    def display_name(self):
        if self.patient_user:
            return self.patient_user.name or self.patient_user.email
        return self.patient_name or self.patient_email

    @property
    def is_registered(self):
        return self.patient_user is not None

    def can_cancel(self):
        hours = self.doctor.cancel_hours_before
        return timezone.now() < (timezone.make_aware(
            datetime.combine(self.start_time.date(), self.start_time.time())
        ) - timedelta(hours=hours)) if timezone.is_naive(self.start_time) else \
               timezone.now() < (self.start_time - timedelta(hours=hours))
