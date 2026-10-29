# 05 — Agenda and booking

Code: `apps/agenda/` — `slots.py` (which times are free and which are shown), `services.py` (every state change),
`calendar_links.py` + `apps/core/ics.py` (calendar export), `feed.py` (subscription feed), `management/commands/agenda_tick.py`.

## 1. Free times (`slots.free_times(dentist, type, day)`)

For one dentist, one appointment type and one local date:

1. Take the day's `WorkingHours` ranges (local time, `dentist.timezone`).
2. Candidate starts every `slot_step_min` minutes inside each range, such that `start + duration_min + buffer_min <= range end`.
3. Drop a candidate if `[start, start + duration + buffer)` overlaps a `TimeBlock` or an appointment in `BLOCKING_STATUSES`
   (PENDING, CONFIRMED) — including that appointment's own type buffer.
4. Return the sorted list of aware datetimes.

`slots.bookable_window(dentist)` = from `now + min_lead_hours` to `today + booking_horizon_days`. Times outside it are never offered
to visitors or patients (the dentist ignores it).

## 2. Visible times (`slots.visible_times(dentist, type, day, viewer)`)

The limit hides most of an **empty** day so the agenda never looks empty.

- A day is **empty** when it has no appointment in `BLOCKING_STATUSES`.
- If `BookingSettings.limit_empty_days` is on and the day is empty, show at most `EMPTY_DAY_VISIBLE_SLOTS = 4` times
  (a module constant, not a setting), chosen by **spread**. Otherwise show all free times.
- `viewer` is `"public"` or `"patient"`: the limit applies to both. The dentist never goes through `visible_times`.

**Spread** (deterministic):
1. Work on the day's **full grid** — free times computed *without* the bookable window — so the chosen times do not shift during the day.
2. Split the grid by working range (e.g. morning, afternoon). Give each range `k` picks proportional to its number of times
   (largest remainder), with at least one per range while picks remain; total = min(4, grid size).
3. In a range with `n` times and `k` picks, take indexes `floor((2i + 1) · n / (2k))` for `i = 0 … k-1`.
4. Finally remove picks outside the bookable window (past or too soon). Do **not** replace them.

Example (`slot_step_min = 30`, 30-min type, Tuesday 08:00–12:00 and 13:30–18:00): the grid has 8 morning and 9 afternoon times
→ 2 + 2 picks → **09:00, 11:00, 14:30, 16:30**. When anyone books (or requests) any time that Tuesday, the day is no longer empty
and all its free times appear.

Tests (`tests/test_slots.py`): grid and overlap rules, buffers, blocks, the example above, stability (same output on repeated calls
and across the day), empty vs booked day, limit off, a hidden time POSTed by hand is refused, two concurrent bookings of the same
time → one wins.

## 3. Booking services (`apps/agenda/services.py`)

All run inside `transaction.atomic()`, lock the dentist row (`Dentist.objects.select_for_update().get(pk=...)`), re-check the time
against `visible_times` (patients/visitors) or `free_times` (dentist), save, `log_action`, then send e-mails with
`transaction.on_commit`.

| Service | Who | Result |
|---|---|---|
| `book(patient, type, start)` | patient (portal) | CONFIRMED if `patient_auto_confirm`, else PENDING. Refused if the patient already holds `max_active_per_patient` future appointments. |
| `request_booking(dentist, type, start, name, email, whatsapp, message, consent, ip)` | visitor | creates/updates **Lead** (source BOOKING, matched by e-mail within the dentist) + PENDING appointment holding the slot. One open request per e-mail per dentist. `visitor_bookable` types only. |
| `create_by_dentist(dentist, patient_or_lead, type, start, ...)` | dentist | CONFIRMED; any free time, no window. |
| `approve(appt)` | dentist | PENDING → CONFIRMED; lead → SCHEDULED. |
| `reject(appt, reason)` | dentist | PENDING → REJECTED; slot freed. |
| `expire_pending(now)` | `agenda_tick` | PENDING older than `pending_hold_hours` (or whose start has passed) → EXPIRED. |
| `reschedule(appt, new_start, by)` | patient (before cutoff) / dentist | new appointment with `rescheduled_from = appt`, same patient/lead/type/treatment; old → RESCHEDULED (no cancel e-mail). New status: CONFIRMED (or PENDING for a lead whose request was still PENDING). |
| `cancel(appt, by, note)` | patient/visitor (before cutoff) / dentist | → CANCELLED, `cancelled_by`, `cancelled_at`. |
| `request_late_cancel(appt, note)` | patient/visitor inside cutoff | sets `late_cancel_requested_at`, `late_cancel_note`; status unchanged; alert `alert_late_cancel`; returns the `wa.me` URL. |
| `keep(appt)` | dentist | clears the late-cancel flag. |
| `complete(appt)`, `no_show(appt)` | dentist, after start | → COMPLETED / NO_SHOW; COMPLETED adds a TreatmentEntry event when linked to a treatment. |

Every change of time or status: `ics_sequence += 1`.

## 4. Statuses

| Status | Set by | Next |
|---|---|---|
| PENDING | visitor request (or patient when auto-confirm is off) | CONFIRMED, REJECTED, EXPIRED, CANCELLED, RESCHEDULED |
| CONFIRMED | auto, or dentist approval | COMPLETED, NO_SHOW, CANCELLED, RESCHEDULED |
| RESCHEDULED | `reschedule()` | final (points forward through the new row's `rescheduled_from`) |
| CANCELLED / REJECTED / EXPIRED / COMPLETED / NO_SHOW | see services | final |

## 5. Cutoff and late cancellation

`appt.in_cutoff` = `appt.start - now < change_cutoff_hours`. Patients and visitors can reschedule or cancel online only when not in cutoff
(`change_cutoff_hours = 0` → always allowed until the start). The dentist can always act.

Inside the cutoff the appointment card shows `components/late_cancel_box.html`:
1. **Contact the clinic**: phone (`tel:`), WhatsApp, address + map, opening hours.
2. Textarea "Detalhes (opcional)" and button **Pedir cancelamento pelo WhatsApp**.
3. POST `.../cancelar-tarde/` → `request_late_cancel()` → e-mail to the dentist (`alert_late_cancel`) → `302` to
   `wa.me/<dentist.whatsapp>?text=<message>`:
   - pt-BR: `Olá, aqui é {nome}. Gostaria de cancelar minha consulta de {tipo} em {Terça-feira, 04/11/2026, às 14:00}. {detalhes}`
   - en: `Hello, this is {name}. I would like to cancel my {type} appointment on {Tuesday, 04/11/2026, at 14:00}. {details}`
   The message language follows the active language. If the dentist has no WhatsApp, the POST still alerts and shows the phone instead.
4. The dentist sees a red "cancelamento solicitado" flag in the agenda and dashboard, then **Cancelar** or **Manter**.

## 6. `agenda_tick` (scheduled task)

`python manage.py agenda_tick` — idempotent, safe to run hourly (paid account) or daily (free account):
1. `expire_pending(now)` → e-mails visitor (always) and dentist (`alert_request_expired`).
2. Reminders: CONFIRMED appointments with `now < start <= now + 24 h` and `reminder_sent_at` empty → e-mail to patient/visitor
   (dentist switch `patient_alert_reminder`, patient opt-out), then set `reminder_sent_at`. Visitors (leads) get reminders when the switch is on.
3. Operator alert `alert_dentist_expiring` for dentists whose `access_until` is in 3 days (once per day).
Each run writes one activity line with counts.

## 7. Calendar export (one way)

wbook is the source of truth; calendars only receive events.

### Per appointment — `calendar_links.links_for(appt)`
| Option | URL |
|---|---|
| Google | `https://calendar.google.com/calendar/render?action=TEMPLATE&text=…&dates=YYYYMMDDTHHMMSSZ/YYYYMMDDTHHMMSSZ&details=…&location=…` |
| Outlook.com | `https://outlook.live.com/calendar/0/deeplink/compose?path=/calendar/action/compose&rru=addevent&subject=…&startdt=ISO&enddt=ISO&body=…&location=…` |
| Microsoft 365 | same on `https://outlook.office.com/calendar/0/deeplink/compose?...` |
| Apple / others | `.ics` file (`/paciente/consultas/<pk>.ics`, `/<slug>/consulta/<uuid>.ics`), also attached to confirmation e-mails |
| WhatsApp | `https://wa.me/?text=<share text>` (section 8) |

Title: `{tipo} — {dentist.display_name}`; location: clinic address; details: clinic phone + link to the portal or status page. All values URL-encoded.

### `.ics` (`apps/core/ics.py`, hand-written, no dependency)
`VCALENDAR` (`PRODID:-//wbook//wbook.com.br//PT`, `VERSION:2.0`, `METHOD:PUBLISH`) with one `VEVENT`: `UID:<ics_uid>@wbook.com.br` where
`ics_uid` = `ref` of the **first** appointment in the reschedule chain (so a rescheduled appointment updates the same event),
`SEQUENCE:<ics_sequence>`, `DTSTAMP`, `DTSTART`/`DTEND` in UTC (`Z`), `SUMMARY`, `LOCATION`, `DESCRIPTION`, `URL`,
`STATUS:CONFIRMED|TENTATIVE|CANCELLED` (PENDING = TENTATIVE), and `VALARM` 2 h before (`TRIGGER:-PT2H`, `ACTION:DISPLAY`).
Cancellation e-mails attach the same event with `METHOD:CANCEL` and `STATUS:CANCELLED`. Lines folded at 75 octets, CRLF, text escaped (`\,` `\;` `\n`).

### Dentist
1. **Exportar agenda** (`agenda:export`): date range + statuses → one `.ics` (all events) or CSV.
2. **Sincronizar com meu calendário** (`agenda:sync`): private feed `https://www.wbook.com.br/calendario/<calendar_feed_token>.ics`
   with appointments from 30 days ago to `booking_horizon_days` ahead (PENDING as TENTATIVE, CANCELLED omitted). Buttons:
   - Google: `https://calendar.google.com/calendar/r?cid=<webcal URL, encoded>`
   - Outlook: `https://outlook.live.com/calendar/0/addfromweb?url=<https URL>&name=wbook – {clinic}`
   - Apple: `webcal://www.wbook.com.br/calendario/<token>.ics`
   - "Copiar link".
   Text on the page: Google refreshes subscribed calendars every few hours, so changes are not instant.
   `feed_detail`: FIRST_NAME (default: "Maria — Avaliação"), FULL_NAME, BUSY ("Ocupado"). **Gerar novo link** rotates the token
   (old URL → 404). The feed sends `Cache-Control: private, max-age=900` and is not logged per request (only token rotation is).

## 8. WhatsApp share and links

`apps/core/whatsapp.py`: `wa_link(number, text)` (E.164 digits, Brazil `55` added when missing) and `wa_share(text)` (`https://wa.me/?text=`).
WhatsApp has no public link that creates its own calendar event, so messages write the date in full — phones usually make it tappable to
add to the calendar — and end with the Google Calendar link:

```
Consulta confirmada: Avaliação com Dra. Ana Lima
Terça-feira, 04/11/2026, das 14:00 às 14:30
Rua das Flores, 123 – São Paulo
Adicionar à agenda: https://calendar.google.com/...
```

Used on: confirmation pages and e-mails (share), "Contact the clinic" (to the dentist's number), late cancellation, sending a quote,
inviting a patient. No WhatsApp API and no automatic WhatsApp reminders in the MVP.

## 9. Public booking page flow

`/<slug>/` → type dropdown (active, `visitor_bookable`; price shown only when `landing.show_prices` and `type.show_price`) →
week grid (HTMX `booking_public:times`) → pick a time → form (name, e-mail, WhatsApp, message, consent, honeypot) →
POST `booking_public:request` → thanks page with status link and Add to calendar (TENTATIVE). If `visitor_booking_enabled` is off or the
landing has `show_calendar` off, the page shows contact buttons only. A logged-in patient of this dentist who opens `/<slug>/` sees a banner
"Agendar pelo portal" linking to `patient:book` (auto-confirm path).
