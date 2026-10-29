from pathlib import Path

from django.test import TestCase

from apps.clinic.models import Dentist
from apps.dataio.importer import run_import

SEED = Path(__file__).resolve().parent.parent / "seed"


class ShippedSeedFileTests(TestCase):
    def test_zip_imports(self):
        rep = run_import((SEED / "demo_seed.zip").read_bytes(), dry_run=False)
        self.assertTrue(rep.ok, rep.errors[:5])
        self.assertEqual(Dentist.objects.count(), 3)

    def test_toml_preview(self):
        rep = run_import((SEED / "demo_seed.toml").read_bytes(), dry_run=True)
        self.assertTrue(rep.ok, rep.errors[:5])
