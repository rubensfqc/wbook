from django.urls import path
from booking.views import (
    # public
    dashboard_redirect, public_booking, booking_confirmation, capture_lead,
    # doctor
    doctor_dashboard, doctor_appointments, appointment_action, appointment_note,
    doctor_schedule_settings, blocked_periods, blocked_period_delete,
    doctor_patients, patient_invite, patient_detail, patient_remove,
    doctor_profile_settings, trial_expired,
    doctor_leads, lead_update_status,
    # patient
    patient_dashboard, patient_book, patient_appointments,
    patient_cancel, patient_reschedule,
    # operator
    operator_dashboard, operator_doctors, operator_doctor_add,
    operator_doctor_edit, operator_doctor_delete,
    operator_patients, operator_appointments, operator_platform_settings,
)

urlpatterns = [
    # ── root redirect ────────────────────────────────────────────────────────
    path('dashboard/',    dashboard_redirect, name='dashboard_redirect'),
    path('dashboard/',    dashboard_redirect, name='dashboard'),

    # ── public booking ───────────────────────────────────────────────────────
    path('book/<slug:slug>/',         public_booking,      name='public_booking'),
    path('book/<slug:slug>/done/',    booking_confirmation, name='booking_confirmation'),
    path('book/<slug:slug>/lead/',    capture_lead,         name='capture_lead'),
    path('trial-expired/',            trial_expired,        name='trial_expired'),

    # ── doctor portal ────────────────────────────────────────────────────────
    path('doctor/',                           doctor_dashboard,         name='doctor_dashboard'),
    path('doctor/appointments/',              doctor_appointments,      name='doctor_appointments'),
    path('doctor/appointments/<int:pk>/<str:action>/', appointment_action, name='appointment_action'),
    path('doctor/appointments/<int:pk>/note/', appointment_note,        name='appointment_note'),
    path('doctor/schedule/',                  doctor_schedule_settings, name='doctor_schedule_settings'),
    path('doctor/blocked/',                   blocked_periods,          name='blocked_periods'),
    path('doctor/blocked/<int:pk>/delete/',   blocked_period_delete,    name='blocked_period_delete'),
    path('doctor/patients/',                  doctor_patients,          name='doctor_patients'),
    path('doctor/patients/invite/',           patient_invite,           name='patient_invite'),
    path('doctor/patients/<int:pk>/',         patient_detail,           name='patient_detail'),
    path('doctor/patients/<int:pk>/remove/',  patient_remove,           name='patient_remove'),
    path('doctor/profile/',                   doctor_profile_settings,  name='doctor_profile_settings'),

    # ── leads ────────────────────────────────────────────────────────────────
    path('doctor/leads/',                     doctor_leads,             name='doctor_leads'),
    path('doctor/leads/<int:pk>/status/',     lead_update_status,       name='lead_update_status'),

    # ── patient portal ───────────────────────────────────────────────────────
    path('patient/',                        patient_dashboard,    name='patient_dashboard'),
    path('patient/book/',                   patient_book,         name='patient_book'),
    path('patient/appointments/',           patient_appointments, name='patient_appointments'),
    path('patient/appointments/<int:pk>/cancel/',     patient_cancel,     name='patient_cancel'),
    path('patient/appointments/<int:pk>/reschedule/', patient_reschedule, name='patient_reschedule'),

    # ── operator portal ──────────────────────────────────────────────────────
    path('operator/',                          operator_dashboard,        name='operator_dashboard'),
    path('operator/doctors/',                  operator_doctors,          name='operator_doctors'),
    path('operator/doctors/add/',              operator_doctor_add,       name='operator_doctor_add'),
    path('operator/doctors/<int:pk>/edit/',    operator_doctor_edit,      name='operator_doctor_edit'),
    path('operator/doctors/<int:pk>/delete/',  operator_doctor_delete,    name='operator_doctor_delete'),
    path('operator/patients/',                 operator_patients,         name='operator_patients'),
    path('operator/appointments/',             operator_appointments,     name='operator_appointments'),
    path('operator/settings/',                 operator_platform_settings, name='operator_platform_settings'),
]
