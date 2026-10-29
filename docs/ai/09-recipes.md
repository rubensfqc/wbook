# 09 — Recipes

## Add a dentist-owned entity
1. Model with an FK to `Dentist` (directly or via `Treatment`), plural `related_name`, a `QuerySet` with `for_dentist()` (and `for_patient()` if
   patients see it), `objects = XQuerySet.as_manager()`, and `ref = UUIDField(...)`. File fields use `UploadTo("prefix")` and go into
   `apps/core/signals.FILE_FIELDS`.
2. `python manage.py makemigrations` (locally) and commit.
3. Form: subclass `DentistScopedForm`; restrict every FK queryset to `self.dentist` in `__init__`.
4. Views with `@dentist_required`, lookups via `X.objects.for_dentist(request.dentist)`, `@require_POST` for changes, `log_action`, `messages.success`.
5. URLs in the app's `urls_dentist.py`. Templates extend `layouts/dentist.html`, use `card`, `components/field.html`, `components/empty.html`,
   and `components/guard.html` if the entity depends on another.
6. Sidebar link in `templates/layouts/dentist.html` (`{% active "ns:prefix" %}`).
7. Admin registration. Isolation test in `tests/test_isolation.py`.
8. Export: `docs/ai/10-data-export-import.md` → "Adding a model to the export"; add seed rows.
9. Translate new strings in `locale/en`; `npm run build:css` if new Tailwind classes.

## Show a private file
`FileField` → authorized view with a scoped lookup → `stream_file(request, obj.file, "name.pdf", "application/pdf")` →
`{% include "components/pdf_viewer.html" with url=... download_url=... title=... %}`. For a photo: `stream_file(..., "image/jpeg")` and
`<img src="{% url 'files:photo' f.pk %}?thumb=1">`. Add a `log_action(request, "file", ...)`.

## Send a new e-mail
Create `templates/emails/<name>.html` extending `emails/base.html` (strings in `{% translate %}`). Can the recipient switch it off?
→ add a `BooleanField(default=True)` to `Dentist` (`alert_*` or `patient_alert_*`) or `PlatformSettings`, add it to `ALERT_FIELDS` /
`PATIENT_ALERT_FIELDS` / operator list (so it appears as a checkbox), and call `notify_dentist` / `notify_patient` / `notify_operator`.
Otherwise `send_templated(to, _("Assunto %(x)s") % {...}, "<name>", {"link": absolute(reverse(...))}, language=recipient.language)`.
Add the row to the table in `07-integrations.md`.

## Add a booking setting
Field on `BookingSettings` with a default → form in `agenda:settings` → use it **only** inside `slots.py` or `services.py` → test in
`tests/test_slots.py` or `tests/test_booking.py` → add to the table in `05-agenda-and-booking.md`.

## Add an appointment action
Service function in `apps/agenda/services.py` (atomic, dentist row locked, `ics_sequence += 1`, `log_action`, e-mail on commit) → POST view →
button in the agenda side panel → status table in `05` if it adds a transition.

## Add a field to the landing page
`LandingPage` → `LandingPageForm.Meta.fields` → section card in `templates/landing/editor.html` → `templates/landing/public.html` → migration.

## Track a new quote action
See `06-quotes-and-tracking.md` → Extending.

## Add a WhatsApp button
Build the text with `{% blocktranslate %}` or `_()` + named placeholders, write dates in full with `|local_dt:dentist`, then
`wa_link(number, text)` or `wa_share(text)`. Never hand-build `wa.me` URLs in templates.

## Add a top-level URL
Add it above the dentist patterns in `config/urls.py` and the segment to `RESERVED_SLUGS`. Check no existing dentist uses that slug.

## Add a translated string
Write it in pt-BR inside `_()` / `{% translate %}` → `python scripts/makemessages_py.py` → fill the empty `msgstr` in
`locale/en/LC_MESSAGES/django.po` → `python scripts/compile_messages.py` → commit `.po` and `.mo`. `tests/test_features.py::I18nTests` fails
while any string is untranslated.
