import uuid

from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from apps.clinic.models import Dentist, PatientProfile, Treatment


def _ref():
    return models.UUIDField(default=uuid.uuid4, unique=True, editable=False)


class DentistQuerySet(models.QuerySet):
    def for_dentist(self, dentist):
        return self.filter(dentist=dentist)


class BookingSettings(models.Model):
    CUTOFF_CHOICES = [(0, _("sem limite")), (12, _("12 horas")), (24, _("24 horas")), (48, _("48 horas")), (72, _("72 horas"))]

    ref = _ref()
    dentist = models.OneToOneField(Dentist, on_delete=models.CASCADE, related_name="booking")
    patient_auto_confirm = models.BooleanField(_("confirmar automaticamente agendamentos de pacientes"), default=True)
    visitor_booking_enabled = models.BooleanField(_("aceitar pedidos de agendamento de visitantes"), default=True)
    change_cutoff_hours = models.PositiveSmallIntegerField(
        _("pacientes podem remarcar/cancelar até"), choices=CUTOFF_CHOICES, default=24
    )
    min_lead_hours = models.PositiveSmallIntegerField(_("antecedência mínima para agendar (horas)"), default=2)
    booking_horizon_days = models.PositiveSmallIntegerField(_("agenda aberta para os próximos (dias)"), default=60)
    slot_step_min = models.PositiveSmallIntegerField(
        _("intervalo entre horários (min)"), choices=[(10, "10"), (15, "15"), (20, "20"), (30, "30"), (60, "60")], default=15
    )
    pending_hold_hours = models.PositiveSmallIntegerField(_("pedido de visitante segura o horário por (horas)"), default=48)
    max_active_per_patient = models.PositiveSmallIntegerField(_("consultas futuras por paciente (máx.)"), default=2)
    limit_empty_days = models.BooleanField(
        _("em dias sem nenhum agendamento, mostrar só 4 horários"), default=True
    )

    objects = DentistQuerySet.as_manager()

    class Meta:
        verbose_name = _("regras de agendamento")
        verbose_name_plural = _("regras de agendamento")


class WorkingHours(models.Model):
    WEEKDAYS = [(0, _("Segunda")), (1, _("Terça")), (2, _("Quarta")), (3, _("Quinta")), (4, _("Sexta")), (5, _("Sábado")), (6, _("Domingo"))]

    ref = _ref()
    dentist = models.ForeignKey(Dentist, on_delete=models.CASCADE, related_name="working_hours")
    weekday = models.PositiveSmallIntegerField(_("dia"), choices=WEEKDAYS)
    start = models.TimeField(_("início"))
    end = models.TimeField(_("fim"))

    objects = DentistQuerySet.as_manager()

    class Meta:
        ordering = ["weekday", "start"]
        verbose_name = _("horário de atendimento")
        verbose_name_plural = _("horários de atendimento")

    def clean(self):
        if self.start and self.end and self.start >= self.end:
            raise ValidationError(_("O fim precisa ser depois do início."))


class TimeBlock(models.Model):
    ref = _ref()
    dentist = models.ForeignKey(Dentist, on_delete=models.CASCADE, related_name="time_blocks")
    start = models.DateTimeField(_("início"))
    end = models.DateTimeField(_("fim"))
    reason = models.CharField(_("motivo"), max_length=120, blank=True)
    all_day = models.BooleanField(_("dia inteiro"), default=False)

    objects = DentistQuerySet.as_manager()

    class Meta:
        ordering = ["start"]
        verbose_name = _("bloqueio de agenda")
        verbose_name_plural = _("bloqueios de agenda")

    def clean(self):
        if self.start and self.end and self.start >= self.end:
            raise ValidationError(_("O fim precisa ser depois do início."))


class AppointmentType(models.Model):
    ref = _ref()
    dentist = models.ForeignKey(Dentist, on_delete=models.CASCADE, related_name="appointment_types")
    name = models.CharField(_("nome"), max_length=80)
    description = models.CharField(_("descrição"), max_length=200, blank=True)
    duration_min = models.PositiveSmallIntegerField(_("duração (min)"), default=30)
    buffer_min = models.PositiveSmallIntegerField(_("intervalo depois (min)"), default=0)
    colour = models.CharField(_("cor"), max_length=7, default="#0f766e")
    price = models.DecimalField(_("preço"), max_digits=10, decimal_places=2, null=True, blank=True)
    show_price = models.BooleanField(_("mostrar preço na página"), default=False)
    visitor_bookable = models.BooleanField(_("visitantes podem pedir"), default=True)
    is_active = models.BooleanField(_("ativo"), default=True)
    order = models.PositiveSmallIntegerField(_("ordem"), default=0)

    objects = DentistQuerySet.as_manager()

    class Meta:
        ordering = ["order", "name"]
        verbose_name = _("tipo de consulta")
        verbose_name_plural = _("tipos de consulta")

    def __str__(self):
        return self.name


class AppointmentQuerySet(models.QuerySet):
    def for_dentist(self, dentist):
        return self.filter(dentist=dentist)

    def for_patient(self, patient):
        return self.filter(patient=patient)

    def blocking(self):
        return self.filter(status__in=Appointment.BLOCKING_STATUSES)

    def upcoming(self):
        return self.filter(start__gte=timezone.now())


class Appointment(models.Model):
    class Status(models.TextChoices):
        PENDING = "PENDING", _("Aguardando confirmação")
        CONFIRMED = "CONFIRMED", _("Confirmada")
        REJECTED = "REJECTED", _("Recusada")
        EXPIRED = "EXPIRED", _("Expirada")
        CANCELLED = "CANCELLED", _("Cancelada")
        RESCHEDULED = "RESCHEDULED", _("Remarcada")
        COMPLETED = "COMPLETED", _("Realizada")
        NO_SHOW = "NO_SHOW", _("Faltou")

    class Source(models.TextChoices):
        PORTAL = "PORTAL", _("Portal do paciente")
        PUBLIC = "PUBLIC", _("Página pública")
        DENTIST = "DENTIST", _("Dentista")

    class By(models.TextChoices):
        PATIENT = "PATIENT", _("Paciente")
        DENTIST = "DENTIST", _("Dentista")
        SYSTEM = "SYSTEM", _("Sistema")

    BLOCKING_STATUSES = ("PENDING", "CONFIRMED")

    ref = _ref()
    dentist = models.ForeignKey(Dentist, on_delete=models.CASCADE, related_name="appointments")
    patient = models.ForeignKey(PatientProfile, null=True, blank=True, on_delete=models.CASCADE, related_name="appointments")
    lead = models.ForeignKey("landing.Lead", null=True, blank=True, on_delete=models.CASCADE, related_name="appointments")
    type = models.ForeignKey(AppointmentType, on_delete=models.RESTRICT, related_name="appointments", verbose_name=_("tipo"))
    treatment = models.ForeignKey(Treatment, null=True, blank=True, on_delete=models.SET_NULL, related_name="appointments",
                                  verbose_name=_("tratamento"))
    start = models.DateTimeField(_("início"))
    end = models.DateTimeField(_("fim"))
    status = models.CharField(_("situação"), max_length=12, choices=Status.choices, default=Status.PENDING)
    source = models.CharField(max_length=8, choices=Source.choices, default=Source.PORTAL)
    public_token = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    patient_note = models.TextField(_("mensagem do paciente"), blank=True)
    dentist_note = models.TextField(_("anotação interna"), blank=True)
    reject_reason = models.CharField(_("motivo"), max_length=200, blank=True)
    rescheduled_from = models.ForeignKey("self", null=True, blank=True, on_delete=models.SET_NULL, related_name="rescheduled_to")
    confirmed_at = models.DateTimeField(null=True, blank=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)
    cancelled_by = models.CharField(max_length=8, choices=By.choices, blank=True)
    late_cancel_requested_at = models.DateTimeField(null=True, blank=True)
    late_cancel_note = models.TextField(blank=True)
    reminder_sent_at = models.DateTimeField(null=True, blank=True)
    ics_sequence = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = AppointmentQuerySet.as_manager()

    class Meta:
        ordering = ["start"]
        verbose_name = _("consulta")
        verbose_name_plural = _("consultas")
        indexes = [models.Index(fields=["dentist", "start"])]
        constraints = [
            models.CheckConstraint(
                condition=(Q(patient__isnull=False, lead__isnull=True) | Q(patient__isnull=True, lead__isnull=False)),
                name="appointment_patient_xor_lead",
            )
        ]

    def __str__(self):
        return f"{self.type} — {self.person_name} — {timezone.localtime(self.start):%d/%m/%Y %H:%M}"

    @property
    def person_name(self):
        return self.patient.name if self.patient_id else self.lead.name

    @property
    def person_first_name(self):
        return (self.person_name or "").split(" ")[0]

    @property
    def person_email(self):
        return self.patient.email if self.patient_id else self.lead.email

    @property
    def person_whatsapp(self):
        return self.patient.contact_whatsapp if self.patient_id else self.lead.whatsapp

    @property
    def recipient(self):
        return self.patient if self.patient_id else self.lead

    @property
    def is_blocking(self):
        return self.status in self.BLOCKING_STATUSES

    @property
    def in_cutoff(self):
        hours = self.dentist.booking.change_cutoff_hours
        return (self.start - timezone.now()).total_seconds() < hours * 3600

    @property
    def can_change_online(self):
        return self.is_blocking and self.start > timezone.now() and not self.in_cutoff

    @property
    def ics_uid(self):
        root = self
        seen = set()
        while root.rescheduled_from_id and root.rescheduled_from_id not in seen:
            seen.add(root.pk)
            root = root.rescheduled_from
        return f"{root.ref}@wbook.com.br"

    @property
    def is_late_cancel_requested(self):
        return bool(self.late_cancel_requested_at) and self.is_blocking
