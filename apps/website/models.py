import uuid

from django.db import models
from django.utils.translation import gettext_lazy as _


class PlatformLead(models.Model):
    ref = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    name = models.CharField(_("nome"), max_length=120)
    email = models.EmailField(_("e-mail"))
    whatsapp = models.CharField(_("WhatsApp"), max_length=30, blank=True)
    clinic_name = models.CharField(_("consultório"), max_length=120, blank=True)
    city = models.CharField(_("cidade"), max_length=80, blank=True)
    message = models.TextField(_("mensagem"), blank=True)
    contacted = models.BooleanField(_("contatado"), default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = _("interessado")
        verbose_name_plural = _("interessados")

    def __str__(self):
        return self.name
