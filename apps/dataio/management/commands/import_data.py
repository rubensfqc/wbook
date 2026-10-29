from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from apps.core.activity import log_action
from apps.dataio.importer import run_import


class Command(BaseCommand):
    help = "Importa uma exportação do wbook (upsert, tudo ou nada; nunca apaga)."

    def add_arguments(self, parser):
        parser.add_argument("file")
        parser.add_argument("--dry-run", action="store_true")

    def handle(self, *args, **o):
        p = Path(o["file"]).expanduser()
        if not p.exists():
            raise CommandError(f"arquivo não encontrado: {p}")
        rep = run_import(p.read_bytes(), dry_run=o["dry_run"])
        for t, c in rep.counts.items():
            self.stdout.write(f"{t:20} criadas {c['created']:5}  atualizadas {c['updated']:5}")
        for w in rep.warnings[:50]:
            self.stdout.write(self.style.WARNING(w))
        for e in rep.errors[:200]:
            self.stdout.write(self.style.ERROR(e))
        if not rep.ok:
            raise CommandError(f"{len(rep.errors)} erro(s) — nada foi gravado.")
        log_action(None, "operator", "import_data %(f)s (%(m)s)", level=30, f=p.name, m="prévia" if o["dry_run"] else "gravado")
        self.stdout.write(self.style.SUCCESS("Prévia OK — nada foi gravado." if o["dry_run"] else "Importação concluída."))
