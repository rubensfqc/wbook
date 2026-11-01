# 07 — Integrations

## Storage and files
- As wiserarch: `USE_S3=False` → `FileSystemStorage` in `media/` (served by Django only when DEBUG); `USE_S3=True` → private S3
  (`AWS_DEFAULT_ACL=None`, `AWS_QUERYSTRING_AUTH=True`, 1 h signed URLs for public images only).
- Private files never use `.url`: PDFs (`TreatmentFile` kind PDF, quote attachments) **and clinical photos** (`TreatmentFile` kind PHOTO,
  both `file` and `thumb`). `apps.core.files.stream_file(request, fieldfile, filename, content_type, inline)` handles `Range`
  (single, suffix, 416), with S3 ranged `get_object` or local seek+read.
- Read bytes server-side with `field.open("rb")` (S3 files have no `.path`).
- Validation: `validate_pdf` (extension + `%PDF-` magic + `MAX_UPLOAD_MB`), `validate_image` (5 MB, public images),
  `apps.clinic.photos.process_upload(uploaded)` for clinical photos: opens JPEG/PNG/WEBP/HEIC (`pillow_heif.register_heif_opener()`),
  applies EXIF orientation (`ImageOps.exif_transpose`), **drops all EXIF** (GPS, device), converts to RGB JPEG quality 85, max side 3000 px,
  makes a 480 px thumbnail, rejects > `MAX_PHOTO_MB`. Multi-upload loops over `request.FILES.getlist("files")`; one bad file doesn't stop the others.
- Cleanup on delete/replace: `apps/core/signals.py` (`FILE_FIELDS`).
- PythonAnywhere static mappings expose only public image folders (`media/logos/`, `media/dentists/`, `media/landing/`); never
  `media/treatments/` or `media/quotes/` (see 08).

## E-mail
`apps.core.emails.send_templated(to, subject, template, ctx, reply_to=None, attachments=None, language=None)` renders
`templates/emails/<template>.html` (extends `emails/base.html`) inside `translation.override(language or recipient.language)`, builds the
text part with links kept, sends from `DEFAULT_FROM_EMAIL`, logs failures instead of raising — to the server log **and** to the activity log
(`email` category, WARNING) so the operator sees them at `/operador/atividade/`. 500 errors are e-mailed to `ADMINS` (`mail_admins`
handler on `django.request`, only with DEBUG=False). `attachments` = list of
`(filename, bytes, mimetype)` — used for `.ics` files. Gmail SMTP with an app password (`wbook@gmail.com`). With DEBUG, the clean `link` is
logged as `[DEV] link do e-mail …` (the console backend breaks long links).

## Alerts (checkboxes)
E-mails that can be switched off go through `apps/core/notifications.py`, never `send_templated` directly:
- `notify_dentist(dentist, "alert_*", subject, template, ctx, ...)` — skipped when the dentist's checkbox is off.
- `notify_patient(dentist, recipient, "patient_alert_*", ...)` — skipped when the dentist's switch is off, the patient opted out
  (`opt_out_reminders` / `opt_out_treatment_updates`), the treatment is hidden, or the patient has no password yet (invite pending).
- `notify_operator("alert_*", ...)` — sent to `PlatformSettings.alert_email` (or `contact_email`) **and** `alert_email_secondary` when set.
Every alert sent or skipped-by-switch is written to the activity log (`alert` category).

| Trigger | Template | To | Checkbox |
|---|---|---|---|
| Register / resend | `verify_email` | dentist | always |
| Patient invite / reinvite | `patient_invite` | patient (reply-to dentist) | always |
| Operator creates dentist | `dentist_welcome_set_password` | dentist | always |
| Password reset | `password_reset.*` | user | always |
| Visitor request | `booking_request_dentist` (reply-to visitor) / `booking_request_received` | dentist / visitor | `alert_new_request` / always |
| Request approved / rejected / expired | `booking_confirmed` (+ .ics) / `booking_rejected` / `booking_expired` | visitor | always |
| Request expired | `booking_expired_dentist` | dentist | `alert_request_expired` |
| Patient books | `booking_confirmed` (+ .ics) / `booking_new_dentist` | patient / dentist | always / `alert_patient_booked` |
| Patient reschedules or cancels online | `booking_changed` (+ .ics) / `booking_changed_dentist` | patient / dentist | always / `alert_patient_changed` |
| Dentist creates, moves or cancels | `booking_changed` (+ .ics, METHOD:CANCEL on cancel) | patient / visitor | always |
| Late cancellation requested | `late_cancel_dentist` | dentist | `alert_late_cancel` |
| Reminder 24 h before | `booking_reminder` (+ .ics) | patient / visitor | `patient_alert_reminder` + opt-out |
| New treatment, shared file, dentist message | `patient_treatment_activity` | patient | `patient_alert_treatment` + opt-out |
| Patient message on a treatment | `dentist_treatment_message` | dentist | `alert_patient_message` |
| Invoice created (opt-in) / "enviar" | `invoice_new` | patient | `patient_alert_invoice` |
| Patient "Já paguei" | `invoice_patient_paid` | dentist | `alert_invoice_paid` |
| Landing contact without booking | `lead_new_dentist` / `lead_confirmation` | dentist / lead | `alert_new_lead` / always |
| Quote sent by e-mail | `quote_sent` | recipient | on "Enviar por e-mail" |
| First quote view | `quote_first_view` | dentist | `alert_quote_viewed` |
| Quote accepted / declined | `quote_response` | dentist | `alert_quote_response` |
| Marketing contact | `platform_lead` | operator | `alert_platform_lead` |
| Dentist self-registers | `operator_new_dentist` | operator | `alert_new_dentist` |
| Dentist access ends in 3 days | `operator_dentist_expiring` | operator | `alert_dentist_expiring` |
| Data import completed | `operator_data_import` | operator | `alert_data_import` |

Dentist checkboxes are edited in `/app/configuracoes/` (section "Alertas por e-mail": "Quero receber" and "Meus pacientes recebem");
operator checkboxes and the two addresses in `/operador/configuracoes/`.

## Activity log
As wiserarch: `apps.core.activity.log_action(request_or_user_or_None, "categoria", "Mensagem %(x)s", x=..., level=logging.INFO)` →
`wbook.activity` logger → `RotatingFileHandler` at `ACTIVITY_LOG_FILE` (default `var/logs/activity.log`, 5 MB × 5).
Line: `YYYY-MM-DD HH:MM:SS | LEVEL | categoria | email (ROLE) | mensagem`; values sanitised (no new lines or `|`).
Categories (`activity.CATEGORIES`): `auth`, `agenda`, `booking`, `patient`, `treatment`, `file`, `quote`, `invoice`, `lead`, `export`, `alert`,
`email`, `settings`, `operator`. Refused logins are logged (`auth`, WARNING) with the identifier typed. `log_action` never raises. WARNING for deletions, suspensions, late-cancel requests, patient-data exports, imports and failures.
Operator UI `/operador/atividade/` (current file + `.1`) with filters and raw download. Messages are pt-BR (log language, not UI language).

## LGPD and clinical data
- Clinical photos, X-rays and treatment notes are sensitive personal data (health, LGPD art. 11). Patients accept a specific consent on first
  login (`consent_at`, `consent_version` = `settings.CONSENT_VERSION`; bumping it asks again). Visitors tick consent on the request form.
- Files never public; photos hidden until shared; EXIF removed; IPs hashed with `IP_HASH_SALT`.
- Every view, upload, share toggle and delete of a clinical file is logged (`file` category, who, file id, treatment id).
- Patient data export: patient `meus-dados/` and dentist `pacientes/<pk>/dados.zip` → ZIP with a JSON/CSV of profile, appointments, treatments,
  entries, invoices and the shared (patient) or all (dentist) files.
- Deleting a patient: anonymises the user (name → "Paciente removido", e-mail → `removed-<ref>@invalid`, unusable password) and keeps treatment
  records, unless the dentist ticks "apagar também os registros clínicos" (WARNING log). Dental-record retention rules (CFO) → legal pages are
  templates marked "revise com um advogado".

## Login and tokens
As wiserarch: `EmailOrUsernameBackend` (e-mail or username, case-insensitive; the login field says "E-mail ou nome de usuário").
Dentist sign-up (`RegisterForm`) asks only **name, e-mail, WhatsApp, password** (+ optional username, terms, honeypot). `create_dentist()`
sets clinic name = name and generates the page address with `apps.core.slugs.unique_public_slug()`; CRO, clinic, address and logo are
completed later in `/app/configuracoes/` (first item of the onboarding checklist). E-mail verification GET shows a button, POST activates (security scanners open links with GET);
first password / reset via `default_token_generator` (`PASSWORD_RESET_TIMEOUT` 3 days); `InclusivePasswordResetForm` also reaches invited
patients without a password. Public tokens (`Appointment.public_token`, `Quote.uuid`, `Dentist.calendar_feed_token`) are UUID4.

## PDFs (ReportLab)
`apps/clinic/invoice_pdf.render_invoice_pdf(invoice, language)`: A4, header with the dentist's logo, CRO, patient, dates, treatment, item,
total, PIX/link/notes box, footer. Helvetica (no font file). Served by `files:invoice`, shown with the PDF.js component.

## i18n (pt-BR + English from day one)
- `LANGUAGE_CODE="pt-br"`, `LANGUAGES=[("pt-br","Português"),("en","English")]`, `LOCALE_PATHS=[BASE_DIR/"locale"]`.
- Middleware order: `SessionMiddleware` → `DefaultLanguageMiddleware` (sets the language cookie to `pt-br` on the first visit when none exists,
  so the browser's `Accept-Language` doesn't switch Brazilians to English) → `LocaleMiddleware` → `CommonMiddleware` …
- Switcher: `components/language_switcher.html` POSTs to `/idioma/`; `apps.core.views.set_language` wraps Django's view and saves
  `request.user.language` for e-mails. Logged-in users get their saved language on login (`user_logged_in` receiver in `accounts` — the
  one allowed non-file signal, UI only).
- **Source strings are pt-BR**; only `locale/en/LC_MESSAGES/django.po` exists. `python scripts/makemessages_py.py` extracts every
  `_()` / `gettext_lazy` / `{% translate %}` / `{% blocktranslate %}` string without GNU gettext (keeps existing translations; `--check`
  exits 1 if any is untranslated), and `python scripts/compile_messages.py` builds the `.mo`. Commit both files.
- E-mail templates use `{% translate %}`/`{% blocktranslate %}` like pages; dates via `|date` with the active language; money always `|brl`.
- `tests/test_i18n.py`: key pages and e-mails render in both languages with no untranslated pt-BR string in the English version for a
  checklist of strings, and the `.po` has no empty `msgstr` (fuzzy or missing translations fail CI).

## Payments
Not integrated. Plans link to external checkout URLs; the operator clicks "Liberar 30/90/365 dias". Dentist→patient payments are informational
(PIX key/link on the invoice; the patient clicks "Já paguei", the dentist marks it paid).

## Rate limits
`apps.core.utils.rate_limited(request, key, limit, window_s)` on the local cache (per process). Register 5/h, resend verification 3/h,
password reset 5/h, visitor booking request 5/h per IP+dentist, landing contact 5/h, marketing contact 5/h, late-cancel 5/h per appointment.
