# 03 — URLs and permissions

Root: `config/urls.py`. Dentist public pages (`/<slug>/...`) are the **last** patterns.
Reserved slugs (`apps/core/slugs.RESERVED_SLUGS`) include at least: `app`, `paciente`, `operador`, `conta`, `arquivos`, `calendario`,
`idioma`, `planos`, `obrigado`, `termos`, `privacidade`, `admin`, `static`, `media`, `robots.txt`, `sitemap.xml`, `api`, `wbook`.

Guard legend: **D** = `@dentist_required` (sets `request.dentist`), **P** = `@patient_required` (sets `request.patient` and
`request.dentist`), **O** = `@operator_required`, **L** = `@login_required` plus scoping by role, **T** = public but authorized by an
unguessable token in the URL, **—** = public. Wrong role → 403. Not your object → 404.

URL segments are Portuguese in both languages (no `i18n_patterns`); only the page text changes with the language.

## Public
| URL | Name | Guard | Notes |
|---|---|---|---|
| `/` | `website:home` | — | marketing home for dentists, contact form (POST `website:contact` → PlatformLead) |
| `/planos/`, `/obrigado/`, `/termos/`, `/privacidade/` | `website:*` | — | |
| `/idioma/` (POST) | `set_language` | — | Django view; also saves `User.language` when logged in (`apps.core.views.set_language`) |
| `/robots.txt`, `/sitemap.xml` | | — | sitemap lists live dentist pages |
| `/calendario/<token>.ics` | `agenda_feed:feed` | T | dentist subscription feed (`text/calendar`); unknown token → 404 |
| `/<slug>/` | `landing_public:page` | — | 404 unless `landing.is_live`; owner sees a preview banner |
| `/<slug>/horarios/?tipo=<id>&semana=<YYYY-MM-DD>` | `booking_public:times` | — | HTMX partial: visible free times for one week and type |
| `/<slug>/agendar/` (POST) | `booking_public:request` | — | visitor request → Lead + PENDING; honeypot `company`, consent, 5/h per IP+dentist; time re-checked against `visible_slots` |
| `/<slug>/agendar/obrigado/<uuid>/` | `booking_public:thanks` | T | "pedido enviado" + Add to calendar |
| `/<slug>/consulta/<uuid>/` | `booking_public:status` | T | request status, Add to calendar, cancel (before cutoff) or late-cancel box |
| `/<slug>/consulta/<uuid>/cancelar/`, `.../cancelar-tarde/` (POST) | `booking_public:cancel`, `:late_cancel` | T | |
| `/<slug>/consulta/<uuid>.ics` | `booking_public:ics` | T | |
| `/<slug>/contato/` (POST) | `landing_public:contact` | — | contact without booking → Lead (source LANDING) |
| `/<slug>/login/` | `landing_public:login` | — | branded login, only for that dentist or their patients |
| `/<slug>/orcamento/<uuid>/` | `quote_public:page` | T | DRAFT → 404 (except owner), inactive → 410 with contact buttons |
| `.../pdf/` | `quote_public:pdf` | T | Range streaming of the attachment |
| `.../beacon/`, `.../evento/` (POST, csrf-exempt) | | T | authorized by the visit token |
| `.../responder/` (POST) | `quote_public:respond` | T | accept / decline |

## Accounts (`/conta/`)
As wiserarch: `accounts:home` (role router), `login`, `logout` (POST), `register` (dentists only), `verify_email_sent`,
`resend_verification` (POST), `verify_email/<uidb64>/<token>` (GET = confirm button, POST = activate),
`set_password/<uidb64>/<token>` (invites + resets; logs in after), `password_reset`, `password_reset_done`, `change_password` (L).
First patient login after the invite shows the LGPD consent page (`accounts:consent`) until accepted.

## Dentist portal (`/app/`, guard D)
| URL | Name |
|---|---|
| `` | `clinic:dashboard` (today's agenda, pending requests, late-cancel flags, new leads, quote activity, open invoices, onboarding checklist) |
| `comecar/` | `clinic:onboarding` |
| `configuracoes/` | `clinic:settings` (profile, payment data, **alert checkboxes**; reachable while expired) |
| `configuracoes/agenda/` | `agenda:settings` (working hours formset, appointment types formset, BookingSettings incl. `limit_empty_days`) |
| `assinatura/` | `clinic:expired` (no guard; reachable while expired) |
| `agenda/?vista=semana\|dia&data=YYYY-MM-DD` | `agenda:calendar` |
| `agenda/nova/[?inicio=&paciente=&tratamento=]` | `agenda:create` (dentist may book any free time, ignoring the visible-slot limit and lead time) |
| `agenda/<pk>/` | `agenda:detail` |
| `agenda/<pk>/<aprovar\|recusar\|cancelar\|manter\|concluir\|faltou>/` (POST) | `agenda:approve`, `:reject`, `:cancel`, `:keep` (clears late-cancel flag), `:complete`, `:no_show` |
| `agenda/<pk>/remarcar/` (GET slot picker, POST) | `agenda:reschedule` |
| `agenda/bloqueios/`, `.../novo/`, `.../<pk>/remover/` (POST) | `agenda:blocks*` |
| `agenda/exportar/?de=&ate=&formato=ics\|csv&status=` | `agenda:export` |
| `agenda/sincronizar/`, `agenda/sincronizar/novo-link/` (POST) | `agenda:sync`, `agenda:sync_rotate` |
| `pacientes/`, `pacientes/convidar/[?lead=]`, `pacientes/<pk>/`, `.../editar/`, `.../remover/`, `.../reenviar-convite/` (POST), `.../dados.zip` | `clinic:patient_*` (`dados.zip` = LGPD export of one patient) |
| `tratamentos/`, `tratamentos/novo/[?paciente=\|?orcamento=]`, `tratamentos/<pk>/`, `.../editar/`, `.../status/` (POST), `.../mensagem/` (POST), `.../arquivos/enviar/` (POST, multi-file), `.../fase/<fase>/compartilhar/` (POST), `.../remover/` | `clinic:treatment_*` |
| `arquivos/<pk>/compartilhar/` (POST, HTMX toggle), `arquivos/<pk>/remover/` (POST) | `clinic:file_share`, `clinic:file_delete` |
| `tratamentos/<pk>/faturas/nova/`, `faturas/`, `faturas/<pk>/`, `faturas/<pk>/<pago\|cancelar\|reabrir\|enviar>/` (POST) | `clinic:invoice_*` |
| `leads/`, `leads/novo/`, `leads/exportar.csv`, `leads/<pk>/` (HTMX-aware), `leads/<pk>/remover/` | `landing:lead_*` |
| `leads/minha-pagina/`, `.../galeria/` (POST), `.../galeria/<pk>/remover/` (POST) | `landing:editor`, `landing:gallery_*` |
| `orcamentos/`, `orcamentos/novo/[?lead=\|?paciente=\|?tratamento=]`, `orcamentos/<pk>/` (access log), `.../editar/`, `.../enviar/` (POST, `email=1`), `.../link/` (POST toggle), `.../duplicar/` (POST), `.../tratamento/` (POST: create treatment), `.../remover/` | `quotes:*` |
| `exportar/` | `clinic:exports` (page with all buttons) |
| `exportar/pacientes.<csv\|xlsx>`, `exportar/consultas.<csv\|xlsx>`, `exportar/leads.csv`, `exportar/faturas.<csv\|xlsx>`, `exportar/orcamentos.<csv\|xlsx>` | `clinic:export_*` |
| `exportar/backup.zip` (POST) | `clinic:export_backup` (dataio export scoped to this dentist, with files) |

## Patient portal (`/paciente/`, guard P)
| URL | Name |
|---|---|
| `` | `patient:dashboard` (next appointment + actions, treatments with progress, open invoices) |
| `agendar/`, `agendar/horarios/` (HTMX), `agendar/confirmar/` (POST) | `patient:book*` (type dropdown → week → time → confirm) |
| `consultas/` | `patient:appointments` (upcoming + history, Add to calendar on each) |
| `consultas/<pk>/remarcar/` (GET/POST), `consultas/<pk>/cancelar/` (POST) | refused inside the cutoff (message + contacts) |
| `consultas/<pk>/cancelar-tarde/` (POST) | `patient:late_cancel` → alert + 302 to `wa.me` |
| `consultas/<pk>.ics`, `consultas.ics` | single event / all upcoming bookings |
| `tratamentos/<pk>/`, `tratamentos/<pk>/mensagem/` (POST) | sessions, timeline, shared files, before/after gallery |
| `faturas/<pk>/`, `faturas/<pk>/ja-paguei/` (POST) | |
| `meus-dados/` (GET page, POST → ZIP) | LGPD export of own data |
| `configuracoes/` | language, opt-out of reminders / treatment updates, change password |

## Files (`/arquivos/`, guard L)
`files:document/<pk>/` (PDF, Range, `?download=1`), `files:photo/<pk>/[?thumb=1]` (JPEG, `Cache-Control: private, max-age=300`),
`files:invoice/<pk>/` (ReportLab PDF generated on the fly), `files:quote_attachment/<pk>/` (owner only).
Access: the owning dentist, or the patient of a visible treatment with `shared` on. Every hit on a clinical file is logged (`file` category).

## Operator (`/operador/`, guard O)
`operator:dashboard`, `dentist_list` (filters `q`, `situacao`, `plano`, `ordem`, `pagina`), `dentist_add` (sends set-password e-mail),
`dentist_edit`, `dentist_extend` (POST days → `paid_until`), `dentist_suspend` (POST toggle), `dentist_delete` (type the slug to confirm;
removes patient logins too), `platform_leads`, `settings` (alert checkboxes, `alert_email`, `alert_email_secondary`, plans, home page),
`activity` (`atividade/`, filters `q`, `categoria`, `quem`, `periodo`, `dia`, `nivel`), `activity_download`, `data` (`dados/`),
`data_import` (POST → preview), `data_import_confirm` (POST), `data_import_cancel` (POST). Django admin at `ADMIN_URL`.

## Conventions for new views
```python
@dentist_required
def thing_detail(request, pk):
    thing = get_object_or_404(Thing.objects.for_dentist(request.dentist), pk=pk)
    ...
```
State changes: guard + `@require_POST`, `log_action(...)`, redirect after POST, `messages.success(...)`.
Token pages (T): look up by token **and** slug (`Appointment.objects.get(public_token=..., dentist__slug=slug)`), 404 otherwise.
