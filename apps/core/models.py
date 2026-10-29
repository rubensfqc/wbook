from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _

# Free photo (Unsplash License) by Ozkan Guner: https://unsplash.com/photos/AQG6C_xYEpA
DEFAULT_HERO_IMAGE = "https://images.unsplash.com/photo-1643660527071-52e37cf7c7ea?auto=format&fit=crop&w=1920&q=70"


class PlatformSettings(models.Model):
    """Singleton (pk=1) edited by operators at /operador/configuracoes/."""

    default_trial_days = models.PositiveIntegerField(_("dias de teste padrão"), default=14)
    contact_email = models.EmailField(_("e-mail de contato"), blank=True)
    contact_whatsapp = models.CharField(_("WhatsApp de contato"), max_length=30, blank=True)
    home_hero_image_url = models.URLField(
        _("foto de fundo do topo da home"), max_length=500, blank=True, default=DEFAULT_HERO_IMAGE,
        help_text=_("Link de uma foto de odontologia (horizontal, ~1920px). Em branco, o topo fica com a cor da marca."),
    )
    instagram_url = models.URLField(_("Instagram"), blank=True)

    alert_email = models.EmailField(_("e-mail principal dos alertas"), blank=True)
    alert_email_secondary = models.EmailField(_("segundo e-mail dos alertas"), blank=True)
    alert_platform_lead = models.BooleanField(_("novo contato pelo site"), default=True)
    alert_new_dentist = models.BooleanField(_("novo dentista cadastrado"), default=True)
    alert_dentist_expiring = models.BooleanField(_("acesso de dentista acabando em 3 dias"), default=True)
    alert_data_import = models.BooleanField(_("importação de dados concluída"), default=True)

    plan1_name = models.CharField(_("plano 1 — nome"), max_length=60, default="Mensal")
    plan1_price = models.CharField(_("plano 1 — preço"), max_length=40, default="R$ 99/mês")
    plan1_description = models.TextField(_("plano 1 — descrição"), blank=True)
    plan1_payment_link = models.URLField(_("plano 1 — link de pagamento"), blank=True)
    plan2_name = models.CharField(_("plano 2 — nome"), max_length=60, default="Semestral")
    plan2_price = models.CharField(_("plano 2 — preço"), max_length=40, default="R$ 89/mês")
    plan2_description = models.TextField(_("plano 2 — descrição"), blank=True)
    plan2_payment_link = models.URLField(_("plano 2 — link de pagamento"), blank=True)
    plan3_name = models.CharField(_("plano 3 — nome"), max_length=60, default="Anual")
    plan3_price = models.CharField(_("plano 3 — preço"), max_length=40, default="R$ 79/mês")
    plan3_description = models.TextField(_("plano 3 — descrição"), blank=True)
    plan3_payment_link = models.URLField(_("plano 3 — link de pagamento"), blank=True)

    ALERT_FIELDS = ["alert_platform_lead", "alert_new_dentist", "alert_dentist_expiring", "alert_data_import"]

    class Meta:
        verbose_name = _("configurações da plataforma")
        verbose_name_plural = _("configurações da plataforma")

    def __str__(self):
        return "PlatformSettings"

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    @classmethod
    def get_solo(cls):
        obj, _created = cls.objects.get_or_create(pk=1)
        return obj

    @property
    def alert_recipients(self):
        first = self.alert_email or self.contact_email or settings.PLATFORM_CONTACT_EMAIL
        out = [first] if first else []
        if self.alert_email_secondary and self.alert_email_secondary not in out:
            out.append(self.alert_email_secondary)
        return out

    @property
    def plans(self):
        return [
            {
                "name": getattr(self, f"plan{i}_name"),
                "price": getattr(self, f"plan{i}_price"),
                "description": getattr(self, f"plan{i}_description"),
                "link": getattr(self, f"plan{i}_payment_link"),
            }
            for i in (1, 2, 3)
        ]
