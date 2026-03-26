from datetime import date, timedelta
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import HttpResponseForbidden
from django.utils import timezone
from booking.models import DoctorProfile, PatientProfile, Appointment, BlockedPeriod


def patient_required(view_func):
    @login_required
    def wrapper(request, *args, **kwargs):
        if not request.user.is_patient:
            return HttpResponseForbidden('Patient access only.')
        return view_func(request, *args, **kwargs)
    return wrapper


@patient_required
def patient_dashboard(request):
    profile  = request.user.patient_profile
    doctor   = profile.doctor
    today    = date.today()
    upcoming = Appointment.objects.filter(
        patient_user=request.user,
        start_time__date__gte=today,
        status__in=[Appointment.Status.CONFIRMED, Appointment.Status.PENDING],
    ).order_by('start_time')[:5]
    past = Appointment.objects.filter(
        patient_user=request.user,
        start_time__date__lt=today,
    ).order_by('-start_time')[:5]
    return render(request, 'booking/patient/dashboard.html', {
        'patient': profile, 'doctor': doctor,
        'upcoming': upcoming, 'past': past,
    })


@patient_required
def patient_book(request):
    """Show available slots for the patient's doctor and let them book."""
    profile = request.user.patient_profile
    doctor  = profile.doctor

    # Build slots for next 14 days
    today       = date.today()
    blocked     = BlockedPeriod.objects.filter(doctor=doctor)
    days_ahead  = 14
    slots_by_day = []

    for offset in range(days_ahead):
        d = today + timedelta(days=offset)
        # skip blocked
        if any(b.contains(d) for b in blocked):
            continue
        raw_slots = doctor.get_slots_for_date(d)
        if not raw_slots:
            continue
        # remove already booked
        taken = set(
            Appointment.objects.filter(
                doctor=doctor,
                start_time__date=d,
                status__in=[Appointment.Status.CONFIRMED, Appointment.Status.PENDING],
            ).values_list('start_time', flat=True)
        )
        available = [s for s in raw_slots
                     if timezone.make_aware(s) not in taken
                     and (not timezone.is_aware(list(taken)[0]) if taken else True)]
        # simpler: just compare naive
        taken_naive = set(
            Appointment.objects.filter(
                doctor=doctor,
                start_time__date=d,
                status__in=[Appointment.Status.CONFIRMED, Appointment.Status.PENDING],
            ).values_list('start_time', flat=True)
        )
        free = [s for s in raw_slots]
        if free:
            slots_by_day.append({'date': d, 'slots': free})

    if request.method == 'POST':
        slot_str = request.POST.get('slot')
        notes    = request.POST.get('notes', '')
        if slot_str:
            from datetime import datetime
            start = datetime.fromisoformat(slot_str)
            from django.utils import timezone as tz
            start_aware = tz.make_aware(start)
            end_aware   = start_aware + timedelta(minutes=doctor.slot_duration_minutes)
            # check not already taken
            conflict = Appointment.objects.filter(
                doctor=doctor,
                start_time=start_aware,
                status__in=[Appointment.Status.CONFIRMED, Appointment.Status.PENDING],
            ).exists()
            if conflict:
                messages.error(request, 'That slot was just taken. Please choose another.')
            else:
                Appointment.objects.create(
                    doctor=doctor,
                    patient_user=request.user,
                    start_time=start_aware,
                    end_time=end_aware,
                    notes=notes,
                    status=Appointment.Status.CONFIRMED,  # registered patients auto-confirmed
                )
                messages.success(request, 'Appointment confirmed!')
                return redirect('patient_appointments')
    return render(request, 'booking/patient/book.html', {
        'doctor': doctor, 'slots_by_day': slots_by_day,
    })


@patient_required
def patient_appointments(request):
    apts = Appointment.objects.filter(patient_user=request.user).order_by('-start_time')
    return render(request, 'booking/patient/appointments.html', {
        'appointments': apts,
        'patient': request.user.patient_profile,
    })


@patient_required
def patient_cancel(request, pk):
    apt = get_object_or_404(Appointment, pk=pk, patient_user=request.user)
    if not apt.can_cancel():
        messages.error(request, 'Cancellation window has passed.')
        return redirect('patient_appointments')
    if request.method == 'POST':
        apt.status = Appointment.Status.CANCELLED
        apt.save()
        messages.success(request, 'Appointment cancelled.')
    return redirect('patient_appointments')


@patient_required
def patient_reschedule(request, pk):
    apt     = get_object_or_404(Appointment, pk=pk, patient_user=request.user)
    profile = request.user.patient_profile
    doctor  = profile.doctor

    if not apt.can_cancel():
        messages.error(request, 'Rescheduling window has passed.')
        return redirect('patient_appointments')

    today       = date.today()
    blocked     = BlockedPeriod.objects.filter(doctor=doctor)
    slots_by_day = []
    for offset in range(14):
        d = today + timedelta(days=offset)
        if any(b.contains(d) for b in blocked):
            continue
        raw_slots = doctor.get_slots_for_date(d)
        if raw_slots:
            slots_by_day.append({'date': d, 'slots': raw_slots})

    if request.method == 'POST':
        slot_str = request.POST.get('slot')
        if slot_str:
            from datetime import datetime
            from django.utils import timezone as tz
            start_aware = tz.make_aware(datetime.fromisoformat(slot_str))
            end_aware   = start_aware + timedelta(minutes=doctor.slot_duration_minutes)
            conflict = Appointment.objects.filter(
                doctor=doctor, start_time=start_aware,
                status__in=[Appointment.Status.CONFIRMED, Appointment.Status.PENDING],
            ).exclude(pk=apt.pk).exists()
            if conflict:
                messages.error(request, 'Slot taken. Choose another.')
            else:
                apt.status     = Appointment.Status.CANCELLED
                apt.save()
                Appointment.objects.create(
                    doctor=doctor,
                    patient_user=request.user,
                    start_time=start_aware,
                    end_time=end_aware,
                    notes=apt.notes,
                    status=Appointment.Status.CONFIRMED,
                )
                messages.success(request, 'Appointment rescheduled!')
                return redirect('patient_appointments')

    return render(request, 'booking/patient/reschedule.html', {
        'apt': apt, 'doctor': doctor, 'slots_by_day': slots_by_day,
    })
