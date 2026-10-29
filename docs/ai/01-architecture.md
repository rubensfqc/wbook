# 01 — Architecture

## Picture

```
Visitor ──► /                          website   (marketing home for dentists, /planos/, contact form → PlatformLead)
Visitor ──► /<slug>/                   landing + agenda (dentist page, calendar of visible free times, booking request → Lead + PENDING)
Visitor ──► /<slug>/consulta/<uuid>/   agenda    (request status, Add to calendar, cancel / late-cancel box — token, no account)
Anyone ───► /<slug>/orcamento/<uuid>/  quotes    (web quote; visits + beacons → access log)
Calendar ─► /calendario/<token>.ics    agenda    (dentist's read-only subscription feed)
Dentist ──► /app/...                   clinic + agenda + landing + quotes (portal)
Patient ──► /paciente/...              clinic + agenda (patient portal, branded with the dentist's logo)
Operator ─► /operador/...              operator
Anyone ───► /conta/...                 accounts (login, register, verify, set password, reset)
Anyone ───► /idioma/                   Django set_language (pt-BR ↔ en)
Logged-in ► /arquivos/...              clinic.views_files (authorized file streaming: PDFs, photos, invoices, .ics)
```

One Django project with server-rendered templates. No REST API, no worker, no cache server (the local cache is used
only for rate limits). HTMX is used for partial updates (calendar week, lead follow-up, share toggles).

## Domain

```
User(role=DENTIST) 1─1 Dentist 1─1 LandingPage 1─N GalleryImage
                         │
                         ├─1─1 BookingSettings
                         ├─1─N WorkingHours, TimeBlock, AppointmentType
                         ├─1─N Lead ────────────────(converted_patient)──┐
                         ├─1─N PatientProfile 1─1 User(role=PATIENT) ◄───┘
                         │        └─1─N Treatment ─1─N TreatmentFile (PDF | photo)
                         │                   ├─1─N TreatmentEntry (timeline)
                         │                   └─1─N Invoice (number sequential per dentist)
                         ├─1─N Appointment (patient XOR lead; optional treatment; rescheduled_from → Appointment)
                         └─1─N Quote (optional lead | patient | treatment) ─1─N QuoteItem
                                    └─1─N QuoteVisit ─1─N QuoteEvent
User(role=OPERATOR) (no profile)     PlatformSettings (singleton)     PlatformLead
```

Business rules:
- **One dentist per clinic** (no Clinic model) and **one dentist per patient** (one e-mail = one account, so the same
  person cannot be a patient of two dentists).
- A treatment needs a patient; an invoice needs a treatment. Templates show the amber `guard` banner when a prerequisite is missing.
- `Treatment.is_visible_to_patient = False` hides the treatment and everything under it from the patient.
- Photos are hidden from the patient until shared (`TreatmentFile.shared`, default False for photos, True for PDFs).
- An appointment belongs to **either** a patient **or** a lead (DB check constraint).
- Lead pipeline: NEW → CONTACTED → SCHEDULED (its appointment confirmed) → QUOTE (linked quote sent) →
  WON (quote accepted or converted to patient) / LOST.
- Visitor requests hold their slot for `pending_hold_hours` (48 h); then `agenda_tick` sets EXPIRED.

## Request lifecycle (portal page)

1. `DefaultLanguageMiddleware` (sets the pt-BR cookie on first visit) → `LocaleMiddleware` → auth → `SubscriptionMiddleware`
   (redirects an expired dentist on `/app/` to `/app/assinatura/`).
2. The view guard (`@dentist_required`) checks the role (403 if wrong), attaches `request.dentist`, and redirects anonymous users to login.
   `@patient_required` attaches `request.patient` and `request.dentist` (the patient's dentist, for branding).
3. The view reads through scoped managers and renders a template that extends `layouts/dentist.html` / `layouts/patient.html`.
4. Charts: the view builds a dict, the template emits `{{ data|json_script:"id" }}`, Chart.js (vendored) reads it.

## Time

`USE_TZ = True`, `TIME_ZONE = "America/Sao_Paulo"`. Datetimes are stored in UTC. Each `Dentist.timezone` (default
`America/Sao_Paulo`) is activated in dentist and patient views and used by `slots.py`, e-mails, `.ics` and WhatsApp text.
`WorkingHours` are local wall-clock times of the dentist.

## Settings (all from `.env`, see `.env.example`)

| Setting | Notes |
|---|---|
| `DEBUG`, `SECRET_KEY`, `ALLOWED_HOSTS`, `CSRF_TRUSTED_ORIGINS` | standard |
| `SITE_URL` | absolute base for e-mail links, quote links, `.ics` UIDs, calendar feed (`https://www.wbook.com.br` in production) |
| `DB_ENGINE` | `sqlite` (default, MVP) or `mysql` (+ `DB_*`, utf8mb4, `CONN_MAX_AGE=280`) |
| `USE_S3` | False → `media/`; True → private S3 (`AWS_*`), signed URLs 1 h for public images only |
| `EMAIL_*`, `DEFAULT_FROM_EMAIL`, `PLATFORM_CONTACT_EMAIL`, `ADMINS` | console backend by default when DEBUG |
| `MAX_UPLOAD_MB` (PDF, default 20), `MAX_PHOTO_MB` (default 10) | upload limits |
| `IP_HASH_SALT` | salt for hashed IPs (LGPD) |
| `ADMIN_URL` | Django admin path (default `admin/`) |
| `ACTIVITY_LOG_FILE` | default `var/logs/activity.log` |
| production (DEBUG False) | `SECURE_PROXY_SSL_HEADER`, secure cookies, SSL redirect, optional HSTS |
| tests | in-memory storage, locmem e-mail, MD5 hasher (automatic under `manage.py test`) |

`LANGUAGE_CODE = "pt-br"`, `LANGUAGES = [("pt-br", "Português"), ("en", "English")]`, `LOCALE_PATHS = [BASE_DIR / "locale"]`.

## Not carried over from wiserarch

`ClientRequest` / `/procuro-arquiteto/` (people looking for a professional), Substack/Instagram feed on the marketing home
(optional later), `Contract` phases.
