from django.core.files.base import ContentFile
from django.test import TestCase
from django.urls import reverse

from apps.agenda.models import Appointment
from apps.clinic.models import Invoice, Treatment, TreatmentFile
from apps.quotes.models import Quote

from .helpers import make_dentist, make_patient


class IsolationTests(TestCase):
    def setUp(self):
        self.a = make_dentist("clinica-a")
        self.b = make_dentist("clinica-b")
        self.pa = make_patient(self.a, "pa@example.com")
        self.pb = make_patient(self.b, "pb@example.com")
        self.tb = Treatment.objects.create(dentist=self.b, patient=self.pb, title="B")
        self.fb = TreatmentFile(treatment=self.tb, kind="PHOTO", shared=True)
        self.fb.file.save("x.jpg", ContentFile(b"jpg"), save=False)
        self.fb.save()
        self.ib = Invoice.objects.create(treatment=self.tb, dentist=self.b, title="x", amount=10)
        self.qb = Quote.objects.create(dentist=self.b, recipient_name="x", title="q")
        self.client.login(username="clinica-a@example.com", password="Senha!2026x")

    def test_other_dentist_objects_404(self):
        for url in [reverse("clinic:treatment_detail", args=[self.tb.pk]), reverse("clinic:patient_detail", args=[self.pb.pk]),
                    reverse("clinic:invoice_detail", args=[self.ib.pk]), reverse("quotes:detail", args=[self.qb.pk]),
                    reverse("files:photo", args=[self.fb.pk]), reverse("files:invoice", args=[self.ib.pk])]:
            self.assertEqual(self.client.get(url).status_code, 404, url)

    def test_cannot_attach_other_patient_by_posting(self):
        r = self.client.post(reverse("clinic:treatment_create"), {"patient": self.pb.pk, "title": "hack", "status": "PLANNED",
                                                                   "progress": 0, "is_visible_to_patient": "on"})
        self.assertEqual(r.status_code, 200)
        self.assertFalse(Treatment.objects.filter(title="hack").exists())

    def test_roles(self):
        self.assertEqual(self.client.get(reverse("operator:dashboard")).status_code, 403)
        self.client.login(username="pa@example.com", password="Senha!2026x")
        self.assertEqual(self.client.get(reverse("clinic:dashboard")).status_code, 403)

    def test_patient_cannot_see_unshared_or_hidden(self):
        t = Treatment.objects.create(dentist=self.a, patient=self.pa, title="A")
        hidden = TreatmentFile(treatment=t, kind="PHOTO", shared=False)
        hidden.file.save("y.jpg", ContentFile(b"jpg"), save=False)
        hidden.save()
        self.client.login(username="pa@example.com", password="Senha!2026x")
        self.assertEqual(self.client.get(reverse("files:photo", args=[hidden.pk])).status_code, 404)
        hidden.shared = True
        hidden.save()
        self.assertEqual(self.client.get(reverse("files:photo", args=[hidden.pk])).status_code, 200)
        t.is_visible_to_patient = False
        t.save()
        self.assertEqual(self.client.get(reverse("files:photo", args=[hidden.pk])).status_code, 404)
        self.assertEqual(self.client.get(reverse("patient:treatment", args=[t.pk])).status_code, 404)

    def test_patient_cannot_touch_other_patients_appointment(self):
        t = self.b.appointment_types.first()
        from django.utils import timezone

        ab = Appointment.objects.create(dentist=self.b, patient=self.pb, type=t, start=timezone.now(), end=timezone.now(),
                                        status="CONFIRMED")
        self.client.login(username="pa@example.com", password="Senha!2026x")
        self.assertEqual(self.client.post(reverse("patient:appointment_cancel", args=[ab.pk])).status_code, 404)

    def test_patient_must_consent_first(self):
        from apps.clinic.services import invite_patient

        p = invite_patient(self.a, name="Novo", email="novo@example.com", send=False)
        p.user.set_password("Senha!2026x")
        p.user.save()
        self.client.login(username="novo@example.com", password="Senha!2026x")
        self.assertRedirects(self.client.get(reverse("patient:dashboard")), reverse("accounts:consent"))

    def test_branded_login_rejects_other_clinic(self):
        self.client.logout()
        r = self.client.post(reverse("landing_public:login", args=["clinica-a"]), {"username": "pb@example.com", "password": "Senha!2026x"})
        self.assertEqual(r.status_code, 200)
        self.assertNotIn("_auth_user_id", self.client.session)


class OperatorTests(TestCase):
    def test_operator_deletes_dentist_with_everything(self):
        from apps.accounts.models import User
        from apps.agenda import services
        from apps.clinic.models import Dentist

        from .helpers import at, next_weekday

        d = make_dentist("apagar")
        d.booking.max_visible_slots = 0
        d.booking.save()
        p = make_patient(d, "p@example.com")
        services.book(p, d.appointment_types.first(), at(d, next_weekday(1), 9))
        services.request_booking(d, d.appointment_types.first(), at(d, next_weekday(1), 11), name="V", email="v@example.com",
                                 consent=True)
        User.objects.create_superuser(email="op@example.com", password="Senha!2026x")
        self.client.login(username="op@example.com", password="Senha!2026x")
        self.client.post(reverse("operator:dentist_delete", args=[d.pk]), {"confirm": "apagar"})
        self.assertFalse(Dentist.objects.filter(slug="apagar").exists())
        self.assertFalse(User.objects.filter(email="p@example.com").exists())
        self.assertFalse(Appointment.objects.exists())

    def test_activity_page(self):
        from apps.accounts.models import User

        User.objects.create_superuser(email="op@example.com", password="Senha!2026x")
        self.client.login(username="op@example.com", password="Senha!2026x")
        self.assertEqual(self.client.get(reverse("operator:activity")).status_code, 200)
        self.assertEqual(self.client.get(reverse("operator:settings")).status_code, 200)
