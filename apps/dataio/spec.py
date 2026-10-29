"""Tables of the wbook export, in import order. FK columns hold the key of the referenced row, never database ids."""

from dataclasses import dataclass, field

from django.apps import apps
from django.db import models

FORMAT = "wbook-export"
VERSION = 1


@dataclass
class Table:
    name: str
    model_label: str
    key: str = "ref"
    exclude: tuple = ()
    late_fks: tuple = ()  # resolved in a second pass (self references, cycles)
    platform: bool = False  # only in "everything" exports
    extra_fields: tuple = ()  # non-editable fields that still travel (tokens)
    _fields: list = field(default=None, repr=False)

    @property
    def model(self):
        return apps.get_model(self.model_label)

    @property
    def fields(self):
        if self._fields is None:
            out = []
            for f in self.model._meta.concrete_fields:
                if f.name in ("id",) and self.key != "id":
                    continue
                if f.name in self.exclude:
                    continue
                out.append(f)
            self._fields = out
        return self._fields

    def fk_fields(self):
        return [f for f in self.fields if isinstance(f, models.ForeignKey)]

    def file_fields(self):
        return [f for f in self.fields if isinstance(f, models.FileField)]


TABLES = [
    Table("platform_settings", "core.PlatformSettings", key="id", platform=True),
    Table("users", "accounts.User", key="email", exclude=("is_staff", "is_superuser")),
    Table("dentists", "clinic.Dentist"),
    Table("booking_settings", "agenda.BookingSettings"),
    Table("working_hours", "agenda.WorkingHours"),
    Table("time_blocks", "agenda.TimeBlock"),
    Table("appointment_types", "agenda.AppointmentType"),
    Table("landing_pages", "landing.LandingPage"),
    Table("gallery_images", "landing.GalleryImage"),
    Table("patients", "clinic.PatientProfile"),
    Table("leads", "landing.Lead"),
    Table("treatments", "clinic.Treatment", late_fks=("source_quote",)),
    Table("treatment_files", "clinic.TreatmentFile"),
    Table("treatment_entries", "clinic.TreatmentEntry"),
    Table("appointments", "agenda.Appointment", late_fks=("rescheduled_from",)),
    Table("invoices", "clinic.Invoice"),
    Table("quotes", "quotes.Quote", key="uuid"),
    Table("quote_items", "quotes.QuoteItem"),
    Table("quote_visits", "quotes.QuoteVisit", key="token"),
    Table("quote_events", "quotes.QuoteEvent"),
    Table("platform_leads", "website.PlatformLead", platform=True),
]
BY_MODEL = {t.model_label.lower(): t for t in TABLES}
BY_NAME = {t.name: t for t in TABLES}


def table_for_model(model):
    return BY_MODEL.get(model._meta.label_lower)


def tenant_of(obj):
    """Dentist id that owns obj (None for users without profile / platform rows)."""
    label = obj._meta.label_lower
    if label == "clinic.dentist":
        return obj.pk
    if label == "accounts.user":
        if hasattr(obj, "dentist_profile"):
            return obj.dentist_profile.pk
        if hasattr(obj, "patient_profile"):
            return obj.patient_profile.dentist_id
        return None
    for attr in ("dentist_id",):
        if hasattr(obj, attr):
            return getattr(obj, attr)
    for parent in ("treatment", "quote", "landing", "visit"):
        if hasattr(obj, parent + "_id") and getattr(obj, parent + "_id"):
            return tenant_of(getattr(obj, parent))
    return None


def scoped_queryset(table, dentists):
    """dentists: list of Dentist or None (= everything)."""
    m = table.model
    qs = m.objects.all()
    if table.name == "users":
        from django.db.models import Q

        qs = qs.filter(role__in=["DENTIST", "PATIENT"], is_staff=False, is_superuser=False)
        if dentists is not None:
            qs = qs.filter(Q(dentist_profile__in=dentists) | Q(patient_profile__dentist__in=dentists))
        return qs.order_by("pk")
    if dentists is None:
        return qs.order_by("pk")
    paths = {
        "dentists": "pk__in", "gallery_images": "landing__dentist__in", "treatment_files": "treatment__dentist__in",
        "treatment_entries": "treatment__dentist__in", "quote_items": "quote__dentist__in", "quote_visits": "quote__dentist__in",
        "quote_events": "visit__quote__dentist__in",
    }
    path = paths.get(table.name, "dentist__in")
    ids = [d.pk for d in dentists]
    return qs.filter(**{path: ids}).order_by("pk")
