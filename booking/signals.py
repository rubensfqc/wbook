from django.db.models.signals import post_save
from django.dispatch import receiver
from django.core.mail import send_mail
from django.conf import settings
from django.utils.translation import gettext as _
from django.utils import translation
from .models import Appointment


def _send(subject, body, recipient):
    """Small helper so every email call shares the same fail-silently behavior."""
    if not recipient:
        return
    try:
        send_mail(subject, body, settings.DEFAULT_FROM_EMAIL, [recipient], fail_silently=True)
    except Exception:
        pass


@receiver(post_save, sender=Appointment)
def send_appointment_notification(sender, instance, created, **kwargs):
    """Send email to the patient and/or the doctor when an appointment is created
    or its status changes."""
    patient_email = (instance.patient_user.email if instance.patient_user
                      else instance.patient_email)
    doctor_email  = instance.doctor.user.email if instance.doctor_id else None
    patient_name  = instance.display_name
    doctor_label  = str(instance.doctor)

    with translation.override('pt-br'):
        formatted_dt = instance.start_time.strftime('%A, %d de %B às %H:%M')

    if created:
        if instance.status == Appointment.Status.CONFIRMED:
            # Patient booked directly through their portal and it was auto-confirmed.
            subject = _('Appointment Confirmed')
            body = _('Hello %(name)s,\n\n'
                     'Your appointment with %(doctor)s is confirmed for %(datetime)s.\n\n'
                     'Thank you!') % {
                'name':     patient_name,
                'doctor':   doctor_label,
                'datetime': formatted_dt,
            }
            _send(subject, body, patient_email)

            subject = _('New Appointment Confirmed')
            body = _('Hello %(doctor)s,\n\n'
                     'A new appointment has just been booked and confirmed.\n\n'
                     'Patient: %(name)s\n'
                     'Date/time: %(datetime)s\n\n'
                     'You can view it in your dashboard.') % {
                'doctor':   doctor_label,
                'name':     patient_name,
                'datetime': formatted_dt,
            }
            _send(subject, body, doctor_email)

        else:
            # New request awaiting the doctor's approval.
            subject = _('Appointment Request Received')
            body = _('Hello %(name)s,\n\n'
                     'We received your appointment request with %(doctor)s for %(datetime)s.\n'
                     'You will be notified once it is confirmed.\n\nThank you!') % {
                'name':     patient_name,
                'doctor':   doctor_label,
                'datetime': formatted_dt,
            }
            _send(subject, body, patient_email)

            subject = _('New Appointment Request')
            body = _('Hello %(doctor)s,\n\n'
                     'You have a new appointment request awaiting your confirmation.\n\n'
                     'Patient: %(name)s\n'
                     'Date/time: %(datetime)s\n\n'
                     'Please review it in your dashboard.') % {
                'doctor':   doctor_label,
                'name':     patient_name,
                'datetime': formatted_dt,
            }
            _send(subject, body, doctor_email)

    else:
        if instance.status == Appointment.Status.CONFIRMED:
            # The doctor is the one confirming it, so only the patient is notified.
            subject = _('Appointment Confirmed')
            body = _('Hello %(name)s,\n\n'
                     'Your appointment with %(doctor)s on %(datetime)s has been confirmed!\n\n'
                     'See you soon.') % {
                'name':     patient_name,
                'doctor':   doctor_label,
                'datetime': formatted_dt,
            }
            _send(subject, body, patient_email)

        elif instance.status == Appointment.Status.REJECTED:
            # The doctor is the one rejecting it, so only the patient is notified.
            subject = _('Appointment Not Available')
            body = _('Hello %(name)s,\n\n'
                     'Unfortunately your appointment request for %(datetime)s could not be confirmed.\n'
                     'Please book another slot.\n\nThank you.') % {
                'name':     patient_name,
                'datetime': formatted_dt,
            }
            _send(subject, body, patient_email)

        elif instance.status == Appointment.Status.CANCELLED:
            # Cancellation is patient-initiated, so both sides are notified.
            subject = _('Appointment Cancelled')
            body = _('Hello %(name)s,\n\n'
                     'Your appointment with %(doctor)s on %(datetime)s has been cancelled.\n\n'
                     'You can book a new slot anytime.') % {
                'name':     patient_name,
                'doctor':   doctor_label,
                'datetime': formatted_dt,
            }
            _send(subject, body, patient_email)

            subject = _('Appointment Cancelled')
            body = _('Hello %(doctor)s,\n\n'
                     'An appointment has been cancelled.\n\n'
                     'Patient: %(name)s\n'
                     'Date/time: %(datetime)s\n\n'
                     'This slot is now free on your calendar.') % {
                'doctor':   doctor_label,
                'name':     patient_name,
                'datetime': formatted_dt,
            }
            _send(subject, body, doctor_email)