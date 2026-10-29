# Demo seed

Two ways to get the same demo data (keys are deterministic, so they never duplicate each other):

```bash
python manage.py seed_demo --password 'Demo!2026x'            # build it (DEBUG only; --allow-non-debug on test servers)
# or
python manage.py import_data seed/demo_seed.zip               # import the shipped export
python manage.py seed_demo --password 'Demo!2026x' --operators-only   # operators are never exported
```

Password for every login: `Demo!2026x`.

| Login | Role | Notes |
|---|---|---|
| `carla@wbook.example`, `rui@wbook.example` | operator | `/operador/` |
| `ana@sorriso.example` | dentist — Clínica Sorriso (`/clinica-sorriso/`) | paying, empty-day limit on, prices shown, 8 patients, 3 treatments with PDFs and illustration photos, 2 quotes (one with an access log), a late-cancel request, pending visitor requests |
| `paulo@odontoipe.example` | dentist — Odonto Ipê (`/odonto-ipe/`) | on trial, empty-day limit off |
| `lia@sorriamais.example` | dentist — Sorria Mais (`/sorria-mais/`) | expired → page offline, portal still works |
| `maria@paciente.example` | patient of Clínica Sorriso | aligners treatment, open invoice, late-cancel flag |
| `joao@paciente.example` … `thiago@paciente.example` | patients of Clínica Sorriso | |
| `anabeatriz@paciente.example`, `carlos@paciente.example`, … | patients of Odonto Ipê | |

Photos are Pillow drawings, never real patient photos. Appointment dates are relative to the day the seed runs.

Regenerate the shipped files after a model change:

```bash
rm db.sqlite3 && python manage.py migrate && python manage.py seed_demo --password 'Demo!2026x'
python manage.py export_data -o seed/demo_seed.zip
python manage.py export_data --format toml --no-files -o seed/demo_seed.toml
```
