from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from apps.dataio.seed import Seeder


class Command(BaseCommand):
    help = "Cria dados de demonstração (3 clínicas, pacientes, agenda, tratamentos, orçamentos, 2 operadores)."

    def add_arguments(self, parser):
        parser.add_argument("--password", required=True)
        parser.add_argument("--allow-non-debug", action="store_true")
        parser.add_argument("--operators-only", action="store_true")

    def handle(self, *args, **o):
        if not settings.DEBUG and not o["allow_non_debug"]:
            raise CommandError("seed_demo só roda com DEBUG=True (ou use --allow-non-debug no ambiente de teste).")
        Seeder(o["password"], stdout=self.stdout).run(operators=True, clinics=not o["operators_only"])
        self.stdout.write(self.style.SUCCESS("Dados de demonstração prontos."))
