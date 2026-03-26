from datetime import date, timedelta, datetime
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt

from booking.models import DoctorProfile, Appointment, BlockedPeriod, PatientProfile, Lead
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


# ── Slot availability helper ──────────────────────────────────────────────────

def _build_slots(doctor):
    """Return slots_by_day list for the next 14 days."""
    today   = date.today()
    blocked = BlockedPeriod.objects.filter(doctor=doctor)
    result  = []
    for offset in range(14):
        d = today + timedelta(days=offset)
        if any(b.contains(d) for b in blocked):
            continue
        raw = doctor.get_slots_for_date(d)
        if not raw:
            continue
        taken = set(
            Appointment.objects.filter(
                doctor=doctor,
                start_time__date=d,
                status__in=[Appointment.Status.CONFIRMED, Appointment.Status.PENDING],
            ).values_list('start_time', flat=True)
        )
        # compare naive vs naive
        taken_naive = {t.replace(tzinfo=None) if hasattr(t, 'tzinfo') else t for t in taken}
        free = [s for s in raw if s not in taken_naive]
        if free:
            result.append({'date': d, 'slots': free})
    return result


# ── AJAX: capture lead at Step 1 ─────────────────────────────────────────────

@require_POST
def capture_lead(request, slug):
    """
    Called by the booking page when the patient clicks 'Next' (Step 1).
    Creates or updates a Lead record immediately — before any slot is chosen.
    Returns JSON with the lead_id so the frontend can pass it along at Step 2.
    """
    doctor_user = get_object_or_404(Seller, slug=slug, role=Seller.Roles.DOCTOR)
    doctor      = get_object_or_404(DoctorProfile, user=doctor_user)

    name  = request.POST.get('name',  '').strip()
    email = request.POST.get('email', '').strip()
    phone = request.POST.get('phone', '').strip()
    notes = request.POST.get('notes', '').strip()

    if not name or not email:
        return JsonResponse({'ok': False, 'error': 'Name and email are required.'}, status=400)

    # Upsert: if the same email already has a NEW/CONTACTED lead for this doctor,
    # update it instead of creating a duplicate.
    lead, created = Lead.objects.update_or_create(
        doctor=doctor,
        email=email,
        status__in=[Lead.Status.NEW, Lead.Status.CONTACTED],
        defaults=dict(
            name=name,
            phone=phone,
            notes=notes,
            status=Lead.Status.NEW,
        ),
    )

    return JsonResponse({
        'ok':      True,
        'lead_id': lead.pk,
        'created': created,
    })


# ── Public booking page (GET + final POST) ────────────────────────────────────

def public_booking(request, slug):
    """Public booking page — accessible by anyone, no login required."""
    doctor_user = get_object_or_404(Seller, slug=slug, role=Seller.Roles.DOCTOR)
    doctor      = get_object_or_404(DoctorProfile, user=doctor_user)

    # Registered patients of this doctor go straight to their portal
    if request.user.is_authenticated and request.user.is_patient:
        try:
            if request.user.patient_profile.doctor == doctor:
                return redirect('patient_book')
        except Exception:
            pass

    slots_by_day  = _build_slots(doctor)
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
            messages.error(request, 'That slot was just taken. Please choose another.')
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

            # Mark the matching lead as CONVERTED and link the appointment
            if lead_id:
                Lead.objects.filter(pk=lead_id, doctor=doctor).update(
                    status=Lead.Status.CONVERTED,
                    appointment=apt,
                )
            else:
                # Fallback: try to find by email if JS failed to pass lead_id
                Lead.objects.filter(
                    doctor=doctor,
                    email=cd['email'],
                    status__in=[Lead.Status.NEW, Lead.Status.CONTACTED],
                ).update(
                    status=Lead.Status.CONVERTED,
                    appointment=apt,
                )

            messages.success(
                request,
                'Your appointment request was submitted! You will receive an email once confirmed.',
            )
            return redirect('booking_confirmation', slug=slug)

    return render(request, 'booking/public/booking_page.html', {
        'doctor':       doctor,
        'slots_by_day': slots_by_day,
        'form':         form,
        'selected_slot': selected_slot,
    })


def booking_confirmation(request, slug):
    doctor_user = get_object_or_404(Seller, slug=slug, role=Seller.Roles.DOCTOR)
    doctor      = get_object_or_404(DoctorProfile, user=doctor_user)
    return render(request, 'booking/public/confirmation.html', {'doctor': doctor})
