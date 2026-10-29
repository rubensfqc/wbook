import re

from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _

RESERVED_SLUGS = {
    "app", "paciente", "operador", "conta", "arquivos", "calendario", "idioma", "planos", "obrigado",
    "termos", "privacidade", "admin", "static", "media", "robots.txt", "sitemap.xml", "api", "wbook",
    "contato", "login", "www", "suporte", "ajuda", "blog",
}
SLUG_RE = re.compile(r"^[a-z0-9](?:[a-z0-9-]{1,48}[a-z0-9])$")


def validate_public_slug(value):
    if not SLUG_RE.match(value or ""):
        raise ValidationError(_("Use de 3 a 50 letras minúsculas, números ou hífens."))
    if value in RESERVED_SLUGS:
        raise ValidationError(_("Este endereço é reservado. Escolha outro."))
