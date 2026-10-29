from django.contrib import admin

from .models import Appointment, AppointmentType, BookingSettings, TimeBlock, WorkingHours


@admin.register(Appointment)
class AppointmentAdmin(admin.ModelAdmin):
    list_display = ("start", "dentist", "type", "status", "source")
    list_filter = ("status", "source")


admin.site.register([AppointmentType, BookingSettings, TimeBlock, WorkingHours])
