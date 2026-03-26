"""
Run with:  python manage.py shell < booking/populate_db.py
"""
import os, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'wbook365.settings')
django.setup()

from datetime import date, timedelta
from accounts.models import Seller
from booking.models import PlatformSettings, DoctorProfile, PatientProfile, OperatorProfile, Appointment

# Platform
platform = PlatformSettings.get_solo()
platform.platform_name = 'wbook365'
platform.default_trial_days = 30
platform.save()
print('Platform settings ready.')

# Operator
op_user, _ = Seller.objects.get_or_create(
    email='operator@wbook365.com',
    defaults=dict(username='operator', name='Platform Operator', role=Seller.Roles.OPERATOR, is_staff=True),
)
op_user.set_password('admin123')
op_user.save()
OperatorProfile.objects.get_or_create(user=op_user, defaults=dict(department='Operations', access_level=10))
print(f'Operator: {op_user.email} / admin123')

# Doctor
doc_user, _ = Seller.objects.get_or_create(
    email='doctor@wbook365.com',
    defaults=dict(username='drsarah', name='Sarah Johnson', role=Seller.Roles.DOCTOR),
)
doc_user.set_password('doctor123')
doc_user.save()
doc_profile, _ = DoctorProfile.objects.get_or_create(user=doc_user)
doc_profile.specialty = 'General Practitioner'
doc_profile.clinic_name = 'Downtown Medical Clinic'
doc_profile.slot_duration_minutes = 30
doc_profile.slots_visible_per_day = 8
doc_profile.working_days = [0, 1, 2, 3, 4]
doc_profile.save()
print(f'Doctor: {doc_user.email} / doctor123 | booking URL: /book/{doc_user.slug}/')

# Patient (registered)
pat_user, _ = Seller.objects.get_or_create(
    email='patient@wbook365.com',
    defaults=dict(username='johnpatient', name='John Patient', role=Seller.Roles.PATIENT),
)
pat_user.set_password('patient123')
pat_user.save()
PatientProfile.objects.get_or_create(user=pat_user, defaults=dict(doctor=doc_profile))
print(f'Patient:  {pat_user.email} / patient123')

print('\nAll done! Superuser: python manage.py createsuperuser')
