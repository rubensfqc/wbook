# 04 — Frontend

## Build
- As wiserarch: Tailwind 3.4 + `@tailwindcss/forms`, compiled ahead of time. Source `static/src/app.css`, output `static/css/app.css`
  (**committed**, so the server needs no Node). `npm install` once, then `npm run build:css` (or `npm run watch:css`).
  `tailwind.config.js` scans `templates/**/*.html`, `apps/**/*.py`, `static/js/**/*.js`.
- Vendored in `static/vendor/` (`npm run vendor` → `scripts/vendor.js`): Chart.js 4.4, HTMX 2.0, with `sourceMappingURL` comments
  removed (the hashed static storage fails on missing `.map` files). No CDN JavaScript; only Google Fonts is external.
- PDFs use the browser's built-in viewer inside an `<iframe>` (`components/pdf_viewer.html`), not PDF.js.
- Static files use hashed names (`HashedStaticStorage`), so `collectstatic` is mandatory on deploy.

## Layouts (`templates/layouts/`)
| Layout | Used by | Look |
|---|---|---|
| `portal.html` | base for dentist + operator | dark sidebar, mobile drawer, page title/actions blocks, language switcher in the footer |
| `dentist.html` | `/app/` | `brand-800` sidebar, wbook logo, trial box, link to public page, red badge for pending requests + late-cancel flags |
| `operator.html` | `/operador/` | `brand-950` sidebar with light logo |
| `patient.html` | `/paciente/` | light top bar with the **dentist's** logo, WhatsApp + phone buttons, language switcher |
| `auth.html` | login, register, consent, onboarding, expired | light background, centred card |
| `public.html` | marketing site | wbook brand |
Dentist public pages (`landing/public.html`, `agenda/public_*.html`, `quotes/public.html`) extend `base.html` and set `--accent` from the landing accent.

Blocks: `title`, `page_title`, `page_subtitle`, `page_actions`, `breadcrumb`, `content`, `scripts`.
Every layout includes `components/language_switcher.html` (a POST form to `set_language` with `next` = current path; shows "PT | EN").

## Components (`templates/components/`)
`field.html`, `form_fields.html`, `guard.html`, `empty.html`, `messages.html`, `pdf_viewer.html` (`with url download_url title height track`), `logo.html`, `pagination.html`, `language_switcher.html`. New for wbook:
- `slot_picker.html` (`with dentist type week times`): week navigation (‹ ›), one column per day, time buttons; days without visible times are greyed;
  loaded by HTMX from `booking_public:times` / `patient:book_times`. Works without JS as a plain form with `?semana=`.
- `add_to_calendar.html` (`with links`): dropdown with Google, Outlook.com, Microsoft 365, Apple/.ics, WhatsApp. `links` comes from
  `apps.agenda.calendar_links.links_for(appointment, request)`.
- `contact_clinic.html` (`with dentist`): phone (`tel:`), WhatsApp, address + map link, opening hours.
- `late_cancel_box.html` (`with appointment action_url`): contact block + textarea "Detalhes (opcional)" + button "Pedir cancelamento pelo WhatsApp".
- `status_pill.html`: appointment / treatment / quote / invoice status → pill colour via `|pill`.
- `photo_gallery.html` (`with files phase_filter compare`): grid of thumbnails grouped by phase (Antes / Durante / Depois), lightbox,
  and a side-by-side compare (pick one BEFORE + one AFTER). Images load from `files:photo` (never `.url`).
- `photo_uploader.html`: drag-and-drop multi-file input with phase select and date; falls back to a plain multiple file input.
- `share_toggle.html`: HTMX button that flips `TreatmentFile.shared` and swaps itself (eye / eye-off icon).

## Agenda UI (dentist)
- Week view (default) and day view, 07:00–21:00 grid at `slot_step_min` rows, appointments as coloured blocks (type colour).
  PENDING = dashed border + amber; late-cancel requested = red left border + icon; time blocks = hatched grey.
- Click an empty cell → `agenda:create` prefilled. Click an appointment → side panel (HTMX) with actions.
- Header: "Exportar agenda", "Sincronizar com meu calendário", "Bloquear horário".
- Server-rendered from a dict built by `apps.agenda.views_dentist.calendar_context()`; no JS calendar library.

## CSS component classes (`static/src/app.css`)
As wiserarch: `btn-primary|secondary|ghost|danger|success|accent|outline-accent` (+`btn-sm`), `card*`, `label`, `input`, `select`, `checkbox`,
`file-input`, `help`, `field-error`, `table`, `pill-{gray,brand,amber,green,red,sky,violet}`, `kpi*`, `nav-link`, `nav-section`, `guard`, `empty`,
`breadcrumb`, `tabular`. New: `slot-btn` (+ `slot-btn-selected`), `cal-grid`, `cal-event`, `cal-event-pending`, `cal-event-late`, `cal-block`.
Wrap public forms in `.pub` for the accent form style. Forms get classes from `apps.core.forms.StyledFormMixin`.

## Template helpers (builtins, no `{% load %}`)
`{% icon "name" "h-4 w-4" %}`, `|brl` (R$ 1.234,56), `|wa_link:"texto"`, `|duration`, `|pill`, `|lines`, `|get_item`, `{% active "clinic:patient" %}`,
new: `|local_dt:dentist` (aware datetime → dentist timezone, formatted per active language), `|weekday_long`, `|mask_cpf`.
`i18n` and `static` are builtins too.

## JS (`static/js/`, no framework)
`app.js` as wiserarch (`data-toast`, `data-sidebar-toggle`, `data-copy`, `form[data-confirm]`, `[data-autosubmit]`, `[data-formset]`, password eye).
`booking.js`: selected-slot state, keeps the hidden `start` input in sync, disables submit until a time is chosen.
`gallery.js`: lightbox and compare slider. `quote-tracking.js`: beacons (see 06). HTMX loaded globally with the CSRF header.

## Charts
View passes a dict; template does `{{ d|json_script:"x" }}` and loads `vendor/chartjs/chart.umd.min.js` in `{% block scripts %}`.
Used for: quote visits per day, dashboard appointments per week (last 8 weeks), lead sources.

## Brand
- Name always lowercase **wbook**. Logo files in `static/img/brand/` (`logo-dark|light.svg`, `mark-*.svg`, `logo-email.png`), favicon set,
  `og-image.png`. Include with `{% include "components/logo.html" with variant="dark|light|mark-dark|mark-light" css="h-8 w-auto" %}`.
- Palette `brand-50…950` defined in `tailwind.config.js` (to be set from the wbook logo when it exists; until then a calm teal/blue health palette).
  Dentist pages use the dentist's accent.

## Forms: file inputs and passwords
`FORM_RENDERER = TemplatesSetting`. File inputs are native (`.file-input`), so the "Choose files" button follows the browser language —
override `templates/django/forms/widgets/` later if that matters. Every `input[type=password]` gets a show/hide button (`data-no-toggle` opts out).
