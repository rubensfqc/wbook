import uuid
from decimal import Decimal

from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from apps.clinic.models import Dentist, PatientProfile, Treatment
from apps.core.storage import UploadTo


def _ref():
    return models.UUIDField(default=uuid.uuid4, unique=True, editable=False)


class QuoteQuerySet(models.QuerySet):
    def for_dentist(self, dentist):
        return self.filter(dentist=dentist)

    def for_patient(self, patient):
        return self.filter(patient=patient).exclude(status="DRAFT").filter(is_active=True)


class Quote(models.Model):
    class Status(models.TextChoices):
        DRAFT = "DRAFT", _("Rascunho")
        SENT = "SENT", _("Enviado")
        VIEWED = "VIEWED", _("Visualizado")
        ACCEPTED = "ACCEPTED", _("Aceito")
        DECLINED = "DECLINED", _("Recusado")

    ref = _ref()
    dentist = models.ForeignKey(Dentist, on_delete=models.CASCADE, related_name="quotes")
    lead = models.ForeignKey("landing.Lead", null=True, blank=True, on_delete=models.SET_NULL, related_name="quotes")
    patient = models.ForeignKey(PatientProfile, null=True, blank=True, on_delete=models.SET_NULL, related_name="quotes")
    treatment = models.ForeignKey(Treatment, null=True, blank=True, on_delete=models.SET_NULL, related_name="quotes")
    recipient_name = models.CharField(_("nome do paciente"), max_length=120)
    recipient_email = models.EmailField(_("e-mail do paciente"), blank=True)
    recipient_whatsapp = models.CharField(_("WhatsApp do paciente"), max_length=30, blank=True)
    uuid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    title = models.CharField(_("título"), max_length=150)
    intro = models.TextField(_("apresentação"), blank=True)
    payment_terms = models.TextField(_("condições de pagamento"), blank=True)
    timeline = models.CharField(_("prazo estimado"), max_length=150, blank=True)
    valid_until = models.DateField(_("válido até"), null=True, blank=True)
    attachment = models.FileField(_("PDF anexo"), upload_to=UploadTo("quotes"), blank=True)
    status = models.CharField(_("situação"), max_length=9, choices=Status.choices, default=Status.DRAFT)
    is_active = models.BooleanField(_("link ativo"), default=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    responded_at = models.DateTimeField(null=True, blank=True)
    response_note = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = QuoteQuerySet.as_manager()

    class Meta:
        ordering = ["-created_at"]
        verbose_name = _("orçamento")
        verbose_name_plural = _("orçamentos")

    def __str__(self):
        return self.title

    @property
    def total(self):
        return sum((i.amount for i in self.items.all()), Decimal("0"))

    @property
    def is_expired(self):
        return bool(self.valid_until and self.valid_until < timezone.localdate())

    @property
    def can_respond(self):
        return self.status in (self.Status.SENT, self.Status.VIEWED) and not self.is_expired and self.is_active


class QuoteItem(models.Model):
    ref = _ref()
    quote = models.ForeignKey(Quote, on_delete=models.CASCADE, related_name="items")
    description = models.CharField(_("procedimento"), max_length=200)
    region = models.CharField(_("dente / região"), max_length=60, blank=True)
    quantity = models.PositiveSmallIntegerField(_("qtd."), default=1)
    unit_amount = models.DecimalField(_("valor unitário"), max_digits=10, decimal_places=2, default=0)
    order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["order", "pk"]

    @property
    def amount(self):
        return (self.unit_amount or 0) * (self.quantity or 0)


class QuoteVisit(models.Model):
    quote = models.ForeignKey(Quote, on_delete=models.CASCADE, related_name="visits")
    token = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    started_at = models.DateTimeField(default=timezone.now)
    last_seen_at = models.DateTimeField(default=timezone.now)
    duration_s = models.PositiveIntegerField(default=0)
    max_scroll_pct = models.PositiveSmallIntegerField(default=0)
    device = models.CharField(max_length=20, blank=True)
    browser = models.CharField(max_length=30, blank=True)
    os = models.CharField(max_length=30, blank=True)
    referrer = models.CharField(max_length=300, blank=True)
    ip_hash = models.CharField(max_length=64, blank=True)
    is_returning = models.BooleanField(default=False)

    class Meta:
        ordering = ["-started_at"]


class QuoteEvent(models.Model):
    class Kind(models.TextChoices):
        PDF = "pdf", _("viu o PDF")
        DOWNLOAD = "download", _("baixou o PDF")
        WHATSAPP = "whatsapp", _("clicou no WhatsApp")
        ACCEPTED = "accepted", _("aceitou")
        DECLINED = "declined", _("recusou")

    ref = _ref()
    visit = models.ForeignKey(QuoteVisit, on_delete=models.CASCADE, related_name="events")
    kind = models.CharField(max_length=10, choices=Kind.choices)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["visit", "kind"], name="one_event_kind_per_visit")]
