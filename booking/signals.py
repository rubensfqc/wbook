from django.db.models.signals import post_save
from django.dispatch import receiver
from django.core.mail import send_mail
from django.conf import settings
from .models import Appointment
from django.utils.translation import gettext as _

@receiver(post_save, sender=Appointment)
def send_appointment_notification(sender, instance, created, **kwargs):
    """Send email when appointment is created or status changes."""
    email = (instance.patient_user.email if instance.patient_user
             else instance.patient_email)
    if not email:
        return

    # ↓ Add it here — runs once, shared by all 4 email cases below
    from django.utils import translation
    with translation.override('pt-br'):
        formatted_dt = instance.start_time.strftime('%A, %d de %B às %H:%M')

    if created:
        if instance.status == Appointment.Status.CONFIRMED:
            subject = _('Appointment Confirmed')
            body = _('Hello %(name)s,\n\n'
                    'Your appointment with %(doctor)s is confirmed for %(datetime)s.\n\n'
                    'Thank you!') % {
                'name':     instance.display_name,
                'doctor':   instance.doctor,
                'datetime': instance.start_time.strftime('%A, %B %d at %H:%M'),
            }
        else:
            subject = _('Appointment Request Received')
            body = _('Hello %(name)s,\n\n'
                    'We received your appointment request with %(doctor)s for %(datetime)s.\n'
                    'You will be notified once it is confirmed.\n\nThank you!') % {
                'name':     instance.display_name,
                'doctor':   instance.doctor,
                'datetime': instance.start_time.strftime('%A, %B %d at %H:%M'),
            }
        try:
            send_mail(subject, body, settings.DEFAULT_FROM_EMAIL, [email], fail_silently=True)
        except Exception:
            pass

    elif not created:
        if instance.status == Appointment.Status.CONFIRMED:
            subject = _('Appointment Confirmed')
            body = _('Hello %(name)s,\n\n'
                    'Your appointment with %(doctor)s on %(datetime)s has been confirmed!\n\n'
                    'See you soon.') % {
                'name':     instance.display_name,
                'doctor':   instance.doctor,
                'datetime': formatted_dt,
            }
            try:
                send_mail(subject, body, settings.DEFAULT_FROM_EMAIL, [email], fail_silently=True)
            except Exception:
                pass

        elif instance.status == Appointment.Status.REJECTED:
            subject = _('Appointment Not Available')
            body = _('Hello %(name)s,\n\n'
                    'Unfortunately your appointment request for %(datetime)s could not be confirmed.\n'
                    'Please book another slot.\n\nThank you.') % {
                'name':     instance.display_name,
                'datetime': formatted_dt,
            }
            try:
                send_mail(subject, body, settings.DEFAULT_FROM_EMAIL, [email], fail_silently=True)
            except Exception:
                pass
