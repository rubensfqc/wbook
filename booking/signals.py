from django.db.models.signals import post_save
from django.dispatch import receiver
from django.core.mail import send_mail
from django.conf import settings
from .models import Appointment


@receiver(post_save, sender=Appointment)
def send_appointment_notification(sender, instance, created, **kwargs):
    """Send email when appointment is created or status changes."""
    email = (instance.patient_user.email if instance.patient_user
             else instance.patient_email)
    if not email:
        return

    if created:
        if instance.status == Appointment.Status.CONFIRMED:
            subject = 'Appointment Confirmed'
            body = (
                f'Hello {instance.display_name},\n\n'
                f'Your appointment with {instance.doctor} is confirmed for '
                f'{instance.start_time:%A, %B %d at %H:%M}.\n\n'
                f'Thank you!'
            )
        else:
            subject = 'Appointment Request Received'
            body = (
                f'Hello {instance.display_name},\n\n'
                f'We received your appointment request with {instance.doctor} for '
                f'{instance.start_time:%A, %B %d at %H:%M}.\n'
                f'You will be notified once it is confirmed.\n\nThank you!'
            )
        try:
            send_mail(subject, body, settings.DEFAULT_FROM_EMAIL, [email], fail_silently=True)
        except Exception:
            pass

    elif not created:
        if instance.status == Appointment.Status.CONFIRMED:
            subject = 'Appointment Confirmed'
            body = (
                f'Hello {instance.display_name},\n\n'
                f'Your appointment with {instance.doctor} on '
                f'{instance.start_time:%A, %B %d at %H:%M} has been confirmed!\n\nSee you soon.'
            )
            try:
                send_mail(subject, body, settings.DEFAULT_FROM_EMAIL, [email], fail_silently=True)
            except Exception:
                pass
        elif instance.status == Appointment.Status.REJECTED:
            subject = 'Appointment Not Available'
            body = (
                f'Hello {instance.display_name},\n\n'
                f'Unfortunately your appointment request for '
                f'{instance.start_time:%A, %B %d at %H:%M} could not be confirmed.\n'
                f'Please book another slot.\n\nThank you.'
            )
            try:
                send_mail(subject, body, settings.DEFAULT_FROM_EMAIL, [email], fail_silently=True)
            except Exception:
                pass
