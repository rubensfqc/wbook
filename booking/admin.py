from django.contrib import admin
from .models import (
    PlatformSettings, DoctorProfile, PatientProfile,
    OperatorProfile, BlockedPeriod, Appointment,
)


@admin.register(PlatformSettings)
class PlatformSettingsAdmin(admin.ModelAdmin):
    list_display = ('platform_name', 'default_trial_days', 'support_email')


@admin.register(DoctorProfile)
class DoctorProfileAdmin(admin.ModelAdmin):
    list_display  = ('user', 'specialty', 'clinic_name', 'trial_is_active', 'is_suspended')
    list_filter   = ('is_suspended',)
    search_fields = ('user__email', 'user__name', 'clinic_name')
    readonly_fields = ('trial_expires_on', 'days_remaining', 'trial_is_active', 'can_access')


@admin.register(PatientProfile)
class PatientProfileAdmin(admin.ModelAdmin):
    list_display  = ('user', 'doctor', 'is_active', 'created_at')
    list_filter   = ('is_active',)
    search_fields = ('user__email', 'user__name')


@admin.register(OperatorProfile)
class OperatorProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'department', 'access_level')


@admin.register(BlockedPeriod)
class BlockedPeriodAdmin(admin.ModelAdmin):
    list_display = ('doctor', 'start_date', 'end_date', 'reason')


@admin.register(Appointment)
class AppointmentAdmin(admin.ModelAdmin):
    list_display  = ('display_name', 'doctor', 'start_time', 'status', 'is_registered')
    list_filter   = ('status',)
    search_fields = ('patient_name', 'patient_email', 'patient_user__email')
    date_hierarchy = 'start_time'
