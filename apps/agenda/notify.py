"""E-mails for agenda events. Called from services via transaction.on_commit.

Dates and links are built inside the recipient's language (translation.override), so a patient who chose English
gets "Tuesday, 04/11/2026, from 14:00 to 14:30" while the dentist gets the Portuguese version.
"""

from django.urls import reverse
from django.utils import translation
from django.utils.translation import gettext_lazy as _

from apps.core.emails import absolute, send_templated

from . import calendar_links as cl


def _lang_person(appt):
    return appt.patient.user.language if appt.patient_id else appt.lead.language


def _ctx(appt, lang, **extra):
    with translation.override(lang):
        return {
            "appt": appt,
            "dentist": appt.dentist,
            "when": cl.when_text(appt),
            "links": cl.links_for(appt),
            "page_link": cl.page_url(appt),
            "agenda_link": absolute(reverse("agenda:detail", args=[appt.pk])),
            **extra,
        }


def _to_dentist(appt, switch, subject, template, reply_to=None, **extra):
    from apps.core.activity import log_action

    d = appt.dentist
    if not getattr(d, switch, True):
        log_action(None, "alert", "Alerta %(s)s desligado para %(d)s", s=switch, d=d.slug)
        return False
    lang = d.user.language
    ctx = _ctx(appt, lang, **extra)
    subject = (subject[0], {k: (ctx["when"] if v == "__when__" else v) for k, v in subject[1].items()}) if isinstance(subject, tuple) else subject
    ok = send_templated(d.user.email, subject, template, ctx, reply_to=reply_to, language=lang)
    log_action(None, "alert", "Alerta %(s)s enviado para %(d)s", s=switch, d=d.slug)
    return ok


def _to_person(appt, subject, template, cancel=False, **extra):
    lang = _lang_person(appt)
    ctx = _ctx(appt, lang, **extra)
    if isinstance(subject, tuple):
        subject = (subject[0], {k: (ctx["when"] if v == "__when__" else v) for k, v in subject[1].items()})
    return send_templated(appt.person_email, subject, template, ctx, reply_to=appt.dentist.user.email,
                          attachments=cl.ics_attachment(appt, cancel=cancel), language=lang)


def request_received(appt):
    _to_dentist(appt, "alert_new_request", (_("Novo pedido de consulta: %(n)s"), {"n": appt.person_name}),
                "booking_request_dentist", reply_to=appt.person_email)
    _to_person(appt, _("Recebemos seu pedido de consulta"), "booking_request_received")


def confirmed(appt, by_dentist=False):
    _to_person(appt, (_("Consulta confirmada: %(w)s"), {"w": "__when__"}), "booking_confirmed")
    if not by_dentist:
        _to_dentist(appt, "alert_patient_booked", (_("%(n)s agendou uma consulta"), {"n": appt.person_name}), "booking_new_dentist")


def rejected(appt):
    _to_person(appt, _("Sobre seu pedido de consulta"), "booking_rejected", cancel=True)


def expired(appt):
    _to_person(appt, _("Seu pedido de consulta expirou"), "booking_expired", cancel=True)
    _to_dentist(appt, "alert_request_expired", (_("Pedido expirou sem resposta: %(n)s"), {"n": appt.person_name}),
                "booking_expired_dentist")


def changed(new, old=None, by="PATIENT"):
    """Reschedule (new + old) or cancellation (new is the cancelled row)."""
    cancelled = new.status == "CANCELLED"
    if cancelled:
        subject = _("Consulta cancelada")
        dsubject = (_("%(n)s cancelou a consulta"), {"n": new.person_name})
    else:
        subject = (_("Consulta remarcada: %(w)s"), {"w": "__when__"})
        dsubject = (_("%(n)s remarcou a consulta"), {"n": new.person_name})
    old_when = None
    if old is not None:
        with translation.override(_lang_person(new)):
            old_when = cl.when_text(old)
    _to_person(new, subject, "booking_changed", cancel=cancelled, old=old, old_when=old_when, cancelled=cancelled)
    if by == "PATIENT":
        _to_dentist(new, "alert_patient_changed", dsubject, "booking_changed_dentist", old=old, cancelled=cancelled)


def late_cancel(appt):
    _to_dentist(appt, "alert_late_cancel", (_("Pedido de cancelamento em cima da hora: %(n)s"), {"n": appt.person_name}),
                "late_cancel_dentist", reply_to=appt.person_email)


def reminder(appt):
    d = appt.dentist
    if not d.patient_alert_reminder:
        return False
    if appt.patient_id:
        p = appt.patient
        if p.opt_out_reminders or not p.user.has_usable_password():
            return False
    return _to_person(appt, (_("Lembrete da sua consulta: %(w)s"), {"w": "__when__"}), "booking_reminder")
