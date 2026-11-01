"""Login with e-mail or username, short dentist sign-up, and the activity/e-mail logging around them."""

import logging
from unittest import mock

from django.core import mail
from django.core.cache import cache
from django.test import TestCase, override_settings
from django.urls import reverse

from apps.accounts.models import User, unique_username
from apps.clinic.models import Dentist
from apps.clinic.services import create_dentist
from apps.core.emails import send_templated

from .helpers import make_dentist

PW = "Senha!2026x"


class LoginTests(TestCase):
    def setUp(self):
        self.dentist = make_dentist(email="Ana.Lima@Example.com")
        self.user = self.dentist.user
        self.user.username = "ana.lima"
        self.user.save()

    def _login(self, ident, pw=PW):
        return self.client.post(reverse("accounts:login"), {"username": ident, "password": pw})

    def test_login_with_email_any_case(self):
        self.assertEqual(self._login("ANA.LIMA@example.com").status_code, 302)

    def test_login_with_username_any_case_and_spaces(self):
        self.assertEqual(self._login("  Ana.Lima ").status_code, 302)

    def test_wrong_password_is_refused_and_logged(self):
        with self.assertLogs("wbook.activity", level="WARNING") as logs:
            resp = self._login("ana.lima", "wrong-password")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("Login recusado para 'ana.lima'", logs.output[0])

    def test_successful_login_is_logged(self):
        with self.assertLogs("wbook.activity", level="INFO") as logs:
            self._login("ana.lima")
        self.assertTrue(any("| auth |" in line and "Login" in line for line in logs.output))


class UsernameTests(TestCase):
    def test_generated_usernames_are_valid_and_unique(self):
        a = User.objects.create_user(email="jo@example.com", password=PW)
        b = User.objects.create_user(email="jo@other.example.com", password=PW)
        self.assertEqual(a.username, "jo-")  # short local parts are padded to 3 characters
        self.assertNotEqual(a.username, b.username)
        for u in (a, b):
            u.full_clean()
        self.assertEqual(unique_username("Maria.Souza+teste@x.com"), "maria.souza-teste")


class RegisterTests(TestCase):
    url = "accounts:register"

    def setUp(self):
        cache.clear()  # sign-up is rate limited per IP (5/hour)

    def _data(self, **kw):
        data = {"name": "Dra. Ana Lima", "email": "ana@example.com", "whatsapp": "(11) 99999-8888",
                "password": PW, "accept": "on"}
        data.update(kw)
        return data

    def test_only_name_email_whatsapp_password_are_required(self):
        resp = self.client.post(reverse(self.url), self._data())
        self.assertRedirects(resp, reverse("accounts:verify_email_sent"))
        d = Dentist.objects.get(user__email="ana@example.com")
        self.assertEqual(d.user.name, "Dra. Ana Lima")
        self.assertEqual(d.whatsapp, "(11) 99999-8888")
        self.assertEqual(d.clinic_name, "Dra. Ana Lima")
        self.assertEqual(d.slug, "dra-ana-lima")
        self.assertFalse(d.user.is_active)
        self.assertEqual(d.cro_number, "")
        subjects = [m.subject for m in mail.outbox]
        self.assertTrue(any("Confirme" in s for s in subjects))
        self.assertTrue(any("Novo dentista" in s for s in subjects))

    def test_missing_whatsapp_or_short_number_rejected(self):
        resp = self.client.post(reverse(self.url), self._data(whatsapp=""))
        self.assertEqual(resp.status_code, 200)
        resp = self.client.post(reverse(self.url), self._data(whatsapp="9999"))
        self.assertContains(resp, "DDD")
        self.assertFalse(Dentist.objects.exists())

    def test_optional_username_is_used_for_login(self):
        self.client.post(reverse(self.url), self._data(username="Dra.Ana"))
        user = User.objects.get(email="ana@example.com")
        self.assertEqual(user.username, "dra.ana")
        user.is_active = True
        user.save()
        resp = self.client.post(reverse("accounts:login"), {"username": "dra.ana", "password": PW})
        self.assertEqual(resp.status_code, 302)

    def test_invalid_or_taken_username_rejected(self):
        User.objects.create_user(email="x@example.com", username="taken", password=PW)
        for bad in ("a b", "ab", "taken", "TAKEN"):
            resp = self.client.post(reverse(self.url), self._data(username=bad))
            self.assertEqual(resp.status_code, 200, bad)
        self.assertFalse(Dentist.objects.exists())

    def test_honeypot_creates_nothing(self):
        resp = self.client.post(reverse(self.url), self._data(website="spam"))
        self.assertRedirects(resp, reverse("accounts:verify_email_sent"))
        self.assertFalse(User.objects.filter(email="ana@example.com").exists())

    def test_same_name_gets_unique_page_address(self):
        create_dentist(email="other@example.com", name="Dra. Ana Lima")
        self.client.post(reverse(self.url), self._data())
        self.assertEqual(Dentist.objects.get(user__email="ana@example.com").slug, "dra-ana-lima-2")

    def test_reserved_or_short_names_get_a_valid_address(self):
        self.assertEqual(create_dentist(email="a@example.com", name="Admin").slug, "admin-dentista")
        self.assertEqual(create_dentist(email="b@example.com", name="Jo").slug, "jo-dentista")


class EmailFailureTests(TestCase):
    @override_settings(EMAIL_BACKEND="django.core.mail.backends.smtp.EmailBackend")
    def test_failure_is_logged_not_raised(self):
        with mock.patch("django.core.mail.message.EmailMessage.send", side_effect=OSError("smtp down")), \
                self.assertLogs("wbook.activity", level=logging.WARNING) as logs, \
                self.assertLogs("wbook", level="ERROR"):
            ok = send_templated("x@example.com", "Teste", "lead_confirmation", {})
        self.assertFalse(ok)
        self.assertIn("| email |", logs.output[0])
        self.assertIn("smtp down", logs.output[0])
