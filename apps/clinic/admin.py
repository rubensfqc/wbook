from django.contrib import admin

from .models import Dentist, Invoice, PatientProfile, Treatment, TreatmentEntry, TreatmentFile


@admin.register(Dentist)
class DentistAdmin(admin.ModelAdmin):
    list_display = ("clinic_name", "slug", "user", "paid_until", "is_suspended")
    search_fields = ("clinic_name", "slug", "user__email")


@admin.register(PatientProfile)
class PatientAdmin(admin.ModelAdmin):
    list_display = ("__str__", "dentist", "invited_at")
    search_fields = ("user__email", "user__name")


admin.site.register([Treatment, TreatmentFile, TreatmentEntry, Invoice])
