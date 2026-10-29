# 10 — Data export / import

Two audiences: the **dentist** downloads his own data (spreadsheets, calendar, clinic backup), and the **operator** backs up and restores the
whole platform or single dentists. Every export and import is written to the activity log (`export` category; WARNING for patient data and imports).

## Dentist exports (`/app/exportar/`, `apps/clinic/views_export.py`)
| Export | URL | Format | Columns / contents |
|---|---|---|---|
| Patients | `exportar/pacientes.csv` / `.xlsx` | CSV, Excel | nome, e-mail, telefone, WhatsApp, data de nascimento, CPF (masked unless "incluir CPF completo" is ticked), entrou no portal (sim/não), convidado em, primeira consulta, última consulta, próxima consulta, tratamentos ativos, faturas em aberto (R$) |
| Appointments | `exportar/consultas.csv` / `.xlsx`, `agenda/exportar/?formato=ics` | CSV, Excel, .ics | data, início, fim, tipo, paciente/lead, status, origem, tratamento, observações; filters: period + statuses |
| Leads | `exportar/leads.csv` (= `leads/exportar.csv`) | CSV | as wiserarch + source, status |
| Invoices | `exportar/faturas.csv` / `.xlsx` | CSV, Excel | número, paciente, tratamento, título, valor, emissão, vencimento, status, pago em |
| Quotes | `exportar/orcamentos.csv` / `.xlsx` | CSV, Excel | título, destinatário, total, status, enviado em, visitas, tempo de leitura, respondido em |
| My clinic (backup) | `exportar/backup.zip` (POST) | ZIP | the operator export (below) with `--dentist <own slug>`, files included, **no password hashes**; the operator can restore it |

- CSV: UTF-8 **with BOM**, `;` separator (Excel pt-BR opens it directly), dates `dd/mm/aaaa`, money `1.234,56`. Headers follow the active language.
- Excel: `openpyxl`, one sheet, bold header row, frozen first row, column widths set, dates as real dates, money with `R$ #.##0,00` format.
- Large exports stream (`StreamingHttpResponse` for CSV); Excel is built in memory (fine for a single clinic).

## Operator backup / restore
Code: `apps/dataio/` (`spec.py`, `codec.py`, `exporter.py`, `importer.py`, commands `export_data` / `import_data`) — **the wiserarch engine,
unchanged**, with `manifest.format = "wbook-export"`. UI: `/operador/dados/` (operators only).

### Formats (both round-trip)
| Format | Contents | Good for |
|---|---|---|
| **ZIP** (default) | `manifest.json`, one `<table>.csv` per table (UTF-8 with BOM), `files/<storage path>` (PDFs, photos, logos, images; optional), `LEIA-ME.txt` | full backups, server moves, restoring one dentist, bulk edits in Excel/LibreOffice |
| **TOML** | one file: `[manifest]` + `[[table]]` arrays; files referenced by path only | reading/diffing by hand, small edits, version control |

### Tables, in import order (`spec.TABLES`)
platform_settings*, users, dentists, booking_settings, working_hours, time_blocks, appointment_types, landing_pages, gallery_images,
patients, leads, treatments, treatment_files, treatment_entries, appointments, invoices, quotes, quote_items, quote_visits, quote_events,
platform_leads*. (* = only in "Tudo" exports.) Operator/staff accounts are never exported.
`appointments` comes after `treatments` and `leads` and references itself (`rescheduled_from`): the importer does a second pass for self-FKs.

### Keys and relations
- Stable keys: `users.email`, `quotes.uuid`, `quote_visits.token`, `platform_settings.id` (=1), everything else `ref`.
- FK columns hold the key of the referenced row (`appointments.patient` = patient `ref`, `dentists.user` = e-mail…), never database ids.
- Import = **upsert**: existing key → update, new key → create, empty `ref` → create with a new ref. **Nothing is deleted.** Re-import is idempotent.
- `auto_now` timestamps are restored from the file. Invoice numbers, `public_token`, `calendar_feed_token` and `ics_sequence` are kept as-is
  (so links, feeds and calendar events keep working after a restore).

### Import pipeline (as wiserarch)
1. `read_bundle()` sniffs ZIP vs TOML, checks `manifest.format == "wbook-export"` and version, rejects unsafe ZIP paths and > 2 GB uncompressed.
2. One `transaction.atomic()`; per row: parse (`codec.from_raw` accepts ISO and pt-BR styles `1.234,56`, `05/03/2026`, `sim/não`),
   resolve FKs (file first, then DB), table rules, `full_clean()`, save in a savepoint.
3. Any error → rollback of everything + report (`tabela · linha N (chave): motivo`). `--dry-run` / UI preview always rolls back, writes no files.
4. Files written only on a real run and only when the path is not stored yet; deleted again if the import fails. File-cleanup signals are
   suspended during imports.
5. On success: `notify_operator("alert_data_import", ...)`.

### Safety rules (importer `_rules`)
- Users: role DENTIST or PATIENT only, `is_staff/is_superuser` forced False; operator/staff e-mails can't be touched. `password` must be a
  Django hash; plain text rejected; new users without a hash get an unusable password (warning → "Esqueci minha senha").
- Dentist user role DENTIST, patient user role PATIENT, one profile per user. Slugs through `validate_public_slug` + uniqueness.
- Cross-tenant links rejected: an appointment's patient/lead/type/treatment, a treatment's patient, a quote's lead/patient/treatment, an invoice's
  treatment, a lead's converted_patient must all belong to the same dentist. Appointment must have exactly one of patient/lead.

### UI flow
Export form (format, all vs selected dentists, include files, include password hashes) → download.
Import: upload → **preview** (counts per table, errors, warnings) → file kept in `var/imports/<token>.bin` → "Confirmar e gravar" → result
report. "Cancelar" deletes the pending file.

### Restore one dentist
On the source: `export_data --dentist clinica-sorriso -o sorriso.zip` (or the dentist's own "backup" ZIP, or the UI with one dentist ticked).
On the target: `import_data sorriso.zip --dry-run` → `import_data sorriso.zip`. Patients keep their logins when hashes were included; otherwise
they use "Esqueci minha senha".

### CLI
```bash
python manage.py export_data -o backup.zip                          # everything
python manage.py export_data --format toml -o dados.toml
python manage.py export_data --dentist clinica-sorriso --no-passwords -o sorriso.zip
python manage.py import_data backup.zip --dry-run
python manage.py import_data backup.zip
```

## Adding a model to the export
1. `ref = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)` (part of `0001_initial` for the first build).
2. Add a `Table(...)` to `spec.TABLES` after the tables it references (`fks={"field": "table"}`, `files=(...)`, `self_fks=(...)`).
3. Scoped queryset in `exporter._querysets()`; cross-tenant rule in `importer._rules()`.
4. Extend `tests/test_dataio.py` (round trip must stay green).

## Demo seed
- Content: `apps/dataio/seed_data.py` (plain data; dates as day offsets from today, times as local wall-clock). Builder: `apps/dataio/seed.py`
  (`Seeder`), command `seed_demo` (DEBUG only unless `--allow-non-debug`).
- Three clinics: `clinica-sorriso` (Dra. Ana Lima, paying, limit on), `odonto-ipe` (Dr. Paulo Reis, trial, limit off),
  `sorria-mais` (expired → landing offline). Each with working hours, types, ~8 patients, 2 leads, appointments in every status over
  the past 30 and next 21 days (some PENDING, one late-cancel flag), 2–3 treatments with PDFs and generated illustration photos per phase
  (Pillow drawings — **never real patient photos**), invoices, and quotes with visits. Operators: `carla@wbook.example`, `rui@wbook.example`.
- Keys are deterministic (`seed.R("appointment", "sorriso", "maria-1")` = uuid5), so re-running the seed or importing `seed/demo_seed.zip`
  never duplicates rows (`tests/test_seed.py`).
- `seed/demo_seed.zip|toml` are exports of a fresh seed with password `Demo!2026x`; `seed/README.md` lists every login. Regenerate after a
  model change (commands in `seed/README.md`); `tests/test_seed.py::ShippedSeedFileTests` fails if they no longer import.
