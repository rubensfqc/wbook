# 02 — Data model

All primary keys are `BigAutoField`. Every exportable model has `ref = UUIDField(default=uuid4, unique=True, editable=False)`.
Files use `apps.core.storage.UploadTo(prefix)` → random names `prefix/YYYY/MM/<hex>.<ext>`.
Deleting a row, or replacing its file, deletes the stored file (`apps/core/signals.py`, list `FILE_FIELDS`). **Add new file fields to that list.**
Choices use `models.TextChoices` with pt-BR labels wrapped in `gettext_lazy`.

## accounts.User (AUTH_USER_MODEL)
`email` (unique, `USERNAME_FIELD`, lowercased), `username` (optional, generated from the e-mail when empty — login accepts either),
`name`, `phone`, `role` (DENTIST / PATIENT / OPERATOR), `language` (`pt-br` / `en`, default `pt-br`; set by the switcher when
logged in, used for e-mails). No `first_name`/`last_name`. `createsuperuser` creates an OPERATOR. Helpers: `is_dentist`, `is_patient`, `is_operator`.

## core.PlatformSettings (singleton)
`PlatformSettings.get_solo()`. As wiserarch: `default_trial_days`, `contact_email`, `contact_whatsapp`, `home_hero_image_url`,
`instagram_url`, `plan{1,2,3}_name/price/description/payment_link` (`.plans`).
Operator alerts: `alert_email` (primary; blank → `contact_email`), **`alert_email_secondary`** (optional; receives a copy of every
operator alert), switches `alert_platform_lead`, `alert_new_dentist`, `alert_dentist_expiring`, `alert_data_import` (all default True).
`alert_recipients` → list of 1–2 addresses. Edited at `/operador/configuracoes/`.

## clinic
| Model | Key fields / notes |
|---|---|
| `Dentist` | `user` 1:1 (`dentist_profile`), `clinic_name`, `display_name` ("Dra. Ana Lima"), `slug` (unique, `validate_public_slug`), `logo`, `photo`, `cro_number`, `cro_state` (UF), `specialties` (one per line), `phone`, `whatsapp`, `address`, `city`, `state`, `maps_url`, `opening_hours_text`, `timezone`, `pix_key`, `payment_link`, `payment_note`, `trial_start_date`, `trial_days`, `paid_until`, `plan_name`, `is_suspended`, `onboarding_done`, `calendar_feed_token` (UUID, regenerable), `feed_detail` (FIRST_NAME / FULL_NAME / BUSY, default FIRST_NAME). Alert checkboxes (dentist receives, all default True): `alert_new_request`, `alert_patient_booked`, `alert_patient_changed`, `alert_late_cancel`, `alert_request_expired`, `alert_patient_message`, `alert_quote_viewed`, `alert_quote_response`, `alert_invoice_paid`, `alert_new_lead`. Patient-facing switches: `patient_alert_reminder`, `patient_alert_treatment`, `patient_alert_invoice`. `ALERT_FIELDS` / `PATIENT_ALERT_FIELDS` list them. Read-only: `trial_ends_on`, `access_until`, `is_paying`, `days_remaining`, `can_access`, `contact_phone`. |
| `PatientProfile` | `user` 1:1 (`patient_profile`), `dentist` FK, `birth_date`, `cpf` (optional; shown masked), `whatsapp`, `notes` (internal, never shown to the patient), `invited_at`, `consent_at`, `consent_version`, `opt_out_reminders`, `opt_out_treatment_updates`. `has_joined` = usable password + has logged in. |
| `Treatment` | `dentist`, `patient`, `title`, `description`, `region` (free text, "36, 37"), `status` (PLANNED / IN_PROGRESS / ON_HOLD / COMPLETED / CANCELLED), `progress` (0–100), `estimated_sessions`, `budget`, `start_date`, `expected_end`, `is_visible_to_patient` (default True), `source_quote` (nullable FK). `sessions_done` = COMPLETED appointments. |
| `TreatmentFile` | `treatment`, `kind` (PDF / PHOTO), `file`, `thumb` (photos, 480 px JPEG), `phase` (BEFORE / DURING / AFTER, photos only), `taken_on`, `title`, `caption`, `region`, `shared` (default: True for PDF, False for PHOTO), `size`, `uploaded_by`. PDF validated by `validate_pdf`; photos by `apps.clinic.photos.process_upload` (HEIC/WEBP/PNG → JPEG, EXIF removed, orientation applied, max `MAX_PHOTO_MB`). Both `file` and `thumb` in `FILE_FIELDS`. |
| `TreatmentEntry` | `treatment`, `author`, `author_role`, `kind` (MSG / EVT), `text`. System events: session completed, file added/shared, status change, quote accepted. Replaces wiserarch `ProjectMessage`; no approval step. |
| `Invoice` | `dentist` (set from treatment), `treatment`, `number` (sequential **per dentist**, unique together, computed under `select_for_update`), `title`, `amount`, `notes`, `issued_date`, `due_date`, `status` OPEN / PAID / CANCELLED, `patient_notified_paid_at`, `paid_at`. `display_number` → `#0001`. |

Scoped managers: `for_dentist(d)` on PatientProfile, Treatment, TreatmentFile, TreatmentEntry, Invoice.
`for_patient(p)` on Treatment (only `is_visible_to_patient`), TreatmentFile (visible treatment **and** `shared`), TreatmentEntry, Invoice (not CANCELLED).

## agenda
| Model | Key fields / notes |
|---|---|
| `BookingSettings` | 1:1 Dentist (`dentist.booking`, created by `create_dentist`). `patient_auto_confirm` (True), `visitor_booking_enabled` (True), `change_cutoff_hours` (24; choices 0/12/24/48/72), `min_lead_hours` (2), `booking_horizon_days` (60), `slot_step_min` (15), `pending_hold_hours` (48), `max_active_per_patient` (2), `limit_empty_days` (True). |
| `WorkingHours` | `dentist`, `weekday` (0 = Monday … 6), `start`, `end` (local times). Several rows per day; validated non-overlapping. |
| `TimeBlock` | `dentist`, `start`, `end` (aware datetimes), `reason`, `all_day`. |
| `AppointmentType` | `dentist`, `name`, `description`, `duration_min`, `buffer_min` (default 0), `colour`, `price` (nullable), `show_price` (False), `visitor_bookable` (True), `is_active`, `order`. Seeded on `create_dentist`: Avaliação (30), Limpeza (45), Urgência (30). |
| `Appointment` | `dentist`, `patient` (nullable), `lead` (nullable), `type` (PROTECT), `treatment` (nullable), `start`, `end` (end = start + duration; buffer is checked in `slots.py`, not stored), `status`, `source` (PORTAL / PUBLIC / DENTIST), `public_token` (UUID, for `/<slug>/consulta/<uuid>/`), `patient_note`, `dentist_note`, `reject_reason`, `rescheduled_from` (self FK, nullable), `confirmed_at`, `cancelled_at`, `cancelled_by` (PATIENT / DENTIST / SYSTEM), `late_cancel_requested_at`, `late_cancel_note`, `reminder_sent_at`, `ics_sequence` (+1 on every change of time or status). Constraint: exactly one of `patient` / `lead`. Index (`dentist`, `start`). |

`Appointment.Status`: PENDING, CONFIRMED, REJECTED, EXPIRED, CANCELLED, RESCHEDULED, COMPLETED, NO_SHOW.
`BLOCKING_STATUSES = {PENDING, CONFIRMED}` — the only statuses that occupy time. Transitions in `05-agenda-and-booking.md`.

Scoped managers: `for_dentist(d)` on all agenda models; `for_patient(p)` on Appointment.
Helper properties: `person_name`, `person_email`, `person_whatsapp` (from patient or lead), `can_change_online` (status CONFIRMED/PENDING and
`start - now > change_cutoff_hours`), `in_cutoff`.

## landing
| Model | Notes |
|---|---|
| `LandingPage` | 1:1 Dentist (`dentist.landing`). `is_published`, `headline`, `subheadline`, `about`, `services` (one per line), `hero_image`, `accent` (named palette → `accent_hex`), `instagram`, `website`, `show_whatsapp_button`, `show_calendar` (True), `show_prices` (False), `insurance_note` (convênios), `thank_you_message`. `is_live` = published and dentist `can_access`. |
| `GalleryImage` | `landing`, `image`, `caption`, `order`. Clinic photos only (never patient photos). Max 12. |
| `Lead` | `dentist`, `name`, `email`, `whatsapp`, `message`, `consent`, `source` (BOOKING / LANDING / MANUAL), `status` (NEW / CONTACTED / SCHEDULED / QUOTE / WON / LOST), `notes`, `converted_patient` (nullable), `ip_hash`. |

## quotes — see `06-quotes-and-tracking.md`
`Quote` (dentist, optional `lead` / `patient` / `treatment`, `recipient_name`, `recipient_email`, `uuid`, title, intro, payment_terms,
timeline, valid_until, attachment PDF, status DRAFT / SENT / VIEWED / ACCEPTED / DECLINED, `is_active`, `sent_at`, `responded_at`,
`response_note`; `total` property); `QuoteItem` (quote, description, region, quantity, unit_amount, order; `amount` property);
`QuoteVisit` (quote, token, started_at, last_seen_at, duration_s, max_scroll_pct, device, browser, os, referrer, ip_hash, is_returning);
`QuoteEvent` (visit, kind pdf / download / whatsapp / accepted / declined, created_at; unique per visit+kind).

## website
`PlatformLead`: a dentist interested in wbook (`name`, `email`, `whatsapp`, `clinic_name`, `city`, `message`, `contacted`).

## Export keys
Users match by e-mail, quotes by `uuid`, visits by `token`, appointments by `ref` (and `public_token` is exported), everything else by `ref`.
See `10-data-export-import.md`.

## Migrations
`0001_initial` per app, generated locally from the final models of the first build. New migrations locally only.
