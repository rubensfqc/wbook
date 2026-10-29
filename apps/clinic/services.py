from datetime import time

from django.db import transaction
from django.utils import timezone
from django.utils.translation import gettext as _

from apps.accounts.models import User
from apps.core.emails import send_templated

from .models import Dentist, PatientProfile, TreatmentEntry

DEFAULT_TYPES = [
    # name, duration, colour, visitor_bookable
    ("Avaliação", 30, "#0f766e", True),
    ("Limpeza", 45, "#1d4ed8", True),
    ("Urgência", 30, "#c2410c", True),
    ("Retorno", 30, "#7e3a6e", False),
]


@transaction.atomic
def create_dentist(*, email, name, clinic_name, slug, password=None, display_name="", cro_number="", cro_state="",
                   whatsapp="", phone="", city="", state="", active=True, language="pt-br", trial_days=None):
    from apps.agenda.models import AppointmentType, BookingSettings, WorkingHours
    from apps.core.models import PlatformSettings
    from apps.landing.models import LandingPage

    user = User.objects.create_user(email=email, password=password, name=name, phone=phone, role=User.Role.DENTIST,
                                    is_active=active, language=language if language in ("pt-br", "en") else "pt-br")
    dentist = Dentist.objects.create(
        user=user, clinic_name=clinic_name, slug=slug, display_name=display_name or name, cro_number=cro_number,
        cro_state=cro_state, whatsapp=whatsapp, phone=phone, city=city, state=state,
        trial_days=trial_days if trial_days is not None else PlatformSettings.get_solo().default_trial_days,
    )
    BookingSettings.objects.create(dentist=dentist)
    LandingPage.objects.create(
        dentist=dentist,
        headline=clinic_name,
        subheadline=_("Agende sua consulta online"),
    )
    for i, (n, dur, colour, vis) in enumerate(DEFAULT_TYPES):
        AppointmentType.objects.create(dentist=dentist, name=n, duration_min=dur, colour=colour, visitor_bookable=vis, order=i)
    for wd in range(5):
        WorkingHours.objects.create(dentist=dentist, weekday=wd, start=time(8, 0), end=time(12, 0))
        WorkingHours.objects.create(dentist=dentist, weekday=wd, start=time(13, 30), end=time(18, 0))
    return dentist


@transaction.atomic
def invite_patient(dentist, *, name, email, phone="", whatsapp="", birth_date=None, cpf="", lead=None, send=True, language=None):
    """Creates a patient login (no password yet) and e-mails a set-password link."""
    email = email.lower().strip()
    user = User.objects.filter(email=email).first()
    if user is not None:
        if user.is_patient and getattr(user, "patient_profile", None) and user.patient_profile.dentist_id == dentist.pk:
            patient = user.patient_profile
        else:
            raise ValueError(_("Este e-mail já tem uma conta no wbook."))
    else:
        user = User.objects.create_user(email=email, name=name, phone=phone, role=User.Role.PATIENT,
                                        language=language or (lead.language if lead else dentist.user.language))
        patient = PatientProfile.objects.create(user=user, dentist=dentist, whatsapp=whatsapp or phone,
                                                birth_date=birth_date, cpf=cpf)
    if lead is not None:
        lead.converted_patient = patient
        lead.status = "WON"
        lead.save(update_fields=["converted_patient", "status", "updated_at"])
        # appointments requested as a visitor now belong to the patient
        lead.appointments.update(patient=patient, lead=None)
        lead.quotes.update(patient=patient)
    if send:
        send_invite(patient)
    return patient


def send_invite(patient):
    from apps.accounts.tokens import set_password_link

    patient.invited_at = timezone.now()
    patient.save(update_fields=["invited_at"])
    dentist = patient.dentist
    send_templated(patient.email, _("%(d)s convidou você para o portal do paciente") % {"d": dentist.name}, "patient_invite",
                   {"patient": patient, "dentist": dentist, "link": set_password_link(patient.user)},
                   reply_to=dentist.user.email, language=patient.user.language)


def add_event(treatment, text, user=None):
    return TreatmentEntry.objects.create(treatment=treatment, author=user, author_role=getattr(user, "role", "SYSTEM"),
                                         kind=TreatmentEntry.Kind.EVT, text=text)


def anonymise_patient(patient, delete_records=False):
    user = patient.user
    if delete_records:
        patient.treatments.all().delete()
        patient.appointments.all().delete()
    user.name = "Paciente removido"
    user.email = f"removed-{patient.ref}@invalid"
    user.phone = ""
    user.is_active = False
    user.set_unusable_password()
    user.save()
    patient.cpf = ""
    patient.whatsapp = ""
    patient.birth_date = None
    patient.notes = ""
    patient.save()
