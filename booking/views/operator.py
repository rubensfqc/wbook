from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import HttpResponseForbidden
from booking.models import DoctorProfile, PatientProfile, Appointment, PlatformSettings
from accounts.models import Seller
from booking.forms import OperatorDoctorForm
import secrets, string


def operator_required(view_func):
    @login_required
    def wrapper(request, *args, **kwargs):
        if not request.user.is_operator:
            return HttpResponseForbidden('Operator access only.')
        return view_func(request, *args, **kwargs)
    return wrapper


@operator_required
def operator_dashboard(request):
    platform      = PlatformSettings.get_solo()
    doctors       = DoctorProfile.objects.select_related('user').all()
    total_doctors = doctors.count()
    trial_doctors = sum(1 for d in doctors if d.trial_is_active and d.trial_start_date)
    active        = sum(1 for d in doctors if d.can_access)
    expired       = sum(1 for d in doctors if not d.trial_is_active and not d.is_suspended)
    suspended     = sum(1 for d in doctors if d.is_suspended)
    total_patients = PatientProfile.objects.count()
    total_apts     = Appointment.objects.count()
    return render(request, 'booking/operator/dashboard.html', {
        'platform': platform,
        'doctors': doctors[:20],
        'total_doctors': total_doctors,
        'trial_doctors': trial_doctors,
        'active_doctors': active,
        'expired': expired,
        'suspended': suspended,
        'total_patients': total_patients,
        'total_appointments': total_apts,
    })


@operator_required
def operator_doctors(request):
    doctors = DoctorProfile.objects.select_related('user').order_by('-user__date_joined')
    return render(request, 'booking/operator/doctors.html', {'doctors': doctors})


@operator_required
def operator_doctor_add(request):
    form = OperatorDoctorForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        cd = form.cleaned_data
        alphabet = string.ascii_letters + string.digits
        raw_pass = cd.get('password') or ''.join(secrets.choice(alphabet) for _ in range(12))
        user = Seller.objects.create_user(
            username=cd['username'],
            email=cd['email'],
            name=cd['name'],
            role=Seller.Roles.DOCTOR,
            password=raw_pass,
        )
        profile = user.doctor_profile  # auto-created by signal
        profile.specialty  = cd.get('specialty', '')
        profile.clinic_name = cd.get('clinic_name', '')
        profile.trial_days = cd.get('trial_days', 14)
        profile.save()
        messages.success(request, f'Doctor {user.name} created. Temp password: {raw_pass}')
        return redirect('operator_doctors')
    return render(request, 'booking/operator/doctor_form.html', {'form': form, 'action': 'Add'})


@operator_required
def operator_doctor_edit(request, pk):
    profile = get_object_or_404(DoctorProfile, pk=pk)
    form = OperatorDoctorForm(
        request.POST or None,
        instance=profile,
        doctor_user=profile.user,
    )
    if request.method == 'POST' and form.is_valid():
        cd = form.cleaned_data
        profile.user.name  = cd['name']
        profile.user.email = cd['email']
        if cd.get('password'):
            profile.user.set_password(cd['password'])
        profile.user.save()
        form.save()
        messages.success(request, 'Doctor updated.')
        return redirect('operator_doctors')
    return render(request, 'booking/operator/doctor_form.html', {'form': form, 'action': 'Edit', 'profile': profile})


@operator_required
def operator_doctor_delete(request, pk):
    profile = get_object_or_404(DoctorProfile, pk=pk)
    if request.method == 'POST':
        profile.user.delete()
        messages.success(request, 'Doctor removed.')
    return redirect('operator_doctors')


@operator_required
def operator_patients(request):
    patients = PatientProfile.objects.select_related('user', 'doctor__user').order_by('-created_at')
    return render(request, 'booking/operator/patients.html', {'patients': patients})


@operator_required
def operator_appointments(request):
    apts = Appointment.objects.select_related('doctor__user', 'patient_user').order_by('-start_time')
    return render(request, 'booking/operator/appointments.html', {'appointments': apts})


@operator_required
def operator_platform_settings(request):
    platform = PlatformSettings.get_solo()
    from django import forms as dj_forms

    class PlatformForm(dj_forms.ModelForm):
        class Meta:
            model  = PlatformSettings
            fields = ['default_trial_days', 'platform_name', 'support_email']

    form = PlatformForm(request.POST or None, instance=platform)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Platform settings updated.')
        return redirect('operator_platform_settings')
    return render(request, 'booking/operator/platform_settings.html', {'form': form, 'platform': platform})
