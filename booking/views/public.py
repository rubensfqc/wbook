from datetime import date, timedelta, datetime
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login
from django.contrib import messages
from django.utils import timezone
from booking.models import DoctorProfile, Appointment, BlockedPeriod, PatientProfile
from booking.forms import PublicBookingForm
from accounts.models import Seller


def dashboard_redirect(request):
    """Route authenticated users to their correct portal."""
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


def public_booking(request, slug):
    """Public booking page for a doctor — accessible by anyone."""
    doctor_user = get_object_or_404(Seller, slug=slug, role=Seller.Roles.DOCTOR)
    doctor      = get_object_or_404(DoctorProfile, user=doctor_user)

    today    = date.today()
    blocked  = BlockedPeriod.objects.filter(doctor=doctor)
    slots_by_day = []

    for offset in range(14):
        d = today + timedelta(days=offset)
        if any(b.contains(d) for b in blocked):
            continue
        raw_slots = doctor.get_slots_for_date(d)
        if not raw_slots:
            continue
        taken = set(
            Appointment.objects.filter(
                doctor=doctor,
                start_time__date=d,
                status__in=[Appointment.Status.CONFIRMED, Appointment.Status.PENDING],
            ).values_list('start_time', flat=True)
        )
        free = [s for s in raw_slots
                if s not in [t.replace(tzinfo=None) if hasattr(t, 'tzinfo') else t for t in taken]]
        if free:
            slots_by_day.append({'date': d, 'slots': free})

    # If logged-in patient of this doctor, redirect to their portal
    if request.user.is_authenticated and request.user.is_patient:
        try:
            pp = request.user.patient_profile
            if pp.doctor == doctor:
                return redirect('patient_book')
        except Exception:
            pass

    form = PublicBookingForm(request.POST or None)
    selected_slot = request.POST.get('slot') or request.GET.get('slot')

    if request.method == 'POST' and form.is_valid() and selected_slot:
        cd    = form.cleaned_data
        start = datetime.fromisoformat(selected_slot)
        start_aware = timezone.make_aware(start)
        end_aware   = start_aware + timedelta(minutes=doctor.slot_duration_minutes)

        conflict = Appointment.objects.filter(
            doctor=doctor, start_time=start_aware,
            status__in=[Appointment.Status.CONFIRMED, Appointment.Status.PENDING],
        ).exists()
        if conflict:
            messages.error(request, 'That slot was just taken. Please choose another.')
        else:
            Appointment.objects.create(
                doctor=doctor,
                patient_name=cd['name'],
                patient_email=cd['email'],
                patient_phone=cd.get('phone', ''),
                start_time=start_aware,
                end_time=end_aware,
                notes=cd.get('notes', ''),
                status=Appointment.Status.PENDING,  # unregistered → needs confirmation
            )
            messages.success(
                request,
                'Your appointment request was submitted! You will receive an email once confirmed.',
            )
            return redirect('booking_confirmation', slug=slug)

    return render(request, 'booking/public/booking_page.html', {
        'doctor': doctor,
        'slots_by_day': slots_by_day,
        'form': form,
        'selected_slot': selected_slot,
    })


def booking_confirmation(request, slug):
    doctor_user = get_object_or_404(Seller, slug=slug, role=Seller.Roles.DOCTOR)
    doctor      = get_object_or_404(DoctorProfile, user=doctor_user)
    return render(request, 'booking/public/confirmation.html', {'doctor': doctor})
