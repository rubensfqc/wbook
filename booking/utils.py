from datetime import datetime, timedelta, time
from .models import WorkingHours, BlockedPeriod, Appointment


def get_available_slots(doctor, target_date):
    """
    Return a list of datetime.time objects representing available slots
    for `doctor` on `target_date`.
    Respects:
      - Working hours for that weekday
      - Daily slot limit
      - Blocked periods
      - Already-booked (non-cancelled/rejected) appointments
    """
    weekday = target_date.weekday()

    # Check blocked periods
    blocked = BlockedPeriod.objects.filter(
        doctor=doctor,
        start_date__lte=target_date,
        end_date__gte=target_date,
    )
    if blocked.exists():
        return []

    # Get working hours for this weekday
    try:
        wh = WorkingHours.objects.get(doctor=doctor, weekday=weekday, is_active=True)
    except WorkingHours.DoesNotExist:
        return []

    # Generate all possible slots
    slots = []
    current = datetime.combine(target_date, wh.start_time)
    end     = datetime.combine(target_date, wh.end_time)
    delta   = timedelta(minutes=doctor.slot_duration_minutes)

    while current + delta <= end:
        slots.append(current.time())
        current += delta

    # Apply daily slot limit
    slots = slots[:doctor.daily_slot_limit]

    # Remove already-booked slots
    booked_times = set(
        Appointment.objects.filter(
            doctor=doctor,
            appointment_date=target_date,
        ).exclude(
            status__in=[Appointment.Status.CANCELLED, Appointment.Status.REJECTED]
        ).values_list('appointment_time', flat=True)
    )

    available = [s for s in slots if s not in booked_times]
    return available
