from datetime import date, timedelta
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import HttpResponseForbidden
from django.utils.translation import gettext_lazy as _
from booking.models import DoctorProfile, PatientProfile, Appointment, BlockedPeriod
from booking.forms import (
    DoctorProfileForm, WorkingDaysForm, PatientInviteForm,
    PatientUpdateForm, BlockedPeriodForm, AppointmentNoteForm,
)
from accounts.models import Seller
import secrets
import string


def doctor_required(view_func):
    @login_required
    def wrapper(request, *args, **kwargs):
        if not request.user.is_doctor:
            return HttpResponseForbidden(_('Doctor access only.'))
        return view_func(request, *args, **kwargs)
    return wrapper


# ── Dashboard ─────────────────────────────────────────────────────────────────

@doctor_required
def doctor_dashboard(request):
    doctor = request.user.doctor_profile
    today  = date.today()
    upcoming = Appointment.objects.filter(
        doctor=doctor,
        start_time__date__gte=today,
        status__in=[Appointment.Status.CONFIRMED, Appointment.Status.PENDING],
    ).order_by('start_time')[:5]
    pending  = Appointment.objects.filter(doctor=doctor, status=Appointment.Status.PENDING).count()
    total_patients = doctor.patients.filter(is_active=True).count()
    today_apts = Appointment.objects.filter(
        doctor=doctor,
        start_time__date=today,
        status=Appointment.Status.CONFIRMED,
    ).count()
    return render(request, 'booking/doctor/dashboard.html', {
        'doctor': doctor,
        'upcoming': upcoming,
        'pending_count': pending,
        'total_patients': total_patients,
        'today_appointments': today_apts,
    })


# ── Calendar / appointments ───────────────────────────────────────────────────

@doctor_required
def doctor_appointments(request):
    doctor = request.user.doctor_profile
    status_filter = request.GET.get('status', '')
    qs = Appointment.objects.filter(doctor=doctor).order_by('-start_time')
    if status_filter:
        qs = qs.filter(status=status_filter)
    return render(request, 'booking/doctor/appointments.html', {
        'doctor': doctor,
        'appointments': qs,
        'status_filter': status_filter,
        'status_choices': Appointment.Status.choices,
    })


@doctor_required
def appointment_action(request, pk, action):
    doctor = request.user.doctor_profile
    apt    = get_object_or_404(Appointment, pk=pk, doctor=doctor)
    if action == 'confirm':
        apt.status = Appointment.Status.CONFIRMED
        messages.success(request, _('Appointment confirmed.'))
    elif action == 'reject':
        apt.status = Appointment.Status.REJECTED
        messages.warning(request, _('Appointment rejected.'))
    elif action == 'complete':
        apt.status = Appointment.Status.COMPLETED
        messages.success(request, _('Appointment marked as completed.'))
    apt.save()
    return redirect('doctor_appointments')


@doctor_required
def appointment_note(request, pk):
    doctor = request.user.doctor_profile
    apt    = get_object_or_404(Appointment, pk=pk, doctor=doctor)
    form   = AppointmentNoteForm(request.POST or None, instance=apt)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, _('Notes saved.'))
        return redirect('doctor_appointments')
    return render(request, 'booking/doctor/appointment_note.html', {'apt': apt, 'form': form})


# ── Schedule settings ─────────────────────────────────────────────────────────

@doctor_required
def doctor_schedule_settings(request):
    doctor  = request.user.doctor_profile
    profile_form     = DoctorProfileForm(instance=doctor)
    working_days_form = WorkingDaysForm(doctor=doctor)

    if request.method == 'POST':
        profile_form      = DoctorProfileForm(request.POST, request.FILES, instance=doctor)
        working_days_form = WorkingDaysForm(request.POST, doctor=doctor)
        if profile_form.is_valid() and working_days_form.is_valid():
            profile = profile_form.save(commit=False)
            profile.working_days = [int(d) for d in working_days_form.cleaned_data['working_days']]
            profile.save()
            messages.success(request, _('Schedule settings updated.'))
            return redirect('doctor_schedule_settings')

    return render(request, 'booking/doctor/schedule_settings.html', {
        'doctor': doctor,
        'profile_form': profile_form,
        'working_days_form': working_days_form,
    })


# ── Blocked periods ───────────────────────────────────────────────────────────

@doctor_required
def blocked_periods(request):
    doctor = request.user.doctor_profile
    periods = BlockedPeriod.objects.filter(doctor=doctor).order_by('start_date')
    form    = BlockedPeriodForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        bp = form.save(commit=False)
        bp.doctor = doctor
        bp.save()
        messages.success(request, _('Period blocked.'))
        return redirect('blocked_periods')
    return render(request, 'booking/doctor/blocked_periods.html', {
        'doctor': doctor, 'periods': periods, 'form': form,
    })


@doctor_required
def blocked_period_delete(request, pk):
    doctor = request.user.doctor_profile
    bp = get_object_or_404(BlockedPeriod, pk=pk, doctor=doctor)
    if request.method == 'POST':
        bp.delete()
        messages.success(request, _('Block removed.'))
    return redirect('blocked_periods')


# ── Patients ──────────────────────────────────────────────────────────────────

@doctor_required
def doctor_patients(request):
    doctor   = request.user.doctor_profile
    patients = doctor.patients.select_related('user').order_by('-created_at')
    return render(request, 'booking/doctor/patients.html', {
        'doctor': doctor, 'patients': patients,
    })


@doctor_required
def patient_invite(request):
    doctor = request.user.doctor_profile
    form   = PatientInviteForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        cd = form.cleaned_data
        # Create Seller user
        alphabet = string.ascii_letters + string.digits
        raw_pass = ''.join(secrets.choice(alphabet) for _ in range(12))
        user = Seller.objects.create_user(
            username=cd['email'].split('@')[0] + '_' + secrets.token_hex(3),
            email=cd['email'],
            name=cd['name'],
            role=Seller.Roles.PATIENT,
            password=raw_pass,
        )
        PatientProfile.objects.create(user=user, doctor=doctor, notes=cd.get('notes', ''))
        # Send credentials by email
        from django.core.mail import send_mail
        from django.conf import settings as djsettings
        login_url = request.build_absolute_uri(f'/book/{doctor.user.slug}/')
        send_mail(
            'Your wbook365 patient account',
            (f'Hello {user.name},\n\nYour doctor has created an account for you.\n'
             f'Login URL: {login_url}\nEmail: {user.email}\nPassword: {raw_pass}\n\n'
             f'Please change your password after logging in.'),
            djsettings.DEFAULT_FROM_EMAIL,
            [user.email],
            fail_silently=True,
        )
        messages.success(request, _('Patient %(name)s invited. Credentials sent to %(email)s.') % {'name': user.name, 'email': user.email})
        return redirect('doctor_patients')
    return render(request, 'booking/doctor/patient_invite.html', {'form': form, 'doctor': doctor})


@doctor_required
def patient_detail(request, pk):
    doctor  = request.user.doctor_profile
    profile = get_object_or_404(PatientProfile, pk=pk, doctor=doctor)
    apts    = Appointment.objects.filter(
        doctor=doctor, patient_user=profile.user
    ).order_by('-start_time')
    form = PatientUpdateForm(
        request.POST or None,
        instance=profile,
        patient_user=profile.user,
    )
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, _('Patient updated.'))
        return redirect('patient_detail', pk=pk)
    return render(request, 'booking/doctor/patient_detail.html', {
        'profile': profile, 'appointments': apts, 'form': form, 'doctor': doctor,
    })


@doctor_required
def patient_remove(request, pk):
    doctor  = request.user.doctor_profile
    profile = get_object_or_404(PatientProfile, pk=pk, doctor=doctor)
    if request.method == 'POST':
        profile.is_active = False
        profile.save()
        messages.warning(request, _('Patient deactivated.'))
    return redirect('doctor_patients')


# ── Profile settings ──────────────────────────────────────────────────────────

@doctor_required
def doctor_profile_settings(request):
    doctor = request.user.doctor_profile
    from accounts.forms import SellerUpdateForm
    user_form    = SellerUpdateForm(request.POST or None, request.FILES or None, instance=request.user)
    profile_form = DoctorProfileForm(request.POST or None, request.FILES or None, instance=doctor)
    if request.method == 'POST':
        if user_form.is_valid() and profile_form.is_valid():
            user_form.save()
            profile_form.save()
            messages.success(request, _('Profile updated.'))
            return redirect('doctor_profile_settings')
    return render(request, 'booking/doctor/profile_settings.html', {
        'doctor': doctor, 'user_form': user_form, 'profile_form': profile_form,
    })


# ── Trial expired ─────────────────────────────────────────────────────────────

def trial_expired(request):
    return render(request, 'booking/trial_expired.html')


# ── Leads ─────────────────────────────────────────────────────────────────────

@doctor_required
def doctor_leads(request):
    doctor = request.user.doctor_profile
    status_filter = request.GET.get('status', '')
    qs = doctor.leads.all().order_by('-created_at')
    if status_filter:
        qs = qs.filter(status=status_filter)

    from booking.models import Lead
    return render(request, 'booking/doctor/leads.html', {
        'doctor': doctor,
        'leads': qs,
        'status_filter': status_filter,
        'status_choices': Lead.Status.choices,
        'counts': {
            'new':       doctor.leads.filter(status='NEW').count(),
            'contacted': doctor.leads.filter(status='CONTACTED').count(),
            'converted': doctor.leads.filter(status='CONVERTED').count(),
            'lost':      doctor.leads.filter(status='LOST').count(),
        },
    })


@doctor_required
def lead_update_status(request, pk):
    doctor = request.user.doctor_profile
    from booking.models import Lead
    lead   = get_object_or_404(Lead, pk=pk, doctor=doctor)
    if request.method == 'POST':
        new_status = request.POST.get('status')
        if new_status in Lead.Status.values:
            lead.status = new_status
            lead.save()
            messages.success(request, _('Lead status updated to %(status)s.') % {'status': lead.get_status_display()})
    return redirect('doctor_leads')
