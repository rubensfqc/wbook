from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import Seller


@receiver(post_save, sender=Seller)
def create_role_profile(sender, instance, created, **kwargs):
    """Auto-create the matching profile when a new user is saved."""
    if not created:
        return

    from booking.models import DoctorProfile, PatientProfile, OperatorProfile, PlatformSettings

    if instance.role == Seller.Roles.DOCTOR:
        if not hasattr(instance, 'doctor_profile'):
            platform = PlatformSettings.get_solo()
            DoctorProfile.objects.create(
                user=instance,
                trial_days=platform.default_trial_days,
            )

    elif instance.role == Seller.Roles.OPERATOR:
        if not hasattr(instance, 'operator_profile'):
            OperatorProfile.objects.create(user=instance)
