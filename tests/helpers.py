from datetime import datetime, time, timedelta

from django.utils import timezone

from apps.clinic.services import create_dentist, invite_patient


def make_dentist(slug="clinica-teste", email=None, **kw):
    d = create_dentist(email=email or f"{slug}@example.com", name="Ana Lima", clinic_name="Clínica Teste", slug=slug,
                       password="Senha!2026x", display_name="Dra. Ana Lima", whatsapp="11999990000", **kw)
    d.landing.is_published = True
    d.landing.save()
    return d


def make_patient(dentist, email="maria@example.com", consent=True, password="Senha!2026x"):
    p = invite_patient(dentist, name="Maria Silva", email=email, send=False)
    p.user.set_password(password)
    p.user.save()
    if consent:
        p.consent_at = timezone.now()
        p.save()
    return p


def next_weekday(weekday, weeks_ahead=1):
    """A date `weeks_ahead` weeks from now on the given weekday (0 = Monday)."""
    today = timezone.localdate()
    d = today + timedelta(days=(weekday - today.weekday()) % 7 + 7 * weeks_ahead)
    return d


def at(dentist, day, hh, mm=0):
    return datetime.combine(day, time(hh, mm), tzinfo=dentist.tzinfo)
