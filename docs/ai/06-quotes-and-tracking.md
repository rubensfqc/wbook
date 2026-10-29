# 06 — Quotes (orçamentos) and the access log

`apps/quotes/` is a port of wiserarch `apps/proposals` (models, public views, beacons, access log, templates), renamed:
Proposal → `Quote`, ProposalItem → `QuoteItem`, ProposalVisit → `QuoteVisit`, ProposalEvent → `QuoteEvent`, `/proposta/` → `/orcamento/`,
`/app/propostas/` → `/app/orcamentos/`. Copy the wiserarch code first, then apply the differences below.

## Differences from wiserarch
- A quote can link to a **lead**, a **patient** or a **treatment** (all optional, all scoped to the same dentist).
- `QuoteItem` has `region` (tooth/region) and `quantity` × `unit_amount`; total = sum.
- On ACCEPTED: **Cadastrar como paciente** (when linked to a lead without a patient → `invite_patient(lead=...)`) and
  **Criar tratamento a partir do orçamento** (`quotes:create_treatment`: title, items as description lines, total as `budget`,
  `source_quote` set; if the quote was linked to a treatment, offer "Atualizar orçamento do tratamento" instead). Optional first invoice.
- Lead status: sending a linked quote sets QUOTE; accepting sets WON.
- Patient portal: quotes sent to a patient are listed on the dashboard (open link in the same branded page).

## Lifecycle
1. Create in `/app/orcamentos/novo/` (pre-filled from `?lead=`, `?paciente=` or `?tratamento=`): title, intro, priced items (formset with live
   total), payment terms (e.g. "10× no cartão ou 5% de desconto no PIX"), timeline, `valid_until`, optional PDF. Status **DRAFT**: only the owner
   can open the link (preview banner).
2. **Enviar** (`quotes:send`): status SENT, `sent_at`; with `email=1` the recipient gets the link (`quote_sent`, reply-to dentist). Also a
   WhatsApp button (`wa_link(recipient whatsapp, text + link)` or `wa_share`) and copy-link.
3. The recipient opens `/<slug>/orcamento/<uuid>/` (dentist logo + accent). The first real visit sets VIEWED and alerts the dentist once
   (`alert_quote_viewed`: "Maria abriu seu orçamento").
4. **Aceitar / Recusar** with an optional comment until `valid_until` → ACCEPTED / DECLINED, `responded_at`, alert `alert_quote_response`.
   After `valid_until` the buttons are replaced by "Orçamento expirado — fale com a clínica" (contacts + WhatsApp).
5. The dentist can disable the link (`is_active=False` → 410 page with contact buttons), duplicate as a new draft, or delete.

## What is logged (one `QuoteVisit` per page load)
| Field | Source |
|---|---|
| `started_at` | server, on GET |
| `duration_s` | beacons: time the tab was **visible** (paused when hidden), capped at 4 h, only increases |
| `max_scroll_pct` | beacons: deepest scroll position (0–100) |
| `device`, `browser`, `os` | `apps.core.utils.describe_user_agent` |
| `is_returning` | same `ip_hash` already visited this quote |
| `ip_hash` | salted SHA-256 (`IP_HASH_SALT`); the raw IP is never stored (LGPD) |
| `referrer` | `Referer` header; page uses `Referrer-Policy: same-origin` (not `no-referrer`, which breaks the HTTPS CSRF check on accept/decline) |
| events | `pdf` (viewer scrolled into view), `download`, `whatsapp`, `accepted`, `declined` — one row per kind per visit |

**Not logged:** the owning dentist (preview banner instead) and link-preview bots (`apps.core.utils.is_bot`: WhatsApp, facebookexternalhit,
Slack, Telegram, Twitterbot, LinkedInBot, Googlebot…), so sharing the link on WhatsApp never counts as "opened".

## Beacon protocol (unchanged from wiserarch)
The page embeds the visit token (random UUID). `static/js/quote-tracking.js` sends `navigator.sendBeacon(url, Blob(JSON, text/plain))`, with
`fetch(..., {keepalive: true})` as fallback, on `visibilitychange→hidden`, on `pagehide`, and every 15 s while visible.
Payload `{"visit": token, "duration": s, "scroll": pct}` → `.../beacon/`. Events `{"visit": token, "kind": "pdf|download|whatsapp"}` → `.../evento/`.
Both endpoints are `@csrf_exempt` + `@require_POST`, always answer 204, and ignore tokens that don't belong to the quote in the URL.

## Dentist view (`/app/orcamentos/<id>/`)
KPIs: total visits / unique visitors, total and average reading time, max scroll, first access (and time since sending), last access.
Table: one row per visit (when, time on page, scroll bar, device/browser/OS, event pills, "retorno" flag). Chart: visits per day (14 days).
Dashboard card "Atividade nos orçamentos": latest visits across all quotes.

## Extending
- New tracked action: add a `QuoteEvent.Kind`, allow it in `views_public.event`, add `data-track="<kind>"` to the element.
- Public template: `templates/quotes/public.html`. Keep the tracking script at the bottom; render it only when `visit` exists.
