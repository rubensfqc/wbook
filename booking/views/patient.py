from datetime import date, timedelta, datetime
import json

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import HttpResponseForbidden
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from booking.models import DoctorProfile, PatientProfile, Appointment, BlockedPeriod


def patient_required(view_func):
    @login_required
    def wrapper(request, *args, **kwargs):
        if not request.user.is_patient:
            return HttpResponseForbidden(_('Patient access only.'))
        return view_func(request, *args, **kwargs)
    return wrapper


def _build_patient_calendar(doctor, days=90):
    """
    Returns (available_dates set, slots_json dict) with spread slots,
    excluding already-booked times.
    """
    today   = date.today()
    blocks  = BlockedPeriod.objects.filter(doctor=doctor)
    blocked = set()
    for b in blocks:
        d = b.start_date
        while d <= b.end_date:
            blocked.add(d)
            d += timedelta(days=1)

    available_dates = set()
    slots_by_date   = {}

    for offset in range(days):
        d = today + timedelta(days=offset)
        if d in blocked:
            continue
        all_slots = doctor.get_all_slots_for_date(d)
        if not all_slots:
            continue
        taken_qs = Appointment.objects.filter(
            doctor=doctor,
            start_time__date=d,
            status__in=[Appointment.Status.CONFIRMED, Appointment.Status.PENDING],
        ).values_list('start_time', flat=True)
        taken = {t.replace(tzinfo=None) if hasattr(t, 'tzinfo') else t for t in taken_qs}
        free  = [s for s in all_slots if s not in taken]
        spread = doctor.spread_slots(free)
        if spread:
            iso = d.isoformat()
            available_dates.add(iso)
            slots_by_date[iso] = [s.strftime('%H:%M') for s in spread]

    return sorted(available_dates), json.dumps(slots_by_date)


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
    profile = request.user.patient_profile
    doctor  = profile.doctor

    available_dates, slots_json = _build_patient_calendar(doctor, days=90)
    selected_slot = request.POST.get('slot')

    if request.method == 'POST' and selected_slot:
        start       = datetime.fromisoformat(selected_slot)
        start_aware = timezone.make_aware(start)
        end_aware   = start_aware + timedelta(minutes=doctor.slot_duration_minutes)

        conflict = Appointment.objects.filter(
            doctor=doctor, start_time=start_aware,
            status__in=[Appointment.Status.CONFIRMED, Appointment.Status.PENDING],
        ).exists()
        if conflict:
            messages.error(request, _('That slot was just taken. Please choose another.'))
        else:
            Appointment.objects.create(
                doctor=doctor,
                patient_user=request.user,
                start_time=start_aware,
                end_time=end_aware,
                notes=request.POST.get('notes', ''),
                status=Appointment.Status.CONFIRMED,
            )
            messages.success(request, _('Appointment confirmed!'))
            return redirect('patient_appointments')

    return render(request, 'booking/patient/book.html', {
        'doctor':          doctor,
        'available_dates': available_dates,
        'slots_json':      slots_json,
        'selected_slot':   selected_slot,
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
        messages.error(request, _('Cancellation window has passed.'))
        return redirect('patient_appointments')
    if request.method == 'POST':
        apt.status = Appointment.Status.CANCELLED
        apt.save()
        messages.success(request, _('Appointment cancelled.'))
    return redirect('patient_appointments')


@patient_required
def patient_reschedule(request, pk):
    apt     = get_object_or_404(Appointment, pk=pk, patient_user=request.user)
    profile = request.user.patient_profile
    doctor  = profile.doctor

    if not apt.can_cancel():
        messages.error(request, _('Rescheduling window has passed.'))
        return redirect('patient_appointments')

    available_dates, slots_json = _build_patient_calendar(doctor, days=90)
    selected_slot = request.POST.get('slot')

    if request.method == 'POST' and selected_slot:
        start_aware = timezone.make_aware(datetime.fromisoformat(selected_slot))
        end_aware   = start_aware + timedelta(minutes=doctor.slot_duration_minutes)
        conflict = Appointment.objects.filter(
            doctor=doctor, start_time=start_aware,
            status__in=[Appointment.Status.CONFIRMED, Appointment.Status.PENDING],
        ).exclude(pk=apt.pk).exists()
        if conflict:
            messages.error(request, _('Slot taken. Choose another.'))
        else:
            apt.status = Appointment.Status.CANCELLED
            apt.save()
            Appointment.objects.create(
                doctor=doctor,
                patient_user=request.user,
                start_time=start_aware,
                end_time=end_aware,
                notes=apt.notes,
                status=Appointment.Status.CONFIRMED,
            )
            messages.success(request, _('Appointment rescheduled!'))
            return redirect('patient_appointments')

    return render(request, 'booking/patient/reschedule.html', {
        'apt':             apt,
        'doctor':          doctor,
        'available_dates': available_dates,
        'slots_json':      slots_json,
        'selected_slot':   selected_slot,
    })
