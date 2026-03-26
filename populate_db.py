# -*- coding: utf-8 -*-
"""
Seed the wbook365 database with demo data.

Run directly from your project root (next to manage.py):
    python populate_db.py

Requires the virtual environment to be active and migrations already applied:
    python manage.py makemigrations accounts booking
    python manage.py migrate
"""

import os
import sys
import django
from datetime import date, time, timedelta, datetime

# -- Bootstrap Django ----------------------------------------------------------
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "wbook365.settings")
try:
    django.setup()
except Exception as e:
    print("ERROR: Could not initialise Django.")
    print(str(e))
    sys.exit(1)

from django.utils import timezone
from accounts.models import Seller
from booking.models import (
    PlatformSettings, DoctorProfile, PatientProfile,
    OperatorProfile, Appointment, BlockedPeriod,
)

# -- Helpers -------------------------------------------------------------------

def make_aware_dt(d, hour, minute=0):
    return timezone.make_aware(datetime(d.year, d.month, d.day, hour, minute))


def create_user(email, username, name, role, password):
    user, created = Seller.objects.get_or_create(
        email=email,
        defaults=dict(username=username, name=name, role=role),
    )
    user.set_password(password)
    user.save()
    tag = "created" if created else "exists "
    print("  [{}]  {:10s}  {}".format(tag, role, email))
    return user, created


def make_apt(doctor, patient_user, d, hour, status, notes="", doctor_notes=""):
    start = make_aware_dt(d, hour)
    end   = start + timedelta(minutes=doctor.slot_duration_minutes)
    obj, created = Appointment.objects.get_or_create(
        doctor=doctor,
        patient_user=patient_user,
        start_time=start,
        defaults=dict(
            end_time=end,
            status=status,
            notes=notes,
            doctor_notes=doctor_notes,
        ),
    )
    tag = "new   " if created else "exists"
    print("  [{}]  {:<22s}  {}  {:02d}:00  [{}]  Dr. {}".format(
        tag, patient_user.name, d, hour, status, doctor.user.name))
    return obj


# -- 0. Platform Settings ------------------------------------------------------

print("\n-- Platform Settings -------------------------------------------")
platform = PlatformSettings.get_solo()
platform.platform_name     = "wbook365"
platform.default_trial_days = 30
platform.support_email     = "support@wbook365.com"
platform.save()
print("  platform_name=wbook365  trial_days=30")


# -- 1. Operator ---------------------------------------------------------------

print("\n-- Operator ----------------------------------------------------")
op_user, _ = create_user(
    email="operator@wbook365.com",
    username="operator",
    name="Platform Operator",
    role=Seller.Roles.OPERATOR,
    password="admin123",
)
op_user.is_staff = True
op_user.save()
OperatorProfile.objects.get_or_create(
    user=op_user,
    defaults=dict(department="Operations", access_level=10),
)


# -- 2. Three Doctors ----------------------------------------------------------

print("\n-- Doctors (3) -------------------------------------------------")

DOCTORS_DATA = [
    dict(
        email         = "dr.sarah@wbook365.com",
        username      = "drsarah",
        name          = "Sarah Johnson",
        password      = "doctor123",
        specialty     = "General Practitioner",
        clinic_name   = "Downtown Medical Clinic",
        clinic_address= "14 Market Street, Suite 3",
        bio           = ("Dr. Johnson has over 12 years of experience "
                         "in family medicine and preventive care."),
        slot_duration = 30,
        slots_per_day = 8,
        work_start    = time(8, 0),
        work_end      = time(17, 0),
        working_days  = [0, 1, 2, 3, 4],   # Mon-Fri
        cancel_hours  = 24,
        reminder_h    = 24,
    ),
    dict(
        email         = "dr.marcos@wbook365.com",
        username      = "drmarcos",
        name          = "Marcos Oliveira",
        password      = "doctor123",
        specialty     = "Cardiologist",
        clinic_name   = "Heart & Vascular Center",
        clinic_address= "88 Riverside Ave, Floor 2",
        bio           = ("Board-certified cardiologist specialising in "
                         "preventive cardiology and heart failure management."),
        slot_duration = 45,
        slots_per_day = 6,
        work_start    = time(9, 0),
        work_end      = time(18, 0),
        working_days  = [0, 1, 3, 4],       # Mon, Tue, Thu, Fri
        cancel_hours  = 48,
        reminder_h    = 48,
    ),
    dict(
        email         = "dr.aisha@wbook365.com",
        username      = "draisha",
        name          = "Aisha Patel",
        password      = "doctor123",
        specialty     = "Dermatologist",
        clinic_name   = "Skin Health Studio",
        clinic_address= "5 Garden Lane",
        bio           = ("Dr. Patel focuses on medical dermatology, "
                         "acne treatment, and skin cancer screening."),
        slot_duration = 20,
        slots_per_day = 12,
        work_start    = time(8, 30),
        work_end      = time(16, 30),
        working_days  = [1, 2, 3, 4, 5],   # Tue-Sat
        cancel_hours  = 24,
        reminder_h    = 12,
    ),
]

doctors = []

for d in DOCTORS_DATA:
    user, _ = create_user(
        email=d["email"], username=d["username"],
        name=d["name"], role=Seller.Roles.DOCTOR, password=d["password"],
    )
    profile, _ = DoctorProfile.objects.get_or_create(user=user)
    profile.specialty              = d["specialty"]
    profile.clinic_name            = d["clinic_name"]
    profile.clinic_address         = d["clinic_address"]
    profile.bio                    = d["bio"]
    profile.slot_duration_minutes  = d["slot_duration"]
    profile.slots_visible_per_day  = d["slots_per_day"]
    profile.work_start_time        = d["work_start"]
    profile.work_end_time          = d["work_end"]
    profile.working_days           = d["working_days"]
    profile.cancel_hours_before    = d["cancel_hours"]
    profile.reminder_hours_before  = d["reminder_h"]
    profile.save()
    doctors.append(profile)
    print("         booking page -> /book/{}/  ({})".format(
        user.slug, d["specialty"]))


# -- 3. Five Patients ----------------------------------------------------------

print("\n-- Patients (5) ------------------------------------------------")

PATIENTS_DATA = [
    dict(
        email     ="alice@example.com", username="alice_p",
        name      ="Alice Ferreira",   password="patient123",
        doctor_idx=0,
        dob       =date(1990, 4, 15),
        notes     ="Hypertension follow-up every 3 months.",
    ),
    dict(
        email     ="bob@example.com",   username="bob_p",
        name      ="Bob Chen",          password="patient123",
        doctor_idx=0,
        dob       =date(1985, 11, 3),
        notes     ="Diabetic patient, HbA1c monitoring.",
    ),
    dict(
        email     ="carol@example.com", username="carol_p",
        name      ="Carol Santos",      password="patient123",
        doctor_idx=1,
        dob       =date(1972, 7, 22),
        notes     ="Post-stent patient, monthly cardiology review.",
    ),
    dict(
        email     ="david@example.com", username="david_p",
        name      ="David Muller",      password="patient123",
        doctor_idx=1,
        dob       =date(1968, 2, 9),
        notes     ="Atrial fibrillation management.",
    ),
    dict(
        email     ="emily@example.com", username="emily_p",
        name      ="Emily Nakamura",    password="patient123",
        doctor_idx=2,
        dob       =date(2000, 8, 30),
        notes     ="Acne treatment programme, 6-month course.",
    ),
]

patients = []

for p in PATIENTS_DATA:
    user, _ = create_user(
        email=p["email"], username=p["username"],
        name=p["name"], role=Seller.Roles.PATIENT, password=p["password"],
    )
    doctor  = doctors[p["doctor_idx"]]
    profile, _ = PatientProfile.objects.get_or_create(
        user=user, doctor=doctor,
        defaults=dict(date_of_birth=p["dob"], notes=p["notes"]),
    )
    patients.append(profile)
    print("         {} -> Dr. {}".format(p["name"], doctor.user.name))


# -- 4. Appointments -----------------------------------------------------------

print("\n-- Appointments ------------------------------------------------")

today   = date.today()
in_1d   = today + timedelta(days=1)
in_3d   = today + timedelta(days=3)
in_7d   = today + timedelta(days=7)
in_14d  = today + timedelta(days=14)
past_3d = today - timedelta(days=3)
past_7d = today - timedelta(days=7)
past_14d= today - timedelta(days=14)

S = Appointment.Status
dr_sarah  = doctors[0]
dr_marcos = doctors[1]
dr_aisha  = doctors[2]
alice = patients[0].user
bob   = patients[1].user
carol = patients[2].user
david = patients[3].user
emily = patients[4].user

# Dr. Sarah -- Alice (hypertension)
make_apt(dr_sarah, alice, past_14d,  9, S.COMPLETED,
         notes="Routine check-up",
         doctor_notes="BP 130/85. Continue Lisinopril.")
make_apt(dr_sarah, alice, past_7d,   9, S.COMPLETED,
         notes="Follow-up hypertension",
         doctor_notes="BP improved to 125/80. Maintain lifestyle changes.")
make_apt(dr_sarah, alice, in_7d,     9, S.CONFIRMED,
         notes="Monthly BP check")
make_apt(dr_sarah, alice, in_14d,   11, S.CONFIRMED,
         notes="Annual blood test review")

# Dr. Sarah -- Bob (diabetes)
make_apt(dr_sarah, bob, past_14d,   10, S.COMPLETED,
         notes="Diabetes review",
         doctor_notes="HbA1c 7.2. Adjust Metformin dosage.")
make_apt(dr_sarah, bob, past_3d,    10, S.COMPLETED,
         notes="HbA1c recheck",
         doctor_notes="HbA1c 6.9. Good progress. Continue current meds.")
make_apt(dr_sarah, bob, in_1d,      10, S.PENDING,
         notes="Quarterly diabetes follow-up")

# Dr. Marcos -- Carol (cardiology)
make_apt(dr_marcos, carol, past_7d,  9, S.COMPLETED,
         notes="Post-stent 3-month review",
         doctor_notes="Ejection fraction stable at 58%. Continue dual antiplatelet.")
make_apt(dr_marcos, carol, in_3d,    9, S.CONFIRMED,
         notes="Monthly cardio check")
make_apt(dr_marcos, carol, in_14d,   9, S.CONFIRMED,
         notes="Echo follow-up")

# Dr. Marcos -- David (AF)
make_apt(dr_marcos, david, past_14d, 10, S.COMPLETED,
         notes="AF management",
         doctor_notes="Heart rate controlled. Warfarin INR 2.4 -- within target.")
make_apt(dr_marcos, david, in_7d,    10, S.PENDING,
         notes="INR check and medication review")

# Dr. Aisha -- Emily (dermatology)
make_apt(dr_aisha, emily, past_14d,  9, S.COMPLETED,
         notes="Initial acne consultation",
         doctor_notes="Moderate inflammatory acne. Starting Doxycycline 100mg + topical retinoid.")
make_apt(dr_aisha, emily, past_3d,   9, S.COMPLETED,
         notes="4-week follow-up",
         doctor_notes="Improvement noted. Continue regimen. Added benzoyl peroxide wash.")
make_apt(dr_aisha, emily, in_3d,     9, S.CONFIRMED,
         notes="8-week treatment review")
make_apt(dr_aisha, emily, in_14d,   11, S.CONFIRMED,
         notes="3-month progress assessment")

# Walk-in (unregistered) requests -- Dr. Sarah
print("\n-- Walk-in requests (no login required) ------------------------")
WALK_INS = [
    dict(name="James Thornton", email="james.t@email.com",
         phone="+44 7700 900111", d=in_1d,  hour=14,
         notes="Persistent cough for 2 weeks"),
    dict(name="Maria Costa",    email="maria.c@email.com",
         phone="+351 912 345678", d=in_3d, hour=15,
         notes="Skin rash on forearm"),
]
for w in WALK_INS:
    start = make_aware_dt(w["d"], w["hour"])
    end   = start + timedelta(minutes=dr_sarah.slot_duration_minutes)
    obj, created = Appointment.objects.get_or_create(
        doctor=dr_sarah,
        patient_email=w["email"],
        start_time=start,
        defaults=dict(
            end_time=end,
            patient_name=w["name"],
            patient_phone=w["phone"],
            notes=w["notes"],
            status=S.PENDING,
        ),
    )
    tag = "new   " if created else "exists"
    print("  [{}]  {:<22s}  {}  {:02d}:00  [PENDING walk-in]".format(
        tag, w["name"], w["d"], w["hour"]))

# One REJECTED and one CANCELLED for UI variety
print("\n-- Variety: rejected & cancelled -------------------------------")
start_r = make_aware_dt(past_7d, 16)
end_r   = start_r + timedelta(minutes=dr_aisha.slot_duration_minutes)
obj, created = Appointment.objects.get_or_create(
    doctor=dr_aisha,
    patient_email="unknown@email.com",
    start_time=start_r,
    defaults=dict(
        end_time=end_r,
        patient_name="Unknown Walk-in",
        notes="Slot double-booked",
        status=S.REJECTED,
    ),
)
print("  [{}]  {:<22s}  {}  16:00  [REJECTED]".format(
    "new   " if created else "exists", "Unknown Walk-in", past_7d))

start_c = make_aware_dt(past_3d, 11)
end_c   = start_c + timedelta(minutes=dr_marcos.slot_duration_minutes)
obj, created = Appointment.objects.get_or_create(
    doctor=dr_marcos,
    patient_user=carol,
    start_time=start_c,
    defaults=dict(
        end_time=end_c,
        notes="Patient cancelled -- travel conflict",
        status=S.CANCELLED,
    ),
)
print("  [{}]  {:<22s}  {}  11:00  [CANCELLED]".format(
    "new   " if created else "exists", carol.name, past_3d))


# -- Summary -------------------------------------------------------------------

print("\n================================================================")
print("  Database seeded successfully!")
print("================================================================\n")
print("  PORTALS")
print("  Operator  ->  http://localhost:8000/operator/")
print("  Doctor    ->  http://localhost:8000/doctor/")
print("  Patient   ->  http://localhost:8000/patient/\n")
print("  CREDENTIALS")
print("  {:<35s} {:15s} {}".format("Email", "Password", "Role"))
print("  " + "-" * 60)
credentials = [
    ("operator@wbook365.com",  "admin123",   "Operator"),
    ("dr.sarah@wbook365.com",  "doctor123",  "Doctor"),
    ("dr.marcos@wbook365.com", "doctor123",  "Doctor"),
    ("dr.aisha@wbook365.com",  "doctor123",  "Doctor"),
    ("alice@example.com",      "patient123", "Patient"),
    ("bob@example.com",        "patient123", "Patient"),
    ("carol@example.com",      "patient123", "Patient"),
    ("david@example.com",      "patient123", "Patient"),
    ("emily@example.com",      "patient123", "Patient"),
]
for email, pwd, role in credentials:
    print("  {:<35s} {:15s} {}".format(email, pwd, role))

print("\n  PUBLIC BOOKING PAGES (no login required)")
for doc in doctors:
    print("  http://localhost:8000/book/{}/   Dr. {}".format(
        doc.user.slug, doc.user.name))
print()
