import uuid
from datetime import timedelta
from zoneinfo import ZoneInfo

from django.conf import settings
from django.db import models, transaction
from django.db.models import Max
from django.utils import timezone as djtz
from django.utils.functional import cached_property
from django.utils.translation import gettext_lazy as _

from apps.core.slugs import validate_public_slug
from apps.core.storage import UploadTo


def _ref():
    return models.UUIDField(default=uuid.uuid4, unique=True, editable=False)


class Dentist(models.Model):
    class FeedDetail(models.TextChoices):
        FIRST_NAME = "FIRST_NAME", _("Primeiro nome do paciente + tipo")
        FULL_NAME = "FULL_NAME", _("Nome completo + tipo")
        BUSY = "BUSY", _("Só \"Ocupado\"")

    ref = _ref()
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="dentist_profile")
    clinic_name = models.CharField(_("consultório / clínica"), max_length=120)
    display_name = models.CharField(_("nome profissional"), max_length=120, blank=True)
    slug = models.SlugField(_("endereço da página"), max_length=50, unique=True, validators=[validate_public_slug])
    logo = models.ImageField(_("logo"), upload_to=UploadTo("logos"), blank=True)
    photo = models.ImageField(_("sua foto"), upload_to=UploadTo("dentists"), blank=True)
    cro_number = models.CharField(_("CRO"), max_length=20, blank=True)
    cro_state = models.CharField(_("UF do CRO"), max_length=2, blank=True)
    specialties = models.TextField(_("especialidades (uma por linha)"), blank=True)
    phone = models.CharField(_("telefone"), max_length=30, blank=True)
    whatsapp = models.CharField(_("WhatsApp"), max_length=30, blank=True)
    address = models.CharField(_("endereço"), max_length=200, blank=True)
    city = models.CharField(_("cidade"), max_length=80, blank=True)
    state = models.CharField(_("estado"), max_length=2, blank=True)
    maps_url = models.URLField(_("link do mapa"), blank=True)
    opening_hours_text = models.CharField(_("horário de atendimento (texto)"), max_length=200, blank=True)
    timezone = models.CharField(_("fuso horário"), max_length=40, default="America/Sao_Paulo")
    pix_key = models.CharField(_("chave PIX"), max_length=120, blank=True)
    payment_link = models.URLField(_("link de pagamento"), blank=True)
    payment_note = models.CharField(_("observação de pagamento"), max_length=200, blank=True)

    trial_start_date = models.DateField(_("início do teste"), default=djtz.localdate)
    trial_days = models.PositiveIntegerField(_("dias de teste"), default=14)
    paid_until = models.DateField(_("pago até"), null=True, blank=True)
    plan_name = models.CharField(_("plano"), max_length=60, blank=True)
    is_suspended = models.BooleanField(_("suspenso"), default=False)
    onboarding_done = models.BooleanField(default=False)

    calendar_feed_token = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    feed_detail = models.CharField(_("detalhe no calendário sincronizado"), max_length=12,
                                   choices=FeedDetail.choices, default=FeedDetail.FIRST_NAME)

    # Alerts the dentist receives
    alert_new_request = models.BooleanField(_("novo pedido de agendamento (visitante)"), default=True)
    alert_patient_booked = models.BooleanField(_("paciente agendou"), default=True)
    alert_patient_changed = models.BooleanField(_("paciente remarcou ou cancelou"), default=True)
    alert_late_cancel = models.BooleanField(_("pedido de cancelamento em cima da hora"), default=True)
    alert_request_expired = models.BooleanField(_("pedido expirou sem resposta"), default=True)
    alert_patient_message = models.BooleanField(_("mensagem de paciente em um tratamento"), default=True)
    alert_quote_viewed = models.BooleanField(_("orçamento aberto pela primeira vez"), default=True)
    alert_quote_response = models.BooleanField(_("orçamento aceito ou recusado"), default=True)
    alert_invoice_paid = models.BooleanField(_("paciente avisou que pagou uma fatura"), default=True)
    alert_new_lead = models.BooleanField(_("novo contato pela página (sem agendamento)"), default=True)
    # E-mails patients receive
    patient_alert_reminder = models.BooleanField(_("lembrete 24 h antes da consulta"), default=True)
    patient_alert_treatment = models.BooleanField(_("novidades no tratamento (arquivos, mensagens)"), default=True)
    patient_alert_invoice = models.BooleanField(_("nova fatura"), default=True)

    created_at = models.DateTimeField(auto_now_add=True)

    ALERT_FIELDS = [
        "alert_new_request", "alert_patient_booked", "alert_patient_changed", "alert_late_cancel", "alert_request_expired",
        "alert_patient_message", "alert_quote_viewed", "alert_quote_response", "alert_invoice_paid", "alert_new_lead",
    ]
    PATIENT_ALERT_FIELDS = ["patient_alert_reminder", "patient_alert_treatment", "patient_alert_invoice"]

    class Meta:
        verbose_name = _("dentista")
        verbose_name_plural = _("dentistas")

    def __str__(self):
        return self.display_name or self.clinic_name

    @property
    def name(self):
        return self.display_name or self.user.name or self.clinic_name

    @cached_property
    def tzinfo(self):
        try:
            return ZoneInfo(self.timezone)
        except Exception:  # noqa: BLE001
            return ZoneInfo("America/Sao_Paulo")

    @property
    def trial_ends_on(self):
        return self.trial_start_date + timedelta(days=self.trial_days)

    @property
    def access_until(self):
        ends = [self.trial_ends_on]
        if self.paid_until:
            ends.append(self.paid_until)
        return max(ends)

    @property
    def is_paying(self):
        return bool(self.paid_until and self.paid_until >= djtz.localdate())

    @property
    def days_remaining(self):
        return (self.access_until - djtz.localdate()).days

    @property
    def can_access(self):
        return not self.is_suspended and self.access_until >= djtz.localdate()

    @property
    def contact_phone(self):
        return self.whatsapp or self.phone or self.user.phone

    @property
    def full_address(self):
        parts = [self.address, " - ".join(p for p in (self.city, self.state) if p)]
        return ", ".join(p for p in parts if p)


class PatientQuerySet(models.QuerySet):
    def for_dentist(self, dentist):
        return self.filter(dentist=dentist)


class PatientProfile(models.Model):
    ref = _ref()
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="patient_profile")
    dentist = models.ForeignKey(Dentist, on_delete=models.CASCADE, related_name="patients")
    birth_date = models.DateField(_("data de nascimento"), null=True, blank=True)
    cpf = models.CharField(_("CPF"), max_length=14, blank=True)
    whatsapp = models.CharField(_("WhatsApp"), max_length=30, blank=True)
    notes = models.TextField(_("anotações internas"), blank=True)
    invited_at = models.DateTimeField(null=True, blank=True)
    consent_at = models.DateTimeField(null=True, blank=True)
    consent_version = models.CharField(max_length=20, blank=True)
    opt_out_reminders = models.BooleanField(_("não quero receber lembretes"), default=False)
    opt_out_treatment_updates = models.BooleanField(_("não quero receber novidades do tratamento"), default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    objects = PatientQuerySet.as_manager()

    class Meta:
        verbose_name = _("paciente")
        verbose_name_plural = _("pacientes")
        ordering = ["user__name"]

    def __str__(self):
        return self.user.name or self.user.email

    @property
    def name(self):
        return self.user.name or self.user.email

    @property
    def email(self):
        return self.user.email

    @property
    def phone(self):
        return self.user.phone

    @property
    def contact_whatsapp(self):
        return self.whatsapp or self.user.phone

    @property
    def has_joined(self):
        return self.user.has_usable_password() and self.user.last_login is not None


class TreatmentQuerySet(models.QuerySet):
    def for_dentist(self, dentist):
        return self.filter(dentist=dentist)

    def for_patient(self, patient):
        return self.filter(patient=patient, is_visible_to_patient=True)


class Treatment(models.Model):
    class Status(models.TextChoices):
        PLANNED = "PLANNED", _("Planejado")
        IN_PROGRESS = "IN_PROGRESS", _("Em andamento")
        ON_HOLD = "ON_HOLD", _("Pausado")
        COMPLETED = "COMPLETED", _("Concluído")
        CANCELLED = "CANCELLED", _("Cancelado")

    ref = _ref()
    dentist = models.ForeignKey(Dentist, on_delete=models.CASCADE, related_name="treatments")
    patient = models.ForeignKey(PatientProfile, on_delete=models.CASCADE, related_name="treatments")
    title = models.CharField(_("título"), max_length=150)
    description = models.TextField(_("descrição"), blank=True)
    region = models.CharField(_("dente / região"), max_length=80, blank=True)
    status = models.CharField(_("situação"), max_length=12, choices=Status.choices, default=Status.PLANNED)
    progress = models.PositiveSmallIntegerField(_("progresso (%)"), default=0)
    estimated_sessions = models.PositiveSmallIntegerField(_("sessões previstas"), null=True, blank=True)
    budget = models.DecimalField(_("valor do tratamento"), max_digits=10, decimal_places=2, null=True, blank=True)
    start_date = models.DateField(_("início"), null=True, blank=True)
    expected_end = models.DateField(_("previsão de término"), null=True, blank=True)
    is_visible_to_patient = models.BooleanField(_("visível para o paciente"), default=True)
    source_quote = models.ForeignKey("quotes.Quote", null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = TreatmentQuerySet.as_manager()

    class Meta:
        verbose_name = _("tratamento")
        verbose_name_plural = _("tratamentos")
        ordering = ["-created_at"]

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        self.progress = max(0, min(100, self.progress or 0))
        if self.status == self.Status.COMPLETED:
            self.progress = 100
        super().save(*args, **kwargs)

    @property
    def sessions_done(self):
        return self.appointments.filter(status="COMPLETED").count()

    @property
    def is_active(self):
        return self.status in (self.Status.PLANNED, self.Status.IN_PROGRESS, self.Status.ON_HOLD)


class TreatmentFileQuerySet(models.QuerySet):
    def for_dentist(self, dentist):
        return self.filter(treatment__dentist=dentist)

    def for_patient(self, patient):
        return self.filter(treatment__patient=patient, treatment__is_visible_to_patient=True, shared=True)


class TreatmentFile(models.Model):
    class Kind(models.TextChoices):
        PDF = "PDF", _("Documento PDF")
        PHOTO = "PHOTO", _("Foto")

    class Phase(models.TextChoices):
        BEFORE = "BEFORE", _("Antes")
        DURING = "DURING", _("Durante")
        AFTER = "AFTER", _("Depois")

    ref = _ref()
    treatment = models.ForeignKey(Treatment, on_delete=models.CASCADE, related_name="files")
    kind = models.CharField(max_length=5, choices=Kind.choices)
    file = models.FileField(upload_to=UploadTo("treatments"))
    thumb = models.FileField(upload_to=UploadTo("treatments/thumbs"), blank=True)
    phase = models.CharField(_("fase"), max_length=6, choices=Phase.choices, blank=True)
    taken_on = models.DateField(_("data"), null=True, blank=True)
    title = models.CharField(_("título"), max_length=150, blank=True)
    caption = models.CharField(_("legenda"), max_length=200, blank=True)
    region = models.CharField(_("dente / região"), max_length=80, blank=True)
    shared = models.BooleanField(_("compartilhado com o paciente"), default=False)
    size = models.PositiveIntegerField(default=0)
    uploaded_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)

    objects = TreatmentFileQuerySet.as_manager()

    class Meta:
        verbose_name = _("arquivo do tratamento")
        verbose_name_plural = _("arquivos do tratamento")
        ordering = ["phase", "taken_on", "created_at"]

    def __str__(self):
        return self.title or self.caption or f"{self.get_kind_display()} #{self.pk}"

    @property
    def is_photo(self):
        return self.kind == self.Kind.PHOTO


class EntryQuerySet(models.QuerySet):
    def for_dentist(self, dentist):
        return self.filter(treatment__dentist=dentist)

    def for_patient(self, patient):
        return self.filter(treatment__patient=patient, treatment__is_visible_to_patient=True)


class TreatmentEntry(models.Model):
    class Kind(models.TextChoices):
        MSG = "MSG", _("Mensagem")
        EVT = "EVT", _("Evento")

    ref = _ref()
    treatment = models.ForeignKey(Treatment, on_delete=models.CASCADE, related_name="entries")
    author = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    author_role = models.CharField(max_length=10, blank=True)
    kind = models.CharField(max_length=3, choices=Kind.choices, default=Kind.MSG)
    text = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    objects = EntryQuerySet.as_manager()

    class Meta:
        ordering = ["created_at"]


class InvoiceQuerySet(models.QuerySet):
    def for_dentist(self, dentist):
        return self.filter(dentist=dentist)

    def for_patient(self, patient):
        return self.filter(treatment__patient=patient, treatment__is_visible_to_patient=True).exclude(status="CANCELLED")


class Invoice(models.Model):
    class Status(models.TextChoices):
        OPEN = "OPEN", _("Em aberto")
        PAID = "PAID", _("Paga")
        CANCELLED = "CANCELLED", _("Cancelada")

    ref = _ref()
    dentist = models.ForeignKey(Dentist, on_delete=models.CASCADE, related_name="invoices")
    treatment = models.ForeignKey(Treatment, on_delete=models.CASCADE, related_name="invoices")
    number = models.PositiveIntegerField(default=0)
    title = models.CharField(_("descrição"), max_length=150)
    amount = models.DecimalField(_("valor"), max_digits=10, decimal_places=2)
    notes = models.TextField(_("observações"), blank=True)
    issued_date = models.DateField(_("emissão"), default=djtz.localdate)
    due_date = models.DateField(_("vencimento"), null=True, blank=True)
    status = models.CharField(_("situação"), max_length=10, choices=Status.choices, default=Status.OPEN)
    patient_notified_paid_at = models.DateTimeField(null=True, blank=True)
    paid_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    objects = InvoiceQuerySet.as_manager()

    class Meta:
        verbose_name = _("fatura")
        verbose_name_plural = _("faturas")
        ordering = ["-number"]
        constraints = [models.UniqueConstraint(fields=["dentist", "number"], name="invoice_number_per_dentist")]

    def __str__(self):
        return f"{self.display_number} {self.title}"

    @property
    def display_number(self):
        return f"#{self.number:04d}"

    @property
    def patient(self):
        return self.treatment.patient

    def save(self, *args, **kwargs):
        self.dentist_id = self.treatment.dentist_id
        if not self.number:
            with transaction.atomic():
                Dentist.objects.select_for_update().filter(pk=self.dentist_id).first()
                last = Invoice.objects.filter(dentist_id=self.dentist_id).aggregate(m=Max("number"))["m"] or 0
                self.number = last + 1
                super().save(*args, **kwargs)
                return
        super().save(*args, **kwargs)
