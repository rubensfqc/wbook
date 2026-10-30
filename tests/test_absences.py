from datetime import timedelta

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse

from apps.agenda import services, slots
from apps.agenda.models import TimeBlock

from .helpers import at, make_dentist, make_patient, next_weekday


class AbsenceTests(TestCase):
    def setUp(self):
        self.d = make_dentist()
        self.type = self.d.appointment_types.get(name="Avaliação")
        self.tue = next_weekday(1)
        self.client.login(username=self.d.user.email, password="Senha!2026x")
        self.url = reverse("agenda:blocks")

    def post(self, **data):
        return self.client.post(self.url, data, follow=True)

    def test_whole_days_block_patients_visitors_and_dentist(self):
        wed = self.tue + timedelta(days=1)
        r = self.post(all_day="on", start_date=self.tue.isoformat(), end_date=wed.isoformat(), reason="Férias")
        self.assertEqual(r.status_code, 200)
        b = TimeBlock.objects.get()
        self.assertTrue(b.all_day)
        self.assertEqual(b.start, at(self.d, self.tue, 0))
        self.assertEqual(b.end, at(self.d, wed + timedelta(days=1), 0))
        self.assertEqual(slots.visible_times(self.d, self.type, self.tue), [])
        self.assertEqual(slots.visible_times(self.d, self.type, wed), [])
        self.assertTrue(slots.visible_times(self.d, self.type, wed + timedelta(days=1)))
        p = make_patient(self.d)
        with self.assertRaises(ValidationError):
            services.book(p, self.type, at(self.d, self.tue, 9))
        with self.assertRaises(ValidationError):
            services.create_by_dentist(self.d, self.type, at(self.d, wed, 9), patient=p)

    def test_hours_only(self):
        self.d.booking.max_visible_slots = 0
        self.d.booking.save()
        self.post(start_date=self.tue.isoformat(), end_date=self.tue.isoformat(), start_time="13:00", end_time="18:00")
        times = [f"{t.astimezone(self.d.tzinfo):%H:%M}" for t in slots.visible_times(self.d, self.type, self.tue)]
        self.assertTrue(times)
        self.assertTrue(all(t < "13:00" for t in times))

    def test_invalid_ranges(self):
        r = self.post(all_day="on", start_date=self.tue.isoformat(), end_date=(self.tue - timedelta(days=1)).isoformat())
        self.assertContains(r, "data final")
        r = self.post(start_date=self.tue.isoformat(), end_date=self.tue.isoformat())
        self.assertContains(r, "Dias inteiros")
        self.assertFalse(TimeBlock.objects.exists())

    def test_existing_appointments_are_listed_not_cancelled(self):
        p = make_patient(self.d)
        a = services.book(p, self.type, slots.visible_times(self.d, self.type, self.tue)[0])
        r = self.post(all_day="on", start_date=self.tue.isoformat(), end_date=self.tue.isoformat())
        self.assertContains(r, reverse("agenda:detail", args=[a.pk]))
        a.refresh_from_db()
        self.assertEqual(a.status, "CONFIRMED")

    def test_remove_frees_times(self):
        self.post(all_day="on", start_date=self.tue.isoformat(), end_date=self.tue.isoformat())
        b = TimeBlock.objects.get()
        self.client.post(reverse("agenda:block_delete", args=[b.pk]))
        self.assertFalse(TimeBlock.objects.exists())
        self.assertTrue(slots.visible_times(self.d, self.type, self.tue))

    def test_other_dentist_cannot_remove(self):
        other = make_dentist(slug="outra-clinica")
        b = TimeBlock.objects.create(dentist=other, start=at(other, self.tue, 9), end=at(other, self.tue, 10))
        r = self.client.post(reverse("agenda:block_delete", args=[b.pk]))
        self.assertEqual(r.status_code, 404)
        self.assertTrue(TimeBlock.objects.filter(pk=b.pk).exists())
