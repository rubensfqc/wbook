import io
import zipfile

from django.test import TestCase

from apps.agenda.models import Appointment
from apps.clinic.models import Dentist, PatientProfile, Treatment
from apps.dataio.exporter import export_bundle
from apps.dataio.importer import run_import
from apps.dataio.seed import Seeder


class DataioTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        Seeder("Demo!2026x").run()

    def test_zip_round_trip_is_idempotent(self):
        data = export_bundle(fmt="zip")
        zf = zipfile.ZipFile(io.BytesIO(data))
        self.assertIn("manifest.json", zf.namelist())
        self.assertTrue(any(n.startswith("files/") for n in zf.namelist()))
        rep = run_import(data, dry_run=False)
        self.assertTrue(rep.ok, rep.errors[:5])
        self.assertTrue(all(c["created"] == 0 for c in rep.counts.values()), rep.counts)

    def test_toml_round_trip(self):
        data = export_bundle(fmt="toml", include_files=False)
        rep = run_import(data, dry_run=True)
        self.assertTrue(rep.ok, rep.errors[:5])

    def test_restore_one_dentist_into_empty_db(self):
        d = Dentist.objects.get(slug="clinica-sorriso")
        data = export_bundle(fmt="zip", dentists=[d], include_platform=False)
        n_pat = PatientProfile.objects.filter(dentist=d).count()
        n_app = Appointment.objects.filter(dentist=d).count()
        token = d.calendar_feed_token
        # wipe that dentist entirely, then restore
        from apps.accounts.models import User

        User.objects.filter(patient_profile__dentist=d).delete()
        d.user.delete()
        rep = run_import(data, dry_run=False)
        self.assertTrue(rep.ok, rep.errors[:5])
        d2 = Dentist.objects.get(slug="clinica-sorriso")
        self.assertEqual(d2.calendar_feed_token, token)
        self.assertEqual(PatientProfile.objects.filter(dentist=d2).count(), n_pat)
        self.assertEqual(Appointment.objects.filter(dentist=d2).count(), n_app)
        self.assertTrue(Appointment.objects.filter(dentist=d2, rescheduled_from__isnull=False).exists())
        self.assertTrue(PatientProfile.objects.filter(dentist=d2).first().user.check_password("Demo!2026x"))

    def test_cross_tenant_rejected(self):
        import csv

        data = export_bundle(fmt="zip", include_files=False)
        zf = zipfile.ZipFile(io.BytesIO(data))
        rows = list(csv.DictReader(io.StringIO(zf.read("treatments.csv").decode("utf-8-sig"))))
        other = PatientProfile.objects.filter(dentist__slug="odonto-ipe").first()
        rows[0]["patient"] = str(other.ref)
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as out:
            for n in zf.namelist():
                if n == "treatments.csv":
                    s = io.StringIO()
                    w = csv.DictWriter(s, fieldnames=list(rows[0].keys()))
                    w.writeheader()
                    w.writerows(rows)
                    out.writestr(n, s.getvalue())
                else:
                    out.writestr(n, zf.read(n))
        title = rows[0]["title"]
        rep = run_import(buf.getvalue(), dry_run=False)
        self.assertFalse(rep.ok)
        self.assertTrue(any("outro dentista" in e for e in rep.errors), rep.errors[:3])
        self.assertEqual(Treatment.objects.get(title=title).patient.dentist.slug, "clinica-sorriso")

    def test_plain_password_rejected(self):
        import csv

        data = export_bundle(fmt="zip", include_files=False)
        zf = zipfile.ZipFile(io.BytesIO(data))
        rows = list(csv.DictReader(io.StringIO(zf.read("users.csv").decode("utf-8-sig"))))
        rows[0]["password"] = "secret"
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as out:
            for n in zf.namelist():
                if n == "users.csv":
                    s = io.StringIO()
                    w = csv.DictWriter(s, fieldnames=list(rows[0].keys()))
                    w.writeheader()
                    w.writerows(rows)
                    out.writestr(n, s.getvalue())
                else:
                    out.writestr(n, zf.read(n))
        rep = run_import(buf.getvalue(), dry_run=True)
        self.assertFalse(rep.ok)

    def test_seed_rerun_is_noop(self):
        before = Appointment.objects.count()
        Seeder("Demo!2026x").run()
        self.assertEqual(Appointment.objects.count(), before)
