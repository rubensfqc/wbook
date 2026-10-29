"""The only place that decides which times are free and which are shown. See docs/ai/05-agenda-and-booking.md."""

from datetime import date, datetime, time, timedelta

from django.utils import timezone

DEFAULT_VISIBLE_SLOTS = 4  # default of BookingSettings.max_visible_slots; 0 there means "show all"


def _aware(dentist, day, t):
    return datetime.combine(day, t, tzinfo=dentist.tzinfo)


def day_bounds(dentist, day):
    start = _aware(dentist, day, time(0, 0))
    return start, start + timedelta(days=1)


def bookable_window(dentist, now=None):
    now = now or timezone.now()
    b = dentist.booking
    earliest = now + timedelta(hours=b.min_lead_hours)
    last_day = timezone.localtime(now, dentist.tzinfo).date() + timedelta(days=b.booking_horizon_days)
    latest = _aware(dentist, last_day, time(23, 59))
    return earliest, latest


def _ranges(dentist, day):
    hours = [h for h in dentist.working_hours.all() if h.weekday == day.weekday()]
    return [(_aware(dentist, day, h.start), _aware(dentist, day, h.end)) for h in sorted(hours, key=lambda h: h.start)]


def busy_intervals(dentist, start, end, exclude=None):
    from .models import Appointment

    out = []
    for blk in dentist.time_blocks.filter(start__lt=end, end__gt=start):
        out.append((blk.start, blk.end))
    qs = Appointment.objects.filter(dentist=dentist, status__in=Appointment.BLOCKING_STATUSES, start__lt=end + timedelta(hours=4),
                                    end__gt=start - timedelta(hours=4)).select_related("type")
    if exclude is not None:
        qs = qs.exclude(pk=exclude.pk)
    for a in qs:
        out.append((a.start, a.end + timedelta(minutes=a.type.buffer_min)))
    return out


def _overlaps(s, e, busy):
    return any(s < be and e > bs for bs, be in busy)


def grid(dentist, appt_type, day, exclude=None):
    """Free start times per working range for the whole day, ignoring the bookable window."""
    step = timedelta(minutes=dentist.booking.slot_step_min)
    need = timedelta(minutes=appt_type.duration_min + appt_type.buffer_min)
    ds, de = day_bounds(dentist, day)
    busy = busy_intervals(dentist, ds, de, exclude=exclude)
    per_range = []
    for rs, re_ in _ranges(dentist, day):
        times, t = [], rs
        while t + need <= re_:
            if not _overlaps(t, t + need, busy):
                times.append(t)
            t += step
        per_range.append(times)
    return per_range


def _in_window(t, window):
    return window[0] <= t <= window[1]


def free_times(dentist, appt_type, day, now=None, exclude=None):
    window = bookable_window(dentist, now)
    return [t for rng in grid(dentist, appt_type, day, exclude) for t in rng if _in_window(t, window)]


def allocate(counts, total):
    """Picks per range: at least one per non-empty range while picks remain, then largest remainder."""
    k = [0] * len(counts)
    remaining = total
    for i, n in enumerate(counts):
        if n and remaining:
            k[i] = 1
            remaining -= 1
    size = sum(counts) or 1
    while remaining > 0:
        best, best_gap = None, None
        for i, n in enumerate(counts):
            if k[i] >= n:
                continue
            gap = n * total / size - k[i]
            if best_gap is None or gap > best_gap:
                best, best_gap = i, gap
        if best is None:
            break
        k[best] += 1
        remaining -= 1
    return k


def spread(per_range, limit=DEFAULT_VISIBLE_SLOTS):
    counts = [len(r) for r in per_range]
    total = min(limit, sum(counts))
    picks = []
    for rng, k in zip(per_range, allocate(counts, total)):
        n = len(rng)
        for i in range(k):
            picks.append(rng[(2 * i + 1) * n // (2 * k)])
    return sorted(picks)


def visible_times(dentist, appt_type, day, now=None, exclude=None):
    """Times shown to visitors and patients: at most `max_visible_slots` per day (0 = all), spread over the day."""
    window = bookable_window(dentist, now)
    per_range = grid(dentist, appt_type, day, exclude)
    limit = dentist.booking.max_visible_slots
    if limit:
        chosen = spread(per_range, limit)
    else:
        chosen = [t for rng in per_range for t in rng]
    return [t for t in chosen if _in_window(t, window)]


def is_visible(dentist, appt_type, start, now=None, exclude=None):
    day = timezone.localtime(start, dentist.tzinfo).date()
    return start in visible_times(dentist, appt_type, day, now=now, exclude=exclude)


def is_free_for_dentist(dentist, appt_type, start, exclude=None):
    end = start + timedelta(minutes=appt_type.duration_min + appt_type.buffer_min)
    return not _overlaps(start, end, busy_intervals(dentist, start - timedelta(days=1), end + timedelta(days=1), exclude))


def week_of(day):
    monday = day - timedelta(days=day.weekday())
    return [monday + timedelta(days=i) for i in range(7)]


def week_visible(dentist, appt_type, week_start, now=None, exclude=None):
    """[(date, [times])] for the 7 days of the week containing week_start."""
    window = bookable_window(dentist, now)
    out = []
    for d in week_of(week_start):
        ds, de = day_bounds(dentist, d)
        if de < window[0] or ds > window[1]:
            out.append((d, []))
        else:
            out.append((d, visible_times(dentist, appt_type, d, now=now, exclude=exclude)))
    return out


def parse_week(value, dentist):
    try:
        return date.fromisoformat(value)
    except (TypeError, ValueError):
        return timezone.localtime(timezone.now(), dentist.tzinfo).date()
