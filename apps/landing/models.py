import uuid

from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.clinic.models import Dentist, PatientProfile
from apps.core.storage import UploadTo

ACCENTS = {
    "teal": "#0f766e",
    "ocean": "#1d4ed8",
    "sage": "#4d7c5a",
    "plum": "#7e3a6e",
    "coral": "#c2410c",
    "slate": "#334155",
}


def _ref():
    return models.UUIDField(default=uuid.uuid4, unique=True, editable=False)


class LandingPage(models.Model):
    ACCENT_CHOICES = [(k, k.capitalize()) for k in ACCENTS]

    ref = _ref()
    dentist = models.OneToOneField(Dentist, on_delete=models.CASCADE, related_name="landing")
    is_published = models.BooleanField(_("página publicada"), default=False)
    headline = models.CharField(_("título"), max_length=120, blank=True)
    subheadline = models.CharField(_("subtítulo"), max_length=200, blank=True)
    about = models.TextField(_("sobre"), blank=True)
    services = models.TextField(_("tratamentos oferecidos (um por linha)"), blank=True)
    hero_image = models.ImageField(_("foto de capa"), upload_to=UploadTo("landing"), blank=True)
    accent = models.CharField(_("cor de destaque"), max_length=10, choices=ACCENT_CHOICES, default="teal")
    instagram = models.URLField(_("Instagram"), blank=True)
    website = models.URLField(_("site"), blank=True)
    show_whatsapp_button = models.BooleanField(_("mostrar botão de WhatsApp"), default=True)
    show_calendar = models.BooleanField(_("mostrar agenda online"), default=True)
    show_prices = models.BooleanField(_("mostrar preços dos tipos de consulta"), default=False)
    insurance_note = models.CharField(_("convênios aceitos"), max_length=200, blank=True)
    thank_you_message = models.CharField(_("mensagem depois do pedido"), max_length=200, blank=True)

    class Meta:
        verbose_name = _("página pública")
        verbose_name_plural = _("páginas públicas")

    @property
    def accent_hex(self):
        return ACCENTS.get(self.accent, ACCENTS["teal"])

    @property
    def is_live(self):
        return self.is_published and self.dentist.can_access


class GalleryImage(models.Model):
    MAX = 12
    ref = _ref()
    landing = models.ForeignKey(LandingPage, on_delete=models.CASCADE, related_name="gallery")
    image = models.ImageField(upload_to=UploadTo("landing/gallery"))
    caption = models.CharField(_("legenda"), max_length=120, blank=True)
    order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["order", "pk"]


class LeadQuerySet(models.QuerySet):
    def for_dentist(self, dentist):
        return self.filter(dentist=dentist)


class Lead(models.Model):
    class Source(models.TextChoices):
        BOOKING = "BOOKING", _("Agendamento online")
        LANDING = "LANDING", _("Contato pela página")
        MANUAL = "MANUAL", _("Cadastro manual")

    class Status(models.TextChoices):
        NEW = "NEW", _("Novo")
        CONTACTED = "CONTACTED", _("Contatado")
        SCHEDULED = "SCHEDULED", _("Consulta marcada")
        QUOTE = "QUOTE", _("Orçamento enviado")
        WON = "WON", _("Virou paciente")
        LOST = "LOST", _("Perdido")

    ref = _ref()
    dentist = models.ForeignKey(Dentist, on_delete=models.CASCADE, related_name="leads")
    name = models.CharField(_("nome"), max_length=120)
    email = models.EmailField(_("e-mail"))
    whatsapp = models.CharField(_("WhatsApp"), max_length=30, blank=True)
    message = models.TextField(_("mensagem"), blank=True)
    consent = models.BooleanField(default=False)
    language = models.CharField(max_length=8, default="pt-br")
    source = models.CharField(_("origem"), max_length=8, choices=Source.choices, default=Source.LANDING)
    status = models.CharField(_("situação"), max_length=10, choices=Status.choices, default=Status.NEW)
    notes = models.TextField(_("anotações"), blank=True)
    converted_patient = models.ForeignKey(PatientProfile, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    ip_hash = models.CharField(max_length=64, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = LeadQuerySet.as_manager()

    class Meta:
        ordering = ["-created_at"]
        verbose_name = _("lead")
        verbose_name_plural = _("leads")

    def __str__(self):
        return self.name

    def advance(self, status):
        """Move forward in the pipeline only (never back from WON/LOST)."""
        order = ["NEW", "CONTACTED", "SCHEDULED", "QUOTE", "WON"]
        if self.status in ("WON", "LOST"):
            return
        if status == "LOST" or order.index(status) > order.index(self.status):
            self.status = status
            self.save(update_fields=["status", "updated_at"])
