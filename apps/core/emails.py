"""Templated e-mail. Failures are logged, never raised."""

import logging
import re

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils import translation
from django.utils.html import strip_tags

from .activity import log_action

log = logging.getLogger("wbook")


def absolute(path):
    return f"{settings.SITE_URL}{path}"


def _html_to_text(html):
    html = re.sub(r'<a [^>]*href="([^"]+)"[^>]*>(.*?)</a>', r"\2: \1", html, flags=re.S)
    html = re.sub(r"<(br|/p|/div|/h[1-6]|/li|/tr)[^>]*>", "\n", html)
    text = strip_tags(html)
    text = re.sub(r"[ \t]+", " ", text)
    return re.sub(r"\n\s*\n+", "\n\n", text).strip()


def render_subject(subject, lang):
    """subject: str, lazy string, or (lazy, params) — translated in the recipient's language."""
    with translation.override(lang):
        if isinstance(subject, tuple):
            text, params = subject
            return str(text) % params
        return str(subject)


def send_templated(to, subject, template, ctx=None, reply_to=None, attachments=None, language=None):
    if isinstance(to, str):
        to = [to]
    to = [t for t in to if t]
    if not to:
        return False
    ctx = dict(ctx or {})
    ctx.setdefault("site_url", settings.SITE_URL)
    lang = language or settings.LANGUAGE_CODE
    try:
        with translation.override(lang):
            html = render_to_string(f"emails/{template}.html", ctx)
        subject = render_subject(subject, lang)
        msg = EmailMultiAlternatives(
            subject=subject,
            body=_html_to_text(html),
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=to,
            reply_to=[reply_to] if reply_to else None,
        )
        msg.attach_alternative(html, "text/html")
        for name, content, mimetype in attachments or []:
            msg.attach(name, content, mimetype)
        if settings.DEBUG and ctx.get("link"):
            # The console backend prints quoted-printable bodies: long links get "=" soft breaks and copying them
            # from the terminal breaks the token. Log the clean link for developers.
            log.warning("[DEV] link do e-mail '%s' para %s:\n%s", template, ", ".join(to), ctx["link"])
        msg.send()
        return True
    except Exception as e:  # noqa: BLE001
        log.exception("Falha ao enviar e-mail %s para %s", template, to)
        # Also in the activity log, so the operator sees it at /operador/atividade/ without opening the server log.
        log_action(None, "email", "Falha ao enviar e-mail '%(tpl)s' para %(to)s — %(err)s",
                   tpl=template, to=", ".join(to), err=f"{type(e).__name__}: {e}"[:200], level=logging.WARNING)
        return False
