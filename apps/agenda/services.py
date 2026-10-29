"""Every agenda state change. Atomic, dentist row locked, time re-checked, logged, e-mails on commit."""

from datetime import timedelta

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone
from django.utils.translation import gettext as _

from apps.clinic.models import Dentist
from apps.core.activity import log_action
from apps.core.whatsapp import wa_link

from . import notify, slots
from .models import Appointment

Status = Appointment.Status


def _lock(dentist):
    return Dentist.objects.select_for_update().get(pk=dentist.pk)


def _end(appt_type, start):
    return start + timedelta(minutes=appt_type.duration_min)


def _check_visible(dentist, appt_type, start, exclude=None):
    if not slots.is_visible(dentist, appt_type, start, exclude=exclude):
        raise ValidationError(_("Este horário não está mais disponível. Escolha outro."))


def _on_commit(fn, *args, **kwargs):
    transaction.on_commit(lambda: fn(*args, **kwargs))


def _bump(appt):
    appt.ics_sequence += 1


@transaction.atomic
def book(patient, appt_type, start, note="", treatment=None, actor=None):
    """Patient books in the portal."""
    dentist = _lock(patient.dentist)
    if appt_type.dentist_id != dentist.pk or not appt_type.is_active:
        raise ValidationError(_("Tipo de consulta inválido."))
    active = Appointment.objects.filter(patient=patient, status__in=Appointment.BLOCKING_STATUSES, start__gte=timezone.now()).count()
    if active >= dentist.booking.max_active_per_patient:
        raise ValidationError(_("Você já tem %(n)s consultas marcadas. Remarque ou cancele uma antes de agendar outra.")
                              % {"n": active})
    _check_visible(dentist, appt_type, start)
    auto = dentist.booking.patient_auto_confirm
    appt = Appointment.objects.create(
        dentist=dentist, patient=patient, type=appt_type, start=start, end=_end(appt_type, start), treatment=treatment,
        status=Status.CONFIRMED if auto else Status.PENDING, source=Appointment.Source.PORTAL, patient_note=note,
        confirmed_at=timezone.now() if auto else None,
    )
    log_action(actor or patient.user, "booking", "Paciente agendou %(t)s em %(w)s (%(s)s)", t=appt_type.name,
               w=f"{timezone.localtime(start):%d/%m/%Y %H:%M}", s=appt.status)
    if auto:
        _on_commit(notify.confirmed, appt)
    else:
        _on_commit(notify.request_received, appt)
    return appt


@transaction.atomic
def request_booking(dentist, appt_type, start, *, name, email, whatsapp="", message="", consent=False, ip_hash="", language="pt-br"):
    """Visitor (no account) asks for a time → Lead + PENDING appointment holding the slot."""
    from apps.landing.models import Lead

    dentist = _lock(dentist)
    if not dentist.booking.visitor_booking_enabled:
        raise ValidationError(_("Este consultório não está aceitando pedidos online no momento."))
    if appt_type.dentist_id != dentist.pk or not appt_type.is_active or not appt_type.visitor_bookable:
        raise ValidationError(_("Tipo de consulta inválido."))
    if not consent:
        raise ValidationError(_("É preciso aceitar o uso dos seus dados para enviar o pedido."))
    email = email.lower().strip()
    lead = Lead.objects.filter(dentist=dentist, email=email).exclude(status__in=["WON", "LOST"]).first()
    if lead and Appointment.objects.filter(lead=lead, status=Status.PENDING).exists():
        raise ValidationError(_("Você já tem um pedido aguardando confirmação. Aguarde a resposta da clínica."))
    _check_visible(dentist, appt_type, start)
    if lead is None:
        lead = Lead.objects.create(dentist=dentist, name=name, email=email, whatsapp=whatsapp, message=message, consent=True,
                                   source=Lead.Source.BOOKING, ip_hash=ip_hash, language=language)
    else:
        lead.name, lead.whatsapp = name, whatsapp or lead.whatsapp
        lead.language = language
        if message:
            lead.message = message
        lead.save()
    appt = Appointment.objects.create(
        dentist=dentist, lead=lead, type=appt_type, start=start, end=_end(appt_type, start), status=Status.PENDING,
        source=Appointment.Source.PUBLIC, patient_note=message,
    )
    log_action(None, "booking", "Pedido de visitante %(n)s em %(w)s para %(d)s", n=email,
               w=f"{timezone.localtime(start):%d/%m/%Y %H:%M}", d=dentist.slug)
    _on_commit(notify.request_received, appt)
    return appt


@transaction.atomic
def create_by_dentist(dentist, appt_type, start, *, patient=None, lead=None, treatment=None, note="", actor=None):
    dentist = _lock(dentist)
    if not slots.is_free_for_dentist(dentist, appt_type, start):
        raise ValidationError(_("Este horário já está ocupado."))
    appt = Appointment.objects.create(
        dentist=dentist, patient=patient, lead=lead, type=appt_type, start=start, end=_end(appt_type, start), treatment=treatment,
        status=Status.CONFIRMED, source=Appointment.Source.DENTIST, dentist_note=note, confirmed_at=timezone.now(),
    )
    if lead is not None:
        lead.advance("SCHEDULED")
    log_action(actor, "agenda", "Dentista marcou %(t)s para %(n)s", t=appt_type.name, n=appt.person_name)
    _on_commit(notify.confirmed, appt, True)
    return appt


@transaction.atomic
def approve(appt, actor=None):
    _lock(appt.dentist)
    appt.refresh_from_db()
    if appt.status != Status.PENDING:
        raise ValidationError(_("Este pedido não está mais pendente."))
    appt.status = Status.CONFIRMED
    appt.confirmed_at = timezone.now()
    _bump(appt)
    appt.save()
    if appt.lead_id:
        appt.lead.advance("SCHEDULED")
    log_action(actor, "agenda", "Pedido aprovado: %(n)s", n=appt.person_name)
    _on_commit(notify.confirmed, appt, True)
    return appt


@transaction.atomic
def reject(appt, reason="", actor=None):
    _lock(appt.dentist)
    appt.refresh_from_db()
    if appt.status != Status.PENDING:
        raise ValidationError(_("Este pedido não está mais pendente."))
    appt.status = Status.REJECTED
    appt.reject_reason = reason
    _bump(appt)
    appt.save()
    log_action(actor, "agenda", "Pedido recusado: %(n)s", n=appt.person_name)
    _on_commit(notify.rejected, appt)
    return appt


def expire_pending(now=None):
    now = now or timezone.now()
    count = 0
    for appt in Appointment.objects.filter(status=Status.PENDING).select_related("dentist__booking", "lead", "patient__user", "type"):
        hold = timedelta(hours=appt.dentist.booking.pending_hold_hours)
        if appt.created_at + hold <= now or appt.start <= now:
            with transaction.atomic():
                appt.status = Status.EXPIRED
                _bump(appt)
                appt.save()
                _on_commit(notify.expired, appt)
            count += 1
    return count


@transaction.atomic
def reschedule(appt, new_start, by="PATIENT", actor=None):
    dentist = _lock(appt.dentist)
    appt.refresh_from_db()
    if not appt.is_blocking:
        raise ValidationError(_("Esta consulta não pode mais ser remarcada."))
    if by == "PATIENT":
        if appt.in_cutoff:
            raise ValidationError(_("Fora do prazo para remarcar online. Fale com a clínica."))
        _check_visible(dentist, appt.type, new_start, exclude=appt)
    elif not slots.is_free_for_dentist(dentist, appt.type, new_start, exclude=appt):
        raise ValidationError(_("Este horário já está ocupado."))
    was_pending = appt.status == Status.PENDING
    appt.status = Status.RESCHEDULED
    _bump(appt)
    appt.save()
    new = Appointment.objects.create(
        dentist=dentist, patient=appt.patient, lead=appt.lead, type=appt.type, treatment=appt.treatment, start=new_start,
        end=_end(appt.type, new_start), source=appt.source, patient_note=appt.patient_note, dentist_note=appt.dentist_note,
        status=Status.PENDING if (was_pending and by == "PATIENT") else Status.CONFIRMED, rescheduled_from=appt,
        confirmed_at=None if (was_pending and by == "PATIENT") else timezone.now(), ics_sequence=appt.ics_sequence + 1,
    )
    log_action(actor, "agenda", "Consulta de %(n)s remarcada (%(b)s)", n=new.person_name, b=by)
    _on_commit(notify.changed, new, appt, by)
    return new


@transaction.atomic
def cancel(appt, by="PATIENT", note="", actor=None):
    _lock(appt.dentist)
    appt.refresh_from_db()
    if not appt.is_blocking:
        raise ValidationError(_("Esta consulta não pode mais ser cancelada."))
    if by == "PATIENT" and appt.in_cutoff:
        raise ValidationError(_("Fora do prazo para cancelar online. Fale com a clínica."))
    appt.status = Status.CANCELLED
    appt.cancelled_at = timezone.now()
    appt.cancelled_by = by
    if note:
        appt.dentist_note = (appt.dentist_note + "\n" + note).strip() if by == "DENTIST" else appt.dentist_note
        if by != "DENTIST":
            appt.patient_note = (appt.patient_note + "\n" + note).strip()
    _bump(appt)
    appt.save()
    log_action(actor, "agenda", "Consulta de %(n)s cancelada (%(b)s)", n=appt.person_name, b=by)
    _on_commit(notify.changed, appt, None, by)
    return appt


def late_cancel_message(appt, note=""):
    from django.utils import formats

    s = timezone.localtime(appt.start, appt.dentist.tzinfo)
    text = _("Olá, aqui é %(name)s. Gostaria de cancelar minha consulta de %(type)s em %(weekday)s, %(date)s, às %(time)s.") % {
        "name": appt.person_name, "type": appt.type.name, "weekday": formats.date_format(s, "l"),
        "date": f"{s:%d/%m/%Y}", "time": f"{s:%H:%M}",
    }
    if note:
        text += " " + note.strip()
    return text


@transaction.atomic
def request_late_cancel(appt, note="", actor=None):
    appt.refresh_from_db()
    if not appt.is_blocking or appt.start <= timezone.now():
        raise ValidationError(_("Esta consulta não pode mais ser cancelada."))
    appt.late_cancel_requested_at = timezone.now()
    appt.late_cancel_note = note
    appt.save(update_fields=["late_cancel_requested_at", "late_cancel_note", "updated_at"])
    log_action(actor, "booking", "Pedido de cancelamento em cima da hora: %(n)s", level=30, n=appt.person_name)
    _on_commit(notify.late_cancel, appt)
    return wa_link(appt.dentist.whatsapp, late_cancel_message(appt, note))


@transaction.atomic
def keep(appt, actor=None):
    appt.late_cancel_requested_at = None
    appt.save(update_fields=["late_cancel_requested_at", "updated_at"])
    log_action(actor, "agenda", "Consulta mantida após pedido de cancelamento: %(n)s", n=appt.person_name)
    return appt


@transaction.atomic
def complete(appt, no_show=False, actor=None):
    from apps.clinic.services import add_event

    if appt.status != Status.CONFIRMED:
        raise ValidationError(_("Só consultas confirmadas podem ser concluídas."))
    appt.status = Status.NO_SHOW if no_show else Status.COMPLETED
    _bump(appt)
    appt.save()
    if appt.treatment_id and not no_show:
        add_event(appt.treatment, _("Sessão realizada: %(t)s em %(d)s") % {
            "t": appt.type.name, "d": f"{timezone.localtime(appt.start):%d/%m/%Y}"}, getattr(actor, "user", actor))
    log_action(actor, "agenda", "Consulta de %(n)s: %(s)s", n=appt.person_name, s=appt.status)
    return appt
