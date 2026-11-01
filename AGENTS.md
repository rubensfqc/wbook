# AGENTS.md — wbook

> Entry point for AI coding agents. Read this file fully before changing code, then open the
> relevant file in `docs/ai/` for depth. wbook is a **from-scratch build** (Nov 2026) on the
> architecture of **wiserarch v2** (`C:\LocalData\wiserarch`). Where these docs say "as wiserarch",
> copy that project's code and conventions and rename *architect* → *dentist*, *client* → *patient*.
> The old wbook code (doctors, `spread_slots`, reschedule flow) is reference only — do not port it.

## 1. What this is

**wbook** (www.wbook.com.br) is a multi-tenant Django SaaS for **Brazilian dentists**. Dentists only:
all terms, fields and copy are dental (CRO, tooth/region, tratamento, orçamento).

1. **Capture**: a public landing page per dentist at `/<slug>/` with a calendar of free times.
   A visitor (no account) who books creates a **Lead** and a **PENDING** appointment that holds the slot
   for 48 h until the dentist approves or rejects it.
2. **Self-service booking**: a registered patient books in a free slot and is **CONFIRMED** at once.
   Patients reschedule/cancel online only until the dentist's cutoff (`change_cutoff_hours`); inside the
   cutoff they see the clinic contacts and a pre-filled WhatsApp message, and the dentist gets an alert.
3. **Quotes (orçamentos)**: a branded web page per quote at `/<slug>/orcamento/<uuid>/` with accept/decline
   and an access log (time on page, scroll, PDF opened) — the wiserarch proposal module, renamed.
4. **Delivery**: patients → treatments → sessions (appointments), PDF documents and clinical photos
   (before / during / after) → invoices (PDF, PIX), in a patient portal branded with the dentist's logo.
5. **Out**: dentist exports (patients CSV/Excel, agenda `.ics`, full clinic backup), calendar export and a
   live subscription feed, operator backup/restore (ZIP or TOML), operator activity log.

| Role | Who | Home |
|---|---|---|
| `DENTIST` | Paying customer (trial → plan). One dentist per clinic. | `/app/` |
| `PATIENT` | Invited by one dentist or converted from a lead. One dentist per patient. | `/paciente/` |
| `OPERATOR` | wbook staff (`createsuperuser`) | `/operador/` |

UI languages: **pt-BR (default and source language of all strings)** and **English**, switchable in every
layout from day one.

## 2. Stack

- Python 3.13, Django 6.0, python-decouple (`.env`), Pillow + pillow-heif, ReportLab, openpyxl,
  django-storages + boto3 (S3, optional, later).
- DB: **SQLite** in dev and on PythonAnywhere for the MVP (MySQL later, `DB_ENGINE=mysql`).
- Frontend: server-rendered templates. **Tailwind is compiled** to `static/css/app.css` (`npm run build:css`).
  Vendored in `static/vendor/` by `node scripts/vendor.js`: Chart.js 4.4, HTMX 2 (source-map comments stripped so `collectstatic`
  works). PDFs are shown with the browser's own viewer in an `<iframe>` (`components/pdf_viewer.html`). Fonts from Google Fonts.
  Icons via `{% icon "name" "classes" %}`. No CDN JavaScript.
- No background workers. E-mail is sent synchronously and failures are logged, never raised.
  Time-based jobs (24 h reminders, expiry of PENDING requests) run from one command, `agenda_tick`,
  called by a PythonAnywhere scheduled task.
- Do **not** use Python 3.14 locally (Django 5.x/6.0 template `Context.__copy__` breaks); use 3.13.

## 3. Golden rules

1. **Tenancy.** Every view touching tenant data uses a guard from `apps/core/permissions.py`
   (`@dentist_required`, `@patient_required`, `@operator_required`). Every lookup goes through scoped managers:
   `Model.objects.for_dentist(request.dentist)` / `.for_patient(request.patient)`. Ownership failure → **404**.
   FK choices in forms are scoped on GET **and** POST (`DentistScopedForm(dentist=...)`).
   `tests/test_isolation.py` must keep passing.
2. **Files are private.** Never render `.url` of a PDF **or of a clinical photo** (`TreatmentFile`, both `file`
   and `thumb`). Serve them through `/arquivos/...` views that authorize first, then call
   `apps.core.files.stream_file`. Only logos, the dentist photo, hero and gallery images may use `.url`.
   Every view/upload/share/delete of a clinical file is logged.
3. **Slots are computed in one place.** `apps/agenda/slots.py` is the only code that decides which times are
   free and which are visible. Views, the booking POST and the HTMX partial all call it. Never trust a time
   posted by the browser: re-check it against `visible_slots()` inside `transaction.atomic()` with
   `select_for_update()` on the dentist row.
4. **Migrations:** `makemigrations` **locally only**, commit them, run only `migrate` on the server.
   CI fails if `makemigrations --check` finds drift.
5. **No signals for business logic.** Use services: `apps.clinic.services.create_dentist()`, `invite_patient()`,
   `apps.agenda.services.book()`, `request_booking()`, `approve()`, `reject()`, `reschedule()`, `cancel()`,
   `request_late_cancel()`. The only signals are in `apps/core/signals.py` (delete stored files on row delete/replace) and the
   `user_logged_in` receiver in `apps/accounts` that activates the user's saved language.
6. **Subscription:** `Dentist.can_access` / `access_until` / `days_remaining` are read-only.
   `SubscriptionMiddleware` blocks only `/app/` (patients are never blocked). An expired dentist's landing
   page and booking go offline; quote links and the patient portal keep working.
7. **URLs:** dentist public pages are the **last** patterns in `config/urls.py`. A new top-level segment must go
   above them **and** into `apps/core/slugs.RESERVED_SLUGS`.
8. **E-mail:** every alert that can be switched off goes through `apps/core/notifications.py`
   (`notify_dentist` / `notify_patient` / `notify_operator`). Everything else uses
   `apps.core.emails.send_templated(to, subject, "template", ctx, attachments=...)`. Build absolute links with
   `absolute(reverse(...))` (uses `SITE_URL`). Never build links from the request `Host`. Render each e-mail in
   the recipient's `User.language`.
9. **Translations:** wrap every user-facing string (`gettext` / `{% translate %}`), source in pt-BR. Named
   placeholders only: `_("Olá, %(name)s") % {"name": n}` — never f-strings inside `_()`. Add the English
   translation to `locale/en/LC_MESSAGES/django.po` in the same change and compile it.
10. **Activity log:** every state-changing view calls `apps.core.activity.log_action(request, "categoria", "Mensagem %(x)s", x=...)`.
    WARNING for deletions, suspensions, late-cancel requests, patient-data exports and imports.
11. **WhatsApp:** only `wa.me` links built by `apps.core.whatsapp` helpers (`wa_link(number, text)`,
    `wa_share(text)`). Dates in messages are written out in full (`Terça-feira, 04/11/2026, das 14:00 às 14:30`).
12. **UI:** reuse component classes in `static/src/app.css` and includes in `templates/components/`.
    Run `npm run build:css` after adding Tailwind classes, and commit `static/css/app.css`.
13. **Copy/tone:** neutral, warm, professional health tone; no aggressive sales language; no clinical claims.
14. **Brand:** always lowercase **`wbook`** (never "WBook" or "Wbook") in copy, titles, e-mails and docs.
    Dentist pages keep the dentist's own logo and accent colour.

## 4. Commands

```bash
py -3.13 -m venv .venv && .venv\Scripts\activate     # Windows (source .venv/bin/activate on Linux)
pip install -r requirements-dev.txt
copy .env.example .env                               # then edit SECRET_KEY etc.
python manage.py migrate
python manage.py seed_demo --password 'Demo!2026x'   # DEBUG only: 3 clinics, patients, agenda, treatments, quotes
python manage.py runserver
python manage.py test                                # 83 tests; in-memory storage, locmem e-mail
python manage.py agenda_tick                         # reminders + expiry of PENDING requests (scheduled task)
python scripts/makemessages_py.py                    # extract strings → locale/en/.../django.po (no gettext needed)
python scripts/compile_messages.py                    # .po → .mo (commit both)
python manage.py export_data -o backup.zip           # full backup (import_data backup.zip [--dry-run] restores)
ruff check .
npm install && npm run build:css                     # only when templates/CSS changed
```

## 5. Where things are

```
config/            settings.py (env-driven), urls.py (ORDER MATTERS), wsgi.py
apps/core/         PlatformSettings, permissions, middleware (subscription, default language), files (Range streaming),
                   emails, notifications, activity, slugs, signals (file cleanup), whatsapp, ics, utils, templatetags/wb.py
apps/accounts/     User (login by e-mail or username, role, language), register/verify/login/branded login/set password/reset
apps/clinic/       Dentist, PatientProfile, Treatment, TreatmentFile, TreatmentEntry, Invoice
                   views_dentist.py (/app/), views_patient.py (/paciente/), views_files.py (/arquivos/),
                   views_export.py (/app/exportar/), invoice_pdf.py, photos.py (convert/strip EXIF/thumbs), services.py
apps/agenda/       BookingSettings, WorkingHours, TimeBlock, AppointmentType, Appointment
                   slots.py (free + visible times), services.py (book/approve/...), calendar_links.py, feed.py,
                   views_dentist.py (/app/agenda/), views_patient.py, views_public.py, management/commands/agenda_tick.py
apps/landing/      LandingPage, GalleryImage, Lead — public page /<slug>/ + /app/leads/ (pipeline, CSV, page editor)
apps/quotes/       Quote, QuoteItem, QuoteVisit, QuoteEvent — public page + beacons + access log (= wiserarch proposals)
apps/operator/     /operador/ (dentists, payments, suspend, platform leads, plans, settings, activity, data export/import)
apps/dataio/       export/import engine (ZIP of CSVs or TOML), demo seed, commands export_data / import_data / seed_demo
apps/website/      marketing home, /planos/, PlatformLead, robots.txt, sitemap.xml, terms/privacy
templates/         layouts/ (portal, dentist, patient, operator, auth, public), components/, emails/, per-app folders
locale/en/         English catalog (source strings are pt-BR)
static/            src/app.css → css/app.css (compiled, committed), js/app.js, js/booking.js, vendor/
tests/             isolation, slots, booking flows, cutoff/late cancel, ics/feed, quotes tracking, exports, dataio, i18n, alerts
```

## 6. Docs index (`docs/ai/`)

| File | Read when |
|---|---|
| `01-architecture.md` | Orientation: request flow, roles, tenancy, settings |
| `02-data-model.md` | Touching any model or migration |
| `03-urls-and-permissions.md` | Adding/changing pages and endpoints |
| `04-frontend.md` | Templates, CSS build, components, calendar UI, gallery, PDF viewer |
| `05-agenda-and-booking.md` | Slots, visible-slot limit, statuses, cutoff, late cancel, calendar export, WhatsApp |
| `06-quotes-and-tracking.md` | Orçamentos and the access log |
| `07-integrations.md` | E-mail and alerts, activity log, files/photos, i18n, tokens, PDFs, LGPD |
| `08-deployment.md` | PythonAnywhere (`plat4user`) setup and release procedure |
| `09-recipes.md` | Step-by-step recipes for common changes |
| `10-data-export-import.md` | Dentist exports, operator backup/restore, adding a model to the export, demo seed |

## 7. Build order (first implementation)

Build in this order; each step ends green (`check`, `ruff`, `test`) and committed.

1. **Skeleton from wiserarch v2**: config, `core`, `accounts`, `website`, `operator`, `dataio`, layouts, CSS build,
   CI. Rename roles and guards. Add `en` to `LANGUAGES`, `LocaleMiddleware`, `DefaultLanguageMiddleware`, switcher.
2. **clinic**: Dentist (registration, trial, onboarding, settings, alert checkboxes), PatientProfile + invites.
3. **agenda core**: WorkingHours, TimeBlock, AppointmentType, BookingSettings, `slots.py` with tests first
   (free slots, visible-slot limit, stability, double booking).
4. **Booking flows**: dentist agenda (week/day), patient booking, visitor request → Lead, approve/reject,
   expiry, reschedule, cancel, cutoff, late cancel, `agenda_tick`.
5. **landing**: public page with calendar (HTMX), gallery, prices toggle, lead pipeline.
6. **Treatments**: Treatment, files (PDF + photos, phases, share), timeline, gallery/compare.
7. **Invoices** (as wiserarch, on Treatment).
8. **Quotes** (port wiserarch proposals) + "create treatment from quote".
9. **Calendar out**: `.ics` per appointment, Add-to-calendar links, dentist export, subscription feed, WhatsApp share.
10. **Exports**: dentist exports (CSV/XLSX/backup ZIP), dataio tables for all new models, seed + `seed/` files.
11. **Operator**: dentists, settings (alerts + second e-mail), activity log, data page.
12. **i18n pass**: every string translated to English; `tests/test_i18n.py` renders key pages in both languages.

## 8. Definition of done

- Guard decorator on the view; scoped queryset on every lookup; a test that another tenant gets 404.
- POST for state changes (`@require_POST`), `{% csrf_token %}`, redirect after POST, `messages.success`.
- Strings wrapped for i18n **and translated in `locale/en`**; new e-mails via `send_templated` or `notify_*`
  (with a checkbox when the recipient can switch it off).
- `log_action` on every state change.
- Migration generated locally and committed; `python manage.py check`, `ruff check .` and `python manage.py test` pass.
- `npm run build:css` if you used new Tailwind classes.
- New model holding tenant data? Add it to the export (`docs/ai/10-data-export-import.md`), add demo rows to the seed,
  regenerate `seed/` files — `tests/test_seed.py` checks them.
