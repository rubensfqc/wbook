"""Builds the demo data. Keys are deterministic (uuid5), so re-running never duplicates rows."""

import io
import uuid
from datetime import datetime, time, timedelta
from decimal import Decimal

from django.core.files.base import ContentFile
from django.db import transaction
from django.utils import timezone

from . import seed_data

NS = uuid.UUID("6f1c2b1e-7a43-4d2a-9b1e-2f6d0b5e9c11")


def R(*parts):
    return uuid.uuid5(NS, "/".join(str(p) for p in parts))


def _logo(text, rgb):
    from PIL import Image, ImageDraw, ImageFont

    img = Image.new("RGB", (256, 256), (255, 255, 255))
    d = ImageDraw.Draw(img)
    d.ellipse((8, 8, 248, 248), fill=rgb)
    try:
        font = ImageFont.load_default(size=96)
    except TypeError:
        font = ImageFont.load_default()
    box = d.textbbox((0, 0), text, font=font)
    d.text(((256 - box[2]) / 2, (256 - box[3]) / 2 - 8), text, fill=(255, 255, 255), font=font)
    buf = io.BytesIO()
    img.save(buf, "PNG")
    return buf.getvalue()


def _illustration(phase, rgb, seed):
    """An abstract drawing of a smile — never a real photo."""
    from PIL import Image, ImageDraw

    w, h = 900, 600
    bg = {"BEFORE": (241, 245, 249), "DURING": (236, 253, 245), "AFTER": (240, 253, 250)}[phase]
    img = Image.new("RGB", (w, h), bg)
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((120, 180, 780, 430), radius=120, fill=(190, 70, 80))
    shade = {"BEFORE": (225, 215, 180), "DURING": (238, 232, 205), "AFTER": (252, 252, 248)}[phase]
    for i in range(8):
        x = 170 + i * 72 + (seed % 3) * 2
        off = (i * seed) % 7 if phase == "BEFORE" else 0
        d.rounded_rectangle((x, 225 + off, x + 62, 320 + off), radius=16, fill=shade, outline=(200, 200, 200))
    d.rectangle((0, h - 40, w, h), fill=rgb)
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=80)
    main = buf.getvalue()
    img.thumbnail((480, 480))
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=80)
    return main, buf.getvalue()


def _pdf(title, lines):
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas

    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    c.setFont("Helvetica-Bold", 18)
    c.drawString(60, 780, title)
    c.setFont("Helvetica", 11)
    y = 740
    for ln in lines:
        c.drawString(60, y, ln)
        y -= 18
    c.setFont("Helvetica-Oblique", 9)
    c.drawString(60, 60, "Documento de demonstração — wbook")
    c.showPage()
    c.save()
    return buf.getvalue()


def _workday(today, offset):
    d = today + timedelta(days=offset)
    while d.weekday() >= 5:
        d += timedelta(days=1 if offset >= 0 else -1)
    return d


class Seeder:
    def __init__(self, password, stdout=None):
        self.password = password
        self.out = stdout

    def log(self, msg):
        if self.out:
            self.out.write(msg)

    @transaction.atomic
    def run(self, operators=True, clinics=True):
        if operators:
            self.operators()
        if clinics:
            for c in seed_data.CLINICS:
                self.clinic(c)

    def operators(self):
        from apps.accounts.models import User

        for o in seed_data.OPERATORS:
            if not User.objects.filter(email=o["email"]).exists():
                User.objects.create_superuser(email=o["email"], password=self.password, name=o["name"])
                self.log(f"operador {o['email']}")

    def clinic(self, c):
        from apps.agenda.models import Appointment, TimeBlock
        from apps.clinic.models import Dentist, Invoice, Treatment, TreatmentEntry, TreatmentFile
        from apps.clinic.services import create_dentist, invite_patient
        from apps.landing.models import Lead
        from apps.quotes.models import Quote, QuoteEvent, QuoteItem, QuoteVisit

        k = c["key"]
        if Dentist.objects.filter(slug=c["slug"]).exists():
            self.log(f"{c['slug']} já existe — mantido")
            return
        today = timezone.localdate()
        d = create_dentist(email=c["email"], name=c["name"], clinic_name=c["clinic_name"], slug=c["slug"], password=self.password,
                           display_name=c["display_name"], cro_number=c["cro"], cro_state=c["uf"], whatsapp=c["whatsapp"],
                           phone=c["phone"], city=c["city"], state=c["uf"], trial_days=c["trial_days"])
        d.ref = R("dentist", k)
        d.user.username = c["slug"].split("-")[-1] + k[:2]
        d.user.save()
        d.address = c["address"]
        d.specialties = c["specialties"]
        d.opening_hours_text = "Seg a sex, 8h às 18h"
        d.pix_key = c["email"]
        d.payment_note = "Parcelamos em até 10x no cartão."
        d.trial_start_date = today - timedelta(days=30) if c["paid_days"] < 0 else today
        if c["paid_days"] > 0:
            d.paid_until = today + timedelta(days=c["paid_days"])
            d.plan_name = "Anual"
        elif c["paid_days"] < 0:
            d.paid_until = today + timedelta(days=c["paid_days"])
        d.onboarding_done = True
        d.calendar_feed_token = R("feed", k)
        initials = "".join(w[0] for w in c["clinic_name"].split()[:2]).upper()
        d.logo.save("logo.png", ContentFile(_logo(initials, c["colour"])), save=False)
        d.save()
        for i, wh in enumerate(d.working_hours.order_by("weekday", "start")):
            wh.ref = R("hours", k, i)
            wh.save()
        for t in d.appointment_types.all():
            t.ref = R("type", k, t.name)
            if t.name == "Avaliação":
                t.price, t.show_price = Decimal("150.00"), True
            t.save()
        b = d.booking
        b.ref = R("booking", k)
        b.max_visible_slots = c["visible_slots"]
        b.save()
        lp = d.landing
        lp.ref = R("landing", k)
        lp.is_published = True
        lp.headline, lp.about, lp.services, lp.accent = c["headline"], c["about"], c["services"], c["accent"]
        lp.subheadline = "Agende sua consulta online em poucos cliques"
        lp.insurance_note = "Atendemos particular e reembolso dos principais convênios"
        lp.show_prices = k == "sorriso"
        lp.save()

        types = {t.name: t for t in d.appointment_types.all()}
        patients = {}
        for pk_, name, email, wa in c["patients"]:
            p = invite_patient(d, name=name, email=email, whatsapp=wa, phone=wa, send=False)
            p.ref = R("patient", k, pk_)
            p.consent_at = timezone.now()
            p.consent_version = "2026-11"
            p.save()
            p.user.set_password(self.password)
            p.user.last_login = timezone.now() - timedelta(days=3)
            p.user.save()
            patients[pk_] = p

        def at(offset, hh, mm=0):
            day = _workday(today, offset)
            return datetime.combine(day, time(hh, mm), tzinfo=d.tzinfo)

        def appt(key, who, type_name, start, status, **extra):
            t = types[type_name]
            a = Appointment(dentist=d, type=t, start=start, end=start + timedelta(minutes=t.duration_min), status=status,
                            ref=R("appointment", k, key), public_token=R("token", k, key), **extra)
            if isinstance(who, Lead):
                a.lead = who
                a.source = Appointment.Source.PUBLIC
            else:
                a.patient = who
            if status in ("CONFIRMED", "COMPLETED"):
                a.confirmed_at = timezone.now()
            a.save()
            return a

        # treatments + files + entries + invoices
        treatments = {}
        for i, (pkey, tkey, title, region, status, progress, sessions, budget) in enumerate(c["treatments"]):
            p = patients[pkey]
            t = Treatment.objects.create(dentist=d, patient=p, title=title, region=region, status=status, progress=progress,
                                         estimated_sessions=sessions, budget=Decimal(budget), ref=R("treatment", k, tkey),
                                         start_date=today - timedelta(days=60 - i * 10),
                                         expected_end=today + timedelta(days=90),
                                         description="Plano combinado na consulta de avaliação.")
            treatments[tkey] = t
            pdf = TreatmentFile(treatment=t, kind="PDF", title="Plano de tratamento.pdf", shared=True, ref=R("file", k, tkey, "pdf"),
                                taken_on=t.start_date)
            data = _pdf(f"Plano de tratamento — {title}", [f"Paciente: {p.name}", f"Região: {region}", f"Sessões previstas: {sessions}",
                                                          f"Valor: R$ {budget}"])
            pdf.file.save("plano.pdf", ContentFile(data), save=False)
            pdf.size = len(data)
            pdf.save()
            phases = ["BEFORE", "DURING", "AFTER"] if status == "COMPLETED" else ["BEFORE", "DURING"]
            for j, ph in enumerate(phases):
                main, thumb = _illustration(ph, c["colour"], i + j + 1)
                f = TreatmentFile(treatment=t, kind="PHOTO", phase=ph, caption=f"Foto {ph.lower()}", region=region,
                                  shared=ph != "DURING", taken_on=t.start_date + timedelta(days=20 * j), ref=R("file", k, tkey, ph))
                f.file.save("foto.jpg", ContentFile(main), save=False)
                f.thumb.save("thumb.jpg", ContentFile(thumb), save=False)
                f.size = len(main)
                f.save()
            TreatmentEntry.objects.create(treatment=t, kind="EVT", text="Tratamento criado", author=d.user, author_role="DENTIST",
                                          ref=R("entry", k, tkey, 1))
            TreatmentEntry.objects.create(treatment=t, kind="MSG", text="Qualquer dúvida sobre o tratamento, escreva por aqui.",
                                          author=d.user, author_role="DENTIST", ref=R("entry", k, tkey, 2))
            TreatmentEntry.objects.create(treatment=t, kind="MSG", text="Obrigada, doutora! Até a próxima sessão.",
                                          author=p.user, author_role="PATIENT", ref=R("entry", k, tkey, 3))
            inv = Invoice(treatment=t, dentist=d, title=f"{title} — 1ª parcela", amount=Decimal(budget) / 2, ref=R("invoice", k, tkey, 1),
                          issued_date=today - timedelta(days=30), due_date=today - timedelta(days=20), status="PAID",
                          paid_at=timezone.now() - timedelta(days=21))
            inv.save()
            inv2 = Invoice(treatment=t, dentist=d, title=f"{title} — 2ª parcela", amount=Decimal(budget) / 2, ref=R("invoice", k, tkey, 2),
                           issued_date=today, due_date=today + timedelta(days=15), status="PAID" if status == "COMPLETED" else "OPEN")
            inv2.save()

        # appointments
        plist = list(patients.values())
        for i, p in enumerate(plist):
            appt(f"past-{i}", p, "Limpeza" if i % 2 else "Avaliação", at(-25 + i * 2, 9 + i % 6), "COMPLETED",
                 treatment=next(iter(p.treatments.all()), None))
            if i < 5:
                appt(f"future-{i}", p, "Avaliação" if i % 2 else "Limpeza", at(1 + i * 2, 10 + i % 5), "CONFIRMED",
                     treatment=next(iter(p.treatments.all()), None))
        if len(plist) > 1:
            appt("noshow", plist[1], "Avaliação", at(-5, 15), "NO_SHOW")
            late = appt("late", plist[0], "Retorno", at(1, 16), "CONFIRMED")
            late.late_cancel_requested_at = timezone.now() - timedelta(hours=2)
            late.late_cancel_note = "Surgiu uma viagem de trabalho."
            late.save()
            old = appt("moved-old", plist[1], "Limpeza", at(4, 8), "RESCHEDULED")
            appt("moved-new", plist[1], "Limpeza", at(6, 8, 30), "CONFIRMED", rescheduled_from=old, ics_sequence=1)
            appt("cancelled", plist[-1], "Avaliação", at(3, 11), "CANCELLED", cancelled_by="PATIENT", cancelled_at=timezone.now())

        leads = {}
        for i, (lkey, name, email, wa, msg) in enumerate(c["leads"]):
            lead = Lead.objects.create(dentist=d, name=name, email=email, whatsapp=wa, message=msg, consent=True,
                                       source="BOOKING", ref=R("lead", k, lkey))
            leads[lkey] = lead
            appt(f"lead-{lkey}", lead, "Avaliação", at(5 + i * 3, 14), "PENDING", patient_note=msg)
        TimeBlock.objects.create(dentist=d, start=at(9, 12), end=at(9, 13, 30), reason="Curso de atualização", ref=R("block", k, 1))

        # quotes
        if k == "sorriso":
            lead = leads["fernanda"]
            q = Quote.objects.create(dentist=d, lead=lead, recipient_name=lead.name, recipient_email=lead.email,
                                     recipient_whatsapp=lead.whatsapp, uuid=R("quote", k, 1), ref=R("quoteref", k, 1),
                                     title="Clareamento dental", intro="Conforme conversamos na avaliação:",
                                     payment_terms="À vista no PIX com 5% de desconto ou em até 6x no cartão.", timeline="3 sessões",
                                     valid_until=today + timedelta(days=20), status="VIEWED", sent_at=timezone.now() - timedelta(days=2))
            QuoteItem.objects.create(quote=q, description="Clareamento de consultório", quantity=2, unit_amount=Decimal("450.00"),
                                     ref=R("qi", k, 1))
            QuoteItem.objects.create(quote=q, description="Moldeira para clareamento caseiro", quantity=1, unit_amount=Decimal("300.00"),
                                     ref=R("qi", k, 2))
            lead.status = "QUOTE"
            lead.save()
            for j in range(3):
                v = QuoteVisit.objects.create(quote=q, token=R("visit", k, j), started_at=timezone.now() - timedelta(days=2 - j, hours=j),
                                              duration_s=[95, 240, 61][j], max_scroll_pct=[60, 100, 85][j],
                                              device=["mobile", "desktop", "mobile"][j], browser=["Safari", "Chrome", "Safari"][j],
                                              os=["iOS", "Windows", "iOS"][j], ip_hash=f"seed{j % 2}", is_returning=j > 0)
                if j == 1:
                    QuoteEvent.objects.create(visit=v, kind="pdf", ref=R("qe", k, j))
            p = patients["pedro"]
            q2 = Quote.objects.create(dentist=d, patient=p, recipient_name=p.name, recipient_email=p.email, uuid=R("quote", k, 2),
                                      ref=R("quoteref", k, 2), title="Restaurações estéticas", status="ACCEPTED",
                                      sent_at=timezone.now() - timedelta(days=6), responded_at=timezone.now() - timedelta(days=5),
                                      response_note="Pode agendar, obrigado!", valid_until=today + timedelta(days=10))
            QuoteItem.objects.create(quote=q2, description="Restauração em resina", region="14, 15", quantity=2,
                                     unit_amount=Decimal("320.00"), ref=R("qi", k, 3))
        self.log(f"clínica {c['slug']}: {len(patients)} pacientes, {len(treatments)} tratamentos")
