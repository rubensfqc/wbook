from datetime import timedelta
from unittest import mock

from django.core import mail
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.agenda import services
from apps.agenda.models import Appointment
from apps.landing.models import Lead

from .helpers import at, make_dentist, make_patient, next_weekday


class BookingFlowTests(TestCase):
    def setUp(self):
        self.d = make_dentist()
        self.d.booking.slot_step_min = 30
        self.d.booking.save()
        self.t = self.d.appointment_types.get(name="Avaliação")
        self.tue = next_weekday(1)
        self.p = make_patient(self.d)

    def test_patient_booking_auto_confirms_and_emails(self):
        with self.captureOnCommitCallbacks(execute=True):
            a = services.book(self.p, self.t, at(self.d, self.tue, 9))
        self.assertEqual(a.status, "CONFIRMED")
        to = sorted(m.to[0] for m in mail.outbox)
        self.assertEqual(to, sorted([self.p.email, self.d.user.email]))
        patient_mail = next(m for m in mail.outbox if m.to == [self.p.email])
        self.assertTrue(any(att[0] == "consulta.ics" for att in patient_mail.attachments))

    def test_auto_confirm_off_goes_pending(self):
        self.d.booking.patient_auto_confirm = False
        self.d.booking.save()
        a = services.book(self.p, self.t, at(self.d, self.tue, 9))
        self.assertEqual(a.status, "PENDING")

    def test_max_active_per_patient(self):
        self.d.booking.max_visible_slots = 0
        self.d.booking.save()
        services.book(self.p, self.t, at(self.d, self.tue, 9))
        services.book(self.p, self.t, at(self.d, self.tue, 10))
        with self.assertRaises(ValidationError):
            services.book(self.p, self.t, at(self.d, self.tue, 11))

    def test_visitor_request_creates_lead_and_approval(self):
        with self.captureOnCommitCallbacks(execute=True):
            a = services.request_booking(self.d, self.t, at(self.d, self.tue, 9), name="Vi", email="vi@example.com",
                                         consent=True)
        self.assertEqual(Lead.objects.get().source, "BOOKING")
        self.assertEqual(len(mail.outbox), 2)  # dentist alert + visitor confirmation
        mail.outbox.clear()
        with self.captureOnCommitCallbacks(execute=True):
            services.approve(a)
        a.refresh_from_db()
        self.assertEqual(a.status, "CONFIRMED")
        self.assertEqual(a.lead.status, "SCHEDULED")
        self.assertEqual(mail.outbox[0].to, ["vi@example.com"])
        self.assertEqual(a.ics_sequence, 1)

    def test_one_open_request_per_email(self):
        self.d.booking.max_visible_slots = 0
        self.d.booking.save()
        services.request_booking(self.d, self.t, at(self.d, self.tue, 9), name="Vi", email="vi@example.com", consent=True)
        with self.assertRaises(ValidationError):
            services.request_booking(self.d, self.t, at(self.d, self.tue, 10), name="Vi", email="vi@example.com", consent=True)

    def test_non_visitor_type_refused(self):
        retorno = self.d.appointment_types.get(name="Retorno")
        with self.assertRaises(ValidationError):
            services.request_booking(self.d, retorno, at(self.d, self.tue, 9), name="Vi", email="vi@example.com", consent=True)

    def test_reschedule_keeps_ics_uid_and_no_cancel_mail(self):
        a = services.book(self.p, self.t, at(self.d, self.tue, 9))
        mail.outbox.clear()
        with self.captureOnCommitCallbacks(execute=True):
            new = services.reschedule(a, at(self.d, self.tue, 11), by="PATIENT")
        a.refresh_from_db()
        self.assertEqual(a.status, "RESCHEDULED")
        self.assertEqual(new.rescheduled_from, a)
        self.assertEqual(new.ics_uid, a.ics_uid)
        self.assertGreater(new.ics_sequence, 0)
        subjects = " ".join(m.subject for m in mail.outbox)
        self.assertNotIn("cancelada", subjects)

    def test_cutoff_blocks_patient_but_not_dentist(self):
        self.d.booking.change_cutoff_hours = 48
        self.d.booking.min_lead_hours = 0
        self.d.booking.save()
        soon = timezone.now() + timedelta(hours=26)
        a = Appointment.objects.create(dentist=self.d, patient=self.p, type=self.t, start=soon, end=soon + timedelta(minutes=30),
                                       status="CONFIRMED")
        self.assertTrue(a.in_cutoff)
        with self.assertRaises(ValidationError):
            services.cancel(a, by="PATIENT")
        services.cancel(a, by="DENTIST")
        a.refresh_from_db()
        self.assertEqual(a.status, "CANCELLED")

    def test_late_cancel_request_alerts_and_returns_whatsapp(self):
        soon = timezone.now() + timedelta(hours=5)
        a = Appointment.objects.create(dentist=self.d, patient=self.p, type=self.t, start=soon, end=soon + timedelta(minutes=30),
                                       status="CONFIRMED")
        with self.captureOnCommitCallbacks(execute=True):
            url = services.request_late_cancel(a, note="Viagem")
        self.assertTrue(url.startswith("https://wa.me/5511999990000?text="))
        self.assertIn("Viagem", __import__("urllib.parse").parse.unquote(url))
        a.refresh_from_db()
        self.assertIsNotNone(a.late_cancel_requested_at)
        self.assertEqual(a.status, "CONFIRMED")
        self.assertEqual(mail.outbox[0].to, [self.d.user.email])

    def test_late_cancel_alert_switch_off(self):
        self.d.alert_late_cancel = False
        self.d.save()
        soon = timezone.now() + timedelta(hours=5)
        a = Appointment.objects.create(dentist=self.d, patient=self.p, type=self.t, start=soon, end=soon + timedelta(minutes=30),
                                       status="CONFIRMED")
        with self.captureOnCommitCallbacks(execute=True):
            services.request_late_cancel(a)
        self.assertEqual(len(mail.outbox), 0)

    def test_late_cancel_view_redirects_to_whatsapp(self):
        soon = timezone.now() + timedelta(hours=5)
        a = Appointment.objects.create(dentist=self.d, patient=self.p, type=self.t, start=soon, end=soon + timedelta(minutes=30),
                                       status="CONFIRMED")
        self.client.login(username=self.p.email, password="Senha!2026x")
        r = self.client.post(reverse("patient:late_cancel", args=[a.pk]), {"note": "x"})
        self.assertEqual(r.status_code, 302)
        self.assertTrue(r["Location"].startswith("https://wa.me/"))

    def test_patient_booking_view(self):
        self.client.login(username=self.p.email, password="Senha!2026x")
        r = self.client.post(reverse("patient:book_confirm"), {"type": self.t.pk, "start": at(self.d, self.tue, 9).isoformat()})
        self.assertEqual(r.status_code, 302)
        self.assertEqual(Appointment.objects.get().status, "CONFIRMED")

    def test_public_request_view_honeypot_and_real(self):
        url = reverse("booking_public:request", args=[self.d.slug])
        data = {"type": self.t.pk, "start": at(self.d, self.tue, 9).isoformat(), "name": "Vi", "email": "vi@example.com",
                "whatsapp": "11999", "consent": "on"}
        self.client.post(url, {**data, "company": "spam"})
        self.assertFalse(Appointment.objects.exists())
        r = self.client.post(url, data)
        a = Appointment.objects.get()
        self.assertRedirects(r, reverse("booking_public:thanks", args=[self.d.slug, a.public_token]), fetch_redirect_response=False)

    def test_agenda_tick_reminders_once(self):
        from django.core.management import call_command

        soon = timezone.now() + timedelta(hours=20)
        Appointment.objects.create(dentist=self.d, patient=self.p, type=self.t, start=soon, end=soon + timedelta(minutes=30),
                                   status="CONFIRMED")
        with mock.patch("sys.stdout"):
            call_command("agenda_tick")
            call_command("agenda_tick")
        reminders = [m for m in mail.outbox if m.to == [self.p.email]]
        self.assertEqual(len(reminders), 1)

    def test_reminder_respects_opt_out(self):
        from django.core.management import call_command

        self.p.opt_out_reminders = True
        self.p.save()
        soon = timezone.now() + timedelta(hours=20)
        Appointment.objects.create(dentist=self.d, patient=self.p, type=self.t, start=soon, end=soon + timedelta(minutes=30),
                                   status="CONFIRMED")
        with mock.patch("sys.stdout"):
            call_command("agenda_tick")
        self.assertEqual([m for m in mail.outbox if m.to == [self.p.email]], [])

    def test_english_patient_gets_english_email(self):
        self.p.user.language = "en"
        self.p.user.save()
        with self.captureOnCommitCallbacks(execute=True):
            services.book(self.p, self.t, at(self.d, self.tue, 9))
        m = next(m for m in mail.outbox if m.to == [self.p.email])
        self.assertIn("Appointment confirmed", m.subject)
        dm = next(m for m in mail.outbox if m.to == [self.d.user.email])
        self.assertIn("agendou", dm.subject)
