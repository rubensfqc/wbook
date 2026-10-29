from datetime import timedelta

from django.core.exceptions import ValidationError
from django.test import TestCase

from apps.agenda import services, slots
from apps.agenda.models import Appointment, TimeBlock

from .helpers import at, make_dentist, make_patient, next_weekday


class SlotTests(TestCase):
    def setUp(self):
        self.d = make_dentist()
        b = self.d.booking
        b.slot_step_min = 30
        b.save()
        self.type = self.d.appointment_types.get(name="Avaliação")  # 30 min
        self.tue = next_weekday(1)

    def hm(self, times):
        from django.utils import timezone

        return [f"{timezone.localtime(t, self.d.tzinfo):%H:%M}" for t in times]

    def test_grid_counts(self):
        per_range = slots.grid(self.d, self.type, self.tue)
        self.assertEqual([len(r) for r in per_range], [8, 9])

    def test_default_is_four(self):
        self.assertEqual(self.d.booking.max_visible_slots, 4)

    def test_empty_day_shows_spread_four(self):
        self.assertEqual(self.hm(slots.visible_times(self.d, self.type, self.tue)), ["09:00", "11:00", "14:30", "16:30"])

    def test_stable(self):
        a = slots.visible_times(self.d, self.type, self.tue)
        b = slots.visible_times(self.d, self.type, self.tue)
        self.assertEqual(a, b)

    def test_zero_shows_all(self):
        self.d.booking.max_visible_slots = 0
        self.d.booking.save()
        self.assertEqual(len(slots.visible_times(self.d, self.type, self.tue)), 17)

    def test_dentist_chooses_how_many(self):
        self.d.booking.max_visible_slots = 6
        self.d.booking.save()
        self.assertEqual(len(slots.visible_times(self.d, self.type, self.tue)), 6)
        self.d.booking.max_visible_slots = 2
        self.d.booking.save()
        self.assertEqual(self.hm(slots.visible_times(self.d, self.type, self.tue)), ["10:00", "15:30"])

    def test_booked_day_still_limited(self):
        p = make_patient(self.d)
        services.book(p, self.type, at(self.d, self.tue, 11))
        times = self.hm(slots.visible_times(self.d, self.type, self.tue))
        self.assertEqual(len(times), 4)
        self.assertNotIn("11:00", times)

    def test_week_never_exceeds_limit(self):
        p = make_patient(self.d)
        services.book(p, self.type, at(self.d, self.tue, 9))
        for _day, times in slots.week_visible(self.d, self.type, self.tue):
            self.assertLessEqual(len(times), 4)

    def test_blocks_and_buffer(self):
        TimeBlock.objects.create(dentist=self.d, start=at(self.d, self.tue, 8), end=at(self.d, self.tue, 12))
        self.d.booking.max_visible_slots = 0
        self.d.booking.save()
        self.assertEqual(len(slots.visible_times(self.d, self.type, self.tue)), 9)
        long = self.d.appointment_types.get(name="Limpeza")  # 45 min
        long.buffer_min = 15
        long.save()
        # 13:30-18:00 with 60 min needed, step 30 → 13:30..17:00 = 8
        self.assertEqual(len(slots.visible_times(self.d, long, self.tue)), 8)

    def test_hidden_time_cannot_be_booked(self):
        p = make_patient(self.d)
        with self.assertRaises(ValidationError):
            services.book(p, self.type, at(self.d, self.tue, 9, 30))  # free but hidden by the visible-times limit
        services.book(p, self.type, at(self.d, self.tue, 9))

    def test_same_time_twice(self):
        p = make_patient(self.d)
        p2 = make_patient(self.d, email="joao@example.com")
        services.book(p, self.type, at(self.d, self.tue, 9))
        with self.assertRaises(ValidationError):
            services.book(p2, self.type, at(self.d, self.tue, 9))

    def test_visitor_request_holds_slot(self):
        services.request_booking(self.d, self.type, at(self.d, self.tue, 9), name="Visitante", email="v@example.com", consent=True)
        appt = Appointment.objects.get()
        self.assertEqual(appt.status, "PENDING")
        self.assertIsNotNone(appt.lead)
        self.assertNotIn("09:00", self.hm(slots.visible_times(self.d, self.type, self.tue)))

    def test_expiry_frees_slot(self):
        services.request_booking(self.d, self.type, at(self.d, self.tue, 9), name="V", email="v@example.com", consent=True)
        from django.utils import timezone

        n = services.expire_pending(now=timezone.now() + timedelta(hours=49))
        self.assertEqual(n, 1)
        self.assertEqual(Appointment.objects.get().status, "EXPIRED")

    def test_allocate(self):
        self.assertEqual(slots.allocate([8, 9], 4), [2, 2])
        self.assertEqual(slots.allocate([2, 0, 10], 4), [1, 0, 3])
        self.assertEqual(slots.allocate([1], 4), [1])
