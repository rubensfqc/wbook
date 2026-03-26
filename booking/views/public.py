from datetime import date, timedelta, datetime
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.http import require_POST

from booking.models import DoctorProfile, Appointment, BlockedPeriod, PatientProfile, Lead
from django.utils.translation import gettext_lazy as _
from booking.forms import PublicBookingForm
from accounts.models import Seller


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _taken_set_for_day(doctor, d):
    """Return set of naive datetimes already booked for doctor on date d."""
    qs = Appointment.objects.filter(
        doctor=doctor,
        start_time__date=d,
        status__in=[Appointment.Status.CONFIRMED, Appointment.Status.PENDING],
    ).values_list('start_time', flat=True)
    return {t.replace(tzinfo=None) if hasattr(t, 'tzinfo') else t for t in qs}


def _available_slots_for_day(doctor, d, blocked_dates):
    """
    Return the spread list of available slots for a given date.
    blocked_dates: set of date objects that are blocked.
    Returns [] if the day is off or fully booked.
    """
    if d in blocked_dates:
        return []
    all_slots = doctor.get_all_slots_for_date(d)
    if not all_slots:
        return []
    taken = _taken_set_for_day(doctor, d)
    free  = [s for s in all_slots if s not in taken]
    return doctor.spread_slots(free)


def _build_calendar_data(doctor, days=90):
    """
    Build two structures for the calendar:
      - available_dates : set of ISO date strings that have >= 1 free slot
      - slots_by_date   : dict {ISO date str -> [naive datetime, ...]}
    Covers today .. today + days.
    """
    today  = date.today()
    blocks = BlockedPeriod.objects.filter(doctor=doctor)
    blocked_dates = set()
    for b in blocks:
        d = b.start_date
        while d <= b.end_date:
            blocked_dates.add(d)
            d += timedelta(days=1)

    available_dates = set()
    slots_by_date   = {}

    for offset in range(days):
        d     = today + timedelta(days=offset)
        slots = _available_slots_for_day(doctor, d, blocked_dates)
        if slots:
            iso = d.isoformat()
            available_dates.add(iso)
            slots_by_date[iso] = slots

    return available_dates, slots_by_date


def _slots_to_json(slots_by_date):
    """
    Convert {date_str: [naive datetime, ...]} to
             {date_str: ['HH:MM', ...]} for JSON embedding in the template.
    """
    return {
        date_str: [s.strftime('%H:%M') for s in slots]
        for date_str, slots in slots_by_date.items()
    }


# ─────────────────────────────────────────────────────────────────────────────
# Dashboard redirect
# ─────────────────────────────────────────────────────────────────────────────

def dashboard_redirect(request):
    if not request.user.is_authenticated:
        return redirect('login')
    user = request.user
    if user.is_superuser or user.is_operator:
        return redirect('operator_dashboard')
    if user.is_doctor:
        return redirect('doctor_dashboard')
    if user.is_patient:
        return redirect('patient_dashboard')
    return redirect('login')


# ─────────────────────────────────────────────────────────────────────────────
# AJAX: capture lead at Step 1
# ─────────────────────────────────────────────────────────────────────────────

@require_POST
def capture_lead(request, slug):
    doctor_user = get_object_or_404(Seller, slug=slug, role=Seller.Roles.DOCTOR)
    doctor      = get_object_or_404(DoctorProfile, user=doctor_user)

    name  = request.POST.get('name',  '').strip()
    email = request.POST.get('email', '').strip()
    phone = request.POST.get('phone', '').strip()
    notes = request.POST.get('notes', '').strip()

    if not name or not email:
        return JsonResponse({'ok': False, 'error': 'Name and email are required.'}, status=400)

    lead, created = Lead.objects.update_or_create(
        doctor=doctor,
        email=email,
        status__in=[Lead.Status.NEW, Lead.Status.CONTACTED],
        defaults=dict(name=name, phone=phone, notes=notes, status=Lead.Status.NEW),
    )

    return JsonResponse({'ok': True, 'lead_id': lead.pk, 'created': created})


# ─────────────────────────────────────────────────────────────────────────────
# Public booking page
# ─────────────────────────────────────────────────────────────────────────────

def public_booking(request, slug):
    doctor_user = get_object_or_404(Seller, slug=slug, role=Seller.Roles.DOCTOR)
    doctor      = get_object_or_404(DoctorProfile, user=doctor_user)

    # Registered patients of this doctor go to their portal
    if request.user.is_authenticated and request.user.is_patient:
        try:
            if request.user.patient_profile.doctor == doctor:
                return redirect('patient_book')
        except Exception:
            pass

    available_dates, slots_by_date = _build_calendar_data(doctor, days=90)
    slots_json = _slots_to_json(slots_by_date)

    form          = PublicBookingForm(request.POST or None)
    selected_slot = request.POST.get('slot') or request.GET.get('slot')

    if request.method == 'POST' and form.is_valid() and selected_slot:
        cd          = form.cleaned_data
        lead_id     = request.POST.get('lead_id')
        start       = datetime.fromisoformat(selected_slot)
        start_aware = timezone.make_aware(start)
        end_aware   = start_aware + timedelta(minutes=doctor.slot_duration_minutes)

        conflict = Appointment.objects.filter(
            doctor=doctor,
            start_time=start_aware,
            status__in=[Appointment.Status.CONFIRMED, Appointment.Status.PENDING],
        ).exists()

        if conflict:
            messages.error(request, _('That slot was just taken. Please choose another.'))
        else:
            apt = Appointment.objects.create(
                doctor=doctor,
                patient_name=cd['name'],
                patient_email=cd['email'],
                patient_phone=cd.get('phone', ''),
                start_time=start_aware,
                end_time=end_aware,
                notes=cd.get('notes', ''),
                status=Appointment.Status.PENDING,
            )
            if lead_id:
                Lead.objects.filter(pk=lead_id, doctor=doctor).update(
                    status=Lead.Status.CONVERTED, appointment=apt)
            else:
                Lead.objects.filter(
                    doctor=doctor, email=cd['email'],
                    status__in=[Lead.Status.NEW, Lead.Status.CONTACTED],
                ).update(status=Lead.Status.CONVERTED, appointment=apt)

            messages.success(request, _('Your appointment request was submitted! You will receive an email once confirmed.'))
            return redirect('booking_confirmation', slug=slug)

    import json
    return render(request, 'booking/public/booking_page.html', {
        'doctor':          doctor,
        'available_dates': sorted(available_dates),
        'slots_json':      json.dumps(slots_json),
        'form':            form,
        'selected_slot':   selected_slot,
    })


def booking_confirmation(request, slug):
    doctor_user = get_object_or_404(Seller, slug=slug, role=Seller.Roles.DOCTOR)
    doctor      = get_object_or_404(DoctorProfile, user=doctor_user)
    return render(request, 'booking/public/confirmation.html', {'doctor': doctor})
