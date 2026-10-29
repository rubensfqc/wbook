# 08 — Deployment (PythonAnywhere)

PythonAnywhere account: **`plat4user`** (home `/home/plat4user`, login e-mail contact.plat4u@gmail.com). The account already runs the old
wiserarch.com app; wbook's two environments sit next to it, each with its own folder, virtualenv, `.env`, SQLite database and web app.

| | Test (`tst`) | Production (`prd`) |
|---|---|---|
| Code | `/home/plat4user/wbook_tst/wbook` | `/home/plat4user/wbook_prd/wbook` |
| Virtualenv | `/home/plat4user/.virtualenvs/wbook_tst` | `/home/plat4user/.virtualenvs/wbook_prd` |
| Address | `https://plat4user.pythonanywhere.com` | `https://www.wbook.com.br` (`wbook.com.br` → `www`) |
| Database (MVP) | SQLite: `db.sqlite3` in the code folder | SQLite: `db.sqlite3` in the code folder |
| Database later | MySQL `plat4user$wbook_tst` | MySQL `plat4user$wbook_prd` |
| Files (MVP) | local `media/` in the code folder | local `media/` in the code folder |
| E-mail sender | `wbook@gmail.com` (Gmail app password) | same, until a `wbook.com.br` mailbox exists |

**Web apps:** a free account has one web app. With old wiserarch.com plus wbook tst and prd, `plat4user` needs a paid plan with at least
three web apps (or run only prd until wiserarch.com moves). If `plat4user.pythonanywhere.com` is already used by another app, use the
next free address the Web tab offers for test and put it in the test `.env`.

Below, `<env>` means `tst` or `prd`.

## 1. Code and virtualenv
```bash
mkdir -p ~/wbook_<env> && cd ~/wbook_<env>
git clone https://github.com/rubensfqc/wbook.git wbook          # or: cd wbook && git pull
cd ~/wbook_<env>/wbook
mkvirtualenv wbook_<env> --python=python3.13                    # later sessions: workon wbook_<env>
pip install -r requirements-prod.txt
```
If `python3.13` is missing, switch the account's system image (Account → System image). Django 6 needs Python ≥ 3.12.

## 2. `.env` (never in git)
```bash
cp .env.example .env && chmod 600 .env
python -c "from django.core.management.utils import get_random_secret_key as k; print(k())"   # → SECRET_KEY
nano .env
git check-ignore -v .env        # must print ".gitignore:...:.env"
```
Production values:
```ini
SECRET_KEY=<generated — different for tst and prd>
DEBUG=False
ALLOWED_HOSTS=www.wbook.com.br,wbook.com.br
SITE_URL=https://www.wbook.com.br
CSRF_TRUSTED_ORIGINS=https://www.wbook.com.br,https://wbook.com.br

DB_ENGINE=sqlite
USE_S3=False
IP_HASH_SALT=<random string, never change after launch>

EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=wbook@gmail.com
EMAIL_HOST_PASSWORD=<16-character Gmail app password, without spaces>
DEFAULT_FROM_EMAIL=wbook <wbook@gmail.com>
SERVER_EMAIL=wbook@gmail.com
PLATFORM_CONTACT_EMAIL=wbook@gmail.com
ADMINS=wbook@gmail.com
```
Test differs in: `SECRET_KEY`, `ALLOWED_HOSTS=plat4user.pythonanywhere.com`, `SITE_URL=https://plat4user.pythonanywhere.com`,
`CSRF_TRUSTED_ORIGINS=https://plat4user.pythonanywhere.com`.

Comments go on their own line (python-decouple keeps `# ...` after a value as part of it). `SITE_URL` must be exactly the address people
browse on — e-mail links, quote links, `.ics` UIDs and the calendar feed are built from it. If `wbook@gmail.com` is replaced by a no-reply
Gmail, only the `EMAIL_*` / `DEFAULT_FROM_EMAIL` lines change.

## 3. E-mail through Gmail
1. Sign in to the Gmail account → Google Account → **Security** → turn on **2-Step Verification**.
2. **App passwords** → create `wbook-tst` and `wbook-prd` → copy the 16 characters into `EMAIL_HOST_PASSWORD`.
3. `python manage.py sendtestemail your-own-address@example.com` and check inbox + spam.
   `SMTPAuthenticationError` → wrong app password or 2-Step off; timeout → host/port.
4. After the first operator login: **Configurações → Alertas por e-mail** → primary and (optional) second alert address.
Gmail sends ~500 messages/day — fine for the MVP; move to a transactional provider before reminders approach that.

## 4. Database, static files, translations, operator account
```bash
cd ~/wbook_<env>/wbook && workon wbook_<env>
python manage.py check --deploy
python manage.py migrate                 # creates db.sqlite3 here
python manage.py collectstatic --noinput
python manage.py createsuperuser         # your OPERATOR login
```
The English `.mo` file is committed, so no `compilemessages` on the server.
Test only — demo data: `python manage.py seed_demo --password 'Demo!2026x' --allow-non-debug`.
**Never** run `makemigrations` on the server. Never copy `db.sqlite3` between test and production.

## 5. Web tab
1. Add a new web app → **Manual configuration** → Python 3.13 (production: custom domain `www.wbook.com.br`; at the registrar
   (registro.br) point `www` with a CNAME to the address PythonAnywhere shows, and redirect the bare `wbook.com.br` to `www`).
2. Source code and working directory `/home/plat4user/wbook_<env>/wbook` · Virtualenv `/home/plat4user/.virtualenvs/wbook_<env>`.
3. WSGI file (replace everything):
   ```python
   import os, sys
   path = "/home/plat4user/wbook_<env>/wbook"   # wbook_tst or wbook_prd
   if path not in sys.path:
       sys.path.insert(0, path)
   os.chdir(path)  # python-decouple finds .env here
   os.environ["DJANGO_SETTINGS_MODULE"] = "config.settings"
   from django.core.wsgi import get_wsgi_application
   application = get_wsgi_application()
   ```
4. Static files (only **public image** folders; clinical files stay private and are served by the app after a permission check):

   | URL | Directory |
   |---|---|
   | `/static/` | `/home/plat4user/wbook_<env>/wbook/staticfiles` |
   | `/media/logos/` | `/home/plat4user/wbook_<env>/wbook/media/logos` |
   | `/media/dentists/` | `/home/plat4user/wbook_<env>/wbook/media/dentists` |
   | `/media/landing/` | `/home/plat4user/wbook_<env>/wbook/media/landing` |

   Do **not** map `/media/` as a whole: `media/treatments/` (clinical PDFs and photos) and `media/quotes/` would become downloadable by URL.
5. **Force HTTPS** on (production: Let's Encrypt certificate for `www.wbook.com.br` first).
6. **Reload**. Errors → "Error log" on the same tab.

## 6. Scheduled tasks (Tasks tab)
```bash
# reminders + expiry of pending requests — hourly on a paid account (daily works but reminders arrive up to a day early)
cd ~/wbook_prd/wbook && ~/.virtualenvs/wbook_prd/bin/python manage.py agenda_tick
# daily backup, keeps the last 7 days
cd ~/wbook_prd/wbook && ~/.virtualenvs/wbook_prd/bin/python manage.py export_data -o ~/backups/wbook-prd-$(date +\%a).zip
```
`mkdir -p ~/backups` once. With SQLite, `db.sqlite3` + `media/` are the whole state; the backup ZIP holds both (restorable with `import_data`).

## 7. Smoke test
`/` and the language switcher (PT ↔ EN) → `/conta/entrar/` → operator login → **Configurações** (alert e-mails) → **Atividade** shows the login.
Register a dentist (verification e-mail + operator alert), set working hours and types, publish the page. In a private window: book as a visitor
(PENDING + lead + dentist e-mail), approve (visitor e-mail with `.ics`), open Add to calendar → Google. Invite a patient, set password, accept
consent, book (auto-confirmed), try to cancel inside the cutoff (WhatsApp redirect + late-cancel alert). Create a treatment, upload a PDF and a
phone photo, share the photo, check the patient sees it. Send a quote, open it in a private window, check the access log. Subscribe the feed in
Google Calendar. Export patients to Excel. Run `agenda_tick` once.

## Release procedure (same for tst and prd)
1. Local: change → `makemigrations` → `ruff check .` → `python manage.py test` → `npm run build:css` if templates changed →
   update `locale/en/.../django.po` and compile.
2. Commit and push (CI runs the same checks). Deploy to **test first**, smoke test, then production.
3. Server:
   ```bash
   cd ~/wbook_<env>/wbook && workon wbook_<env> && git pull \
     && pip install -r requirements-prod.txt && python manage.py migrate && python manage.py collectstatic --noinput
   ```
4. Web tab → Reload.
`collectstatic` is **not optional** (hashed static names from `staticfiles/staticfiles.json`).

## Later: MySQL and S3
1. Databases tab → create `wbook_tst` / `wbook_prd` (→ `plat4user$wbook_tst` / `plat4user$wbook_prd`).
2. `python manage.py export_data -o ~/move.zip`.
3. `.env`: `DB_ENGINE=mysql`, `DB_NAME=plat4user$wbook_<env>`, `DB_USER=plat4user`, `DB_PASSWORD=…`,
   `DB_HOST=plat4user.mysql.pythonanywhere-services.com`; for S3 `USE_S3=True` + `AWS_*` (private bucket per environment).
4. `migrate` → `import_data ~/move.zip --dry-run` → `import_data ~/move.zip` → `createsuperuser` → Reload. Remove the `/media/...` mappings once files are on S3.
