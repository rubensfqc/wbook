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


def unique_public_slug(text, taken):
    """A valid, non-reserved slug from `text` ("Dra. Ana Lima" -> "dra-ana-lima"), made unique with -2, -3….
    `taken(slug) -> bool` says whether a slug is already used."""
    from django.utils.text import slugify

    root = slugify(text or "")[:44].strip("-")
    if len(root) < 3:
        root = f"{root}-dentista".strip("-") if root else "dentista"
    if root in RESERVED_SLUGS:
        root = f"{root}-dentista"
    candidate, n = root, 2
    while taken(candidate) or not SLUG_RE.match(candidate):
        candidate = f"{root}-{n}"
        n += 1
    return candidate
