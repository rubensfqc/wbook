"""Alerts that recipients can switch off (checkboxes). Everything else uses emails.send_templated."""

from .activity import log_action
from .emails import send_templated


def notify_dentist(dentist, switch, subject, template, ctx=None, reply_to=None, attachments=None):
    if not getattr(dentist, switch, True):
        log_action(None, "alert", "Alerta %(s)s desligado para %(d)s", s=switch, d=dentist.slug)
        return False
    lang = dentist.user.language
    ctx = {"dentist": dentist, **(ctx or {})}
    ok = send_templated(dentist.user.email, subject, template, ctx, reply_to=reply_to,
                        attachments=attachments, language=lang)
    log_action(None, "alert", "Alerta %(s)s enviado para %(d)s", s=switch, d=dentist.slug)
    return ok


def notify_patient(dentist, recipient, switch, subject, template, ctx=None, attachments=None, opt_out=None, treatment=None):
    """recipient: a PatientProfile or a Lead (visitor)."""
    if switch and not getattr(dentist, switch, True):
        return False
    if treatment is not None and not treatment.is_visible_to_patient:
        return False
    user = getattr(recipient, "user", None)
    if user is not None:
        if not user.has_usable_password():
            return False
        if opt_out and getattr(recipient, opt_out, False):
            return False
        email, lang = user.email, user.language
    else:
        email, lang = recipient.email, getattr(recipient, "language", None) or "pt-br"
    ctx = {"dentist": dentist, "recipient": recipient, **(ctx or {})}
    ok = send_templated(email, subject, template, ctx, reply_to=dentist.user.email,
                        attachments=attachments, language=lang)
    log_action(None, "alert", "E-mail %(t)s para paciente de %(d)s", t=template, d=dentist.slug)
    return ok


def notify_operator(switch, subject, template, ctx=None, reply_to=None):
    from .models import PlatformSettings

    ps = PlatformSettings.get_solo()
    if not getattr(ps, switch, True):
        return False
    to = ps.alert_recipients
    ok = send_templated(to, subject, template, ctx or {}, reply_to=reply_to, language="pt-br")
    log_action(None, "alert", "Alerta de operador %(s)s enviado para %(n)s endereço(s)", s=switch, n=len(to))
    return ok
