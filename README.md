# wbook — Doctor Appointment SaaS

A Django 4.x multi-tenant appointment booking system.

## Architecture

```
wbook/
├── accounts/          # Custom AbstractUser (Seller) with Doctor/Patient/Operator roles
├── booking/           # Core domain: DoctorProfile, PatientProfile, Appointment, etc.
│   ├── views/
│   │   ├── doctor.py   # Doctor portal views
│   │   ├── patient.py  # Patient portal views
│   │   ├── operator.py # Operator portal views
│   │   └── public.py   # Public booking page + routing
│   └── templates/booking/
│       ├── base_doctor.html
│       ├── base_patient.html
│       ├── base_operator.html
│       ├── doctor/
│       ├── patient/
│       ├── operator/
│       └── public/
└── wbook/          # Project settings & root URLs
```

## Quick Start

```bash
# 1. Install dependencies
pip install Django>=4.2 Pillow

# 2. Run migrations
python manage.py makemigrations accounts booking
python manage.py migrate

# 3. Seed demo data
python manage.py shell < booking/populate_db.py

# 4. (Optional) Create superuser
python manage.py createsuperuser

# 5. Run
python manage.py runserver
```

## Translation to portuguese

`python manage.py makemessages -l pt_BR`

`python manage.py compilemessages`


## Demo Accounts (after seeding)

PORTALS
- Operator  ->  http://localhost:8000/operator/
- Doctor    ->  http://localhost:8000/doctor/
- Patient   ->  http://localhost:8000/patient/

### CREDENTIALS

| Email | Password | Role |
| :--- | :--- | :--- |
| operator@wbook.com | admin123 | Operator |
| dr.sarah@wbook.com | doctor123 | Doctor |
| dr.marcos@wbook.com | doctor123 | Doctor |
| dr.aisha@wbook.com | doctor123 | Doctor |
| alice@example.com | patient123 | Patient |
| bob@example.com | patient123 | Patient |
| carol@example.com | patient123 | Patient |
| david@example.com | patient123 | Patient |
| emily@example.com | patient123 | Patient |

### PUBLIC BOOKING PAGES (no login required)

* [Dr. Sarah Johnson](http://localhost:8000/book/drsarah/)
* [Dr. Marcos Oliveira](http://localhost:8000/book/drmarcos/)
* [Dr. Aisha Patel](http://localhost:8000/book/draisha/)

## URL Map

| Portal   | URL prefix         | Description                        |
|----------|--------------------|------------------------------------|
| Public   | `/book/<slug>/`    | Doctor's public booking page       |
| Doctor   | `/doctor/`         | Doctor dashboard & management      |
| Patient  | `/patient/`        | Patient dashboard & self-booking   |
| Operator | `/operator/`       | SaaS platform management           |
| Auth     | `/accounts/login/` | Login (email-based)                |
| Admin    | `/admin/`          | Django admin panel                 |

## Key Features

### Doctor Portal
- Dashboard with KPIs (patients, today's appointments, pending requests, booking URL)
- Appointment calendar with confirm / reject / complete / notes actions
- Schedule settings: slot duration, slots visible per day, working hours, working days
- Block time periods (vacations, etc.)
- Patient management: invite (sends credentials by email), view history, deactivate
- Public booking URL per doctor: `http://yourdomain.com/book/<doctor-slug>/`

### Patient Portal
- Registered patients: appointments auto-confirmed upon booking
- View upcoming & past appointments
- Cancel (respects doctor's 24/48h cancellation window)
- Reschedule

### Public Booking (unregistered)
- Browse available slots for any doctor via their unique URL
- Submit appointment request → status: PENDING (doctor must confirm)
- Email confirmation sent on request and on doctor action

### Operator Portal
- Dashboard: total doctors, trial stats, total patients & appointments
- Add / edit / delete doctors, set trial duration, suspend accounts
- View all patients and all appointments platform-wide
- Platform settings (default trial days, platform name, support email)

## Email Notifications
Set `EMAIL_BACKEND` in `settings.py` for production. Currently uses console backend.
Emails sent on: appointment request, confirmation, rejection, and patient invite.
