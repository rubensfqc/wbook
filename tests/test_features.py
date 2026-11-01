import json
from datetime import timedelta

from django.core import mail
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.agenda.models import Appointment
from apps.core import ics
from apps.quotes.models import Quote, QuoteItem, QuoteVisit

from .helpers import at, make_dentist, make_patient, next_weekday


class CalendarExportTests(TestCase):
    def setUp(self):
        self.d = make_dentist()
        self.p = make_patient(self.d)
        t = self.d.appointment_types.first()
        s = at(self.d, next_weekday(1), 9)
        self.a = Appointment.objects.create(dentist=self.d, patient=self.p, type=t, start=s, end=s + timedelta(minutes=30),
                                            status="CONFIRMED")

    def test_ics_format(self):
        from apps.agenda.calendar_links import ics_bytes, links_for

        body = ics_bytes(self.a).decode()
        self.assertIn("BEGIN:VCALENDAR", body)
        self.assertIn(f"UID:{self.a.ref}@wbook.com.br", body)
        self.assertIn("TRIGGER:-PT120M", body)
        self.assertTrue(all(len(line.encode()) <= 75 for line in body.split("\r\n")))
        links = links_for(self.a)
        self.assertTrue(links["google"].startswith("https://calendar.google.com/calendar/render?action=TEMPLATE"))
        self.assertIn("outlook.live.com", links["outlook"])
        self.assertTrue(links["whatsapp"].startswith("https://wa.me/?text="))

    def test_escape_and_fold(self):
        out = ics.calendar([{"uid": "x", "start": timezone.now(), "end": timezone.now(), "summary": "a,b;c\n" + "é" * 80}]).decode()
        self.assertIn("a\\,b\\;c\\n", out)

    def test_feed_and_rotation(self):
        url = reverse("agenda_feed:feed", args=[self.d.calendar_feed_token])
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        self.assertIn("Maria — ", r.content.decode())
        self.assertNotIn("Silva", r.content.decode())  # FIRST_NAME by default
        self.client.login(username=self.d.user.email, password="Senha!2026x")
        self.client.post(reverse("agenda:sync_rotate"))
        self.assertEqual(self.client.get(url).status_code, 404)

    def test_patient_ics(self):
        self.client.login(username=self.p.email, password="Senha!2026x")
        r = self.client.get(reverse("patient:appointment_ics", args=[self.a.pk]))
        self.assertEqual(r["Content-Type"], "text/calendar; charset=utf-8")


class QuoteTrackingTests(TestCase):
    def setUp(self):
        self.d = make_dentist()
        self.q = Quote.objects.create(dentist=self.d, recipient_name="Ana", recipient_email="ana@example.com", title="Implante",
                                      status="SENT")
        QuoteItem.objects.create(quote=self.q, description="Implante", quantity=1, unit_amount=1000)
        self.url = reverse("quote_public:page", args=[self.d.slug, self.q.uuid])

    def test_first_visit_marks_viewed_and_alerts_once(self):
        self.client.get(self.url)
        self.client.get(self.url)
        self.q.refresh_from_db()
        self.assertEqual(self.q.status, "VIEWED")
        self.assertEqual(QuoteVisit.objects.count(), 2)
        self.assertEqual(len(mail.outbox), 1)
        self.assertTrue(QuoteVisit.objects.order_by("started_at").last().is_returning)

    def test_bots_and_owner_not_logged(self):
        self.client.get(self.url, HTTP_USER_AGENT="WhatsApp/2.23")
        self.client.login(username=self.d.user.email, password="Senha!2026x")
        self.client.get(self.url)
        self.assertEqual(QuoteVisit.objects.count(), 0)

    def test_beacon_and_event(self):
        self.client.get(self.url)
        v = QuoteVisit.objects.get()
        b = reverse("quote_public:beacon", args=[self.d.slug, self.q.uuid])
        e = reverse("quote_public:event", args=[self.d.slug, self.q.uuid])
        self.client.post(b, json.dumps({"visit": str(v.token), "duration": 90, "scroll": 70}), content_type="text/plain")
        self.client.post(b, json.dumps({"visit": str(v.token), "duration": 30, "scroll": 20}), content_type="text/plain")
        self.client.post(e, json.dumps({"visit": str(v.token), "kind": "pdf"}), content_type="text/plain")
        self.client.post(e, json.dumps({"visit": str(v.token), "kind": "pdf"}), content_type="text/plain")
        v.refresh_from_db()
        self.assertEqual((v.duration_s, v.max_scroll_pct), (90, 70))
        self.assertEqual(v.events.count(), 1)

    def test_accept(self):
        self.client.post(reverse("quote_public:respond", args=[self.d.slug, self.q.uuid]), {"decision": "accept", "note": "ok"})
        self.q.refresh_from_db()
        self.assertEqual(self.q.status, "ACCEPTED")

    def test_draft_404_inactive_410(self):
        self.q.status = "DRAFT"
        self.q.save()
        self.assertEqual(self.client.get(self.url).status_code, 404)
        self.q.status, self.q.is_active = "SENT", False
        self.q.save()
        self.assertEqual(self.client.get(self.url).status_code, 410)


class ExportTests(TestCase):
    def setUp(self):
        self.d = make_dentist()
        make_patient(self.d)
        self.client.login(username=self.d.user.email, password="Senha!2026x")

    def test_patients_csv_and_xlsx(self):
        r = self.client.get(reverse("clinic:export", args=["pacientes", "csv"]))
        body = r.content.decode("utf-8")
        self.assertTrue(body.startswith("﻿"))
        self.assertIn("Maria Silva;maria@example.com", body)
        r = self.client.get(reverse("clinic:export", args=["pacientes", "xlsx"]))
        self.assertEqual(r.content[:2], b"PK")

    def test_backup_zip(self):
        r = self.client.post(reverse("clinic:export_backup"))
        self.assertEqual(r.content[:2], b"PK")


class AlertTests(TestCase):
    def test_operator_alert_goes_to_both_addresses(self):
        from apps.core.models import PlatformSettings
        from apps.core.notifications import notify_operator

        ps = PlatformSettings.get_solo()
        ps.alert_email, ps.alert_email_secondary = "op1@example.com", "op2@example.com"
        ps.save()
        notify_operator("alert_platform_lead", "x", "platform_lead", {"lead": None})
        self.assertEqual(mail.outbox[0].to, ["op1@example.com", "op2@example.com"])
        ps.alert_platform_lead = False
        ps.save()
        notify_operator("alert_platform_lead", "x", "platform_lead", {"lead": None})
        self.assertEqual(len(mail.outbox), 1)

    def test_dentist_switch(self):
        from apps.core.notifications import notify_dentist

        d = make_dentist()
        d.alert_new_lead = False
        d.save()
        notify_dentist(d, "alert_new_lead", "x", "lead_new_dentist", {"lead": None})
        self.assertEqual(len(mail.outbox), 0)


class I18nTests(TestCase):
    def test_po_complete(self):
        import subprocess
        import sys
        from pathlib import Path

        root = Path(__file__).resolve().parent.parent
        out = subprocess.run([sys.executable, str(root / "scripts" / "makemessages_py.py"), "--check"], capture_output=True,
                             text=True, encoding="utf-8", cwd=root)
        self.assertIn(" 0 untranslated", out.stdout, out.stderr)

    def test_pages_in_english(self):
        d = make_dentist()
        self.client.cookies["wbook_lang"] = "en"
        html = self.client.get(reverse("landing_public:page", args=[d.slug])).content.decode()
        self.assertIn("Book your appointment", html)
        self.assertIn('lang="en"', html)

    def test_default_portuguese(self):
        d = make_dentist()
        html = self.client.get(reverse("landing_public:page", args=[d.slug]), HTTP_ACCEPT_LANGUAGE="en-US").content.decode()
        self.assertIn("Agende sua consulta", html)

    def test_switcher_saves_user_language(self):
        d = make_dentist()
        self.client.login(username=d.user.email, password="Senha!2026x")
        self.client.post(reverse("set_language"), {"language": "en", "next": "/app/"})
        d.user.refresh_from_db()
        self.assertEqual(d.user.language, "en")
