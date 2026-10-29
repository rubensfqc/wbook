from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from apps.clinic.models import Dentist
from apps.core.activity import log_action
from apps.dataio.exporter import export_bundle


class Command(BaseCommand):
    help = "Exporta os dados do wbook (ZIP de CSVs + arquivos, ou TOML)."

    def add_arguments(self, parser):
        parser.add_argument("-o", "--output", required=True)
        parser.add_argument("--format", choices=["zip", "toml"], default="zip")
        parser.add_argument("--dentist", action="append", help="slug (pode repetir). Sem isso: tudo.")
        parser.add_argument("--no-files", action="store_true")
        parser.add_argument("--no-passwords", action="store_true")

    def handle(self, *args, **o):
        dentists = None
        if o["dentist"]:
            dentists = list(Dentist.objects.filter(slug__in=o["dentist"]))
            missing = set(o["dentist"]) - {d.slug for d in dentists}
            if missing:
                raise CommandError(f"dentista não encontrado: {', '.join(sorted(missing))}")
        data = export_bundle(fmt=o["format"], dentists=dentists, include_files=not o["no_files"],
                             include_passwords=not o["no_passwords"], include_platform=dentists is None)
        out = Path(o["output"]).expanduser()
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(data)
        log_action(None, "export", "export_data → %(f)s (%(n)s bytes)", f=out.name, n=len(data))
        self.stdout.write(self.style.SUCCESS(f"{out} ({len(data):,} bytes)"))
