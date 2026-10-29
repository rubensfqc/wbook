# wbook

Plataforma para dentistas: **página pública com agenda online**, **agendamento direto pelo paciente**,
**orçamentos com registro de acesso** e **portal do paciente** (tratamentos, documentos em PDF, fotos antes/depois e faturas).

Django 6 · Python 3.13 · Tailwind (compilado) · HTMX · PDF.js · PythonAnywhere (SQLite + arquivos locais no MVP).
Endereço: **https://www.wbook.com.br** · Idiomas: português (padrão) e inglês.

## Rodando localmente (Windows)

```powershell
cd C:\LocalData\wbook
py -3.13 -m venv .venv
.venv\Scripts\activate
pip install -r requirements-dev.txt
copy .env.example .env
python manage.py migrate
python manage.py seed_demo --password 'Demo!2026x'
python manage.py runserver
```

Abra:
- http://localhost:8000/clinica-sorriso/ — página pública de uma das clínicas demo (agenda com horários livres)
- http://localhost:8000/conta/entrar/ — `ana@sorriso.example` (dentista), `maria@paciente.example` (paciente),
  `carla@wbook.example` (operador). Senha: a que você passou em `--password`.

Veja `seed/README.md` para todos os logins e a situação de cada clínica demo.

E-mails aparecem no terminal (backend de console) enquanto `DEBUG=True`.

> Use Python 3.13. O Python 3.14 quebra o Django nos templates (`Context.__copy__`).

## Testes e qualidade

```bash
python manage.py test
ruff check .
```

## CSS

O CSS já vem compilado em `static/css/app.css`. Só recompile se mudar templates ou classes:

```bash
npm install
npm run build:css          # ou npm run watch:css durante o desenvolvimento
```

## Traduções (inglês)

Os textos-fonte estão em português. A tradução para inglês fica em `locale/en/LC_MESSAGES/django.po`:

```bash
python scripts/makemessages_py.py     # extrai os textos para o .po (não precisa do GNU gettext)
python scripts/compile_messages.py    # gera o .mo
```

Faça commit do `.po` e do `.mo`.

## Tarefas agendadas

Lembretes 24 h antes e expiração de pedidos pendentes (48 h):

```bash
python manage.py agenda_tick
```

## Backup, migração e edição em massa

Operador → **Exportar / importar** (`/operador/dados/`): baixa tudo (ou só alguns dentistas) como ZIP de planilhas CSV + arquivos,
ou um TOML único, e importa de volta com prévia antes de gravar. O dentista também baixa a lista de pacientes (CSV/Excel) e um
backup da própria clínica em `/app/exportar/`.

```bash
python manage.py export_data -o backup.zip
python manage.py export_data --dentist clinica-sorriso -o sorriso.zip
python manage.py import_data backup.zip --dry-run
python manage.py import_data backup.zip
```

## Deploy

Veja `docs/ai/08-deployment.md` (PythonAnywhere, conta `plat4user`: teste `wbook_tst` em `plat4user.pythonanywhere.com`
e produção `wbook_prd` em `www.wbook.com.br`; e-mail via `wbook@gmail.com`). O `.env` nunca vai para o git.

Atualização de uma versão (sempre em teste primeiro, depois produção):

```bash
cd ~/wbook_<env>/wbook && workon wbook_<env>   # <env> = tst ou prd
git pull
pip install -r requirements-prod.txt
python manage.py migrate
python manage.py collectstatic --noinput
```

(O arquivo `.mo` das traduções vai compilado no git; não precisa de `compilemessages` no servidor.)

Depois: aba **Web** do PythonAnywhere → **Reload**. Nunca rode `makemigrations` no servidor.

## Para agentes de IA

Comece por `AGENTS.md`.
