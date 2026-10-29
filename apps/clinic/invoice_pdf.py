"""Invoice PDF with ReportLab (built-in Helvetica, no font file)."""

import io

from django.utils import translation
from django.utils.translation import gettext as _
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas

from apps.core.utils import brl


def render_invoice_pdf(invoice, language="pt-br"):
    with translation.override(language):
        return _render(invoice)


def _render(inv):
    d = inv.dentist
    t = inv.treatment
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    w, h = A4
    c.setFillColor(colors.HexColor("#134e4a"))
    c.rect(0, h - 38 * mm, w, 38 * mm, fill=1, stroke=0)
    x = 18 * mm
    if d.logo:
        try:
            with d.logo.open("rb") as fh:
                c.drawImage(ImageReader(io.BytesIO(fh.read())), x, h - 32 * mm, width=26 * mm, height=26 * mm,
                            preserveAspectRatio=True, mask="auto")
            x += 32 * mm
        except Exception:  # noqa: BLE001
            pass
    c.setFillColor(colors.white)
    c.setFont("Helvetica-Bold", 16)
    c.drawString(x, h - 17 * mm, d.clinic_name)
    c.setFont("Helvetica", 10)
    line = d.name + (f" — CRO {d.cro_number}/{d.cro_state}" if d.cro_number else "")
    c.drawString(x, h - 23 * mm, line)
    c.drawString(x, h - 29 * mm, d.full_address or d.contact_phone or "")
    c.setFont("Helvetica-Bold", 20)
    c.drawRightString(w - 18 * mm, h - 20 * mm, _("Fatura %(n)s") % {"n": inv.display_number})

    y = h - 52 * mm
    c.setFillColor(colors.black)

    def row(label, value, bold=False):
        nonlocal y
        c.setFont("Helvetica", 9)
        c.setFillColor(colors.HexColor("#64748b"))
        c.drawString(18 * mm, y, label)
        c.setFillColor(colors.black)
        c.setFont("Helvetica-Bold" if bold else "Helvetica", 11)
        c.drawString(60 * mm, y, str(value or "—"))
        y -= 7 * mm

    row(_("Paciente"), t.patient.name, True)
    row(_("Tratamento"), t.title)
    row(_("Emissão"), f"{inv.issued_date:%d/%m/%Y}")
    row(_("Vencimento"), f"{inv.due_date:%d/%m/%Y}" if inv.due_date else "—")
    row(_("Situação"), inv.get_status_display())

    y -= 4 * mm
    c.setStrokeColor(colors.HexColor("#cbd5e1"))
    c.line(18 * mm, y, w - 18 * mm, y)
    y -= 9 * mm
    c.setFont("Helvetica", 11)
    c.drawString(18 * mm, y, inv.title[:90])
    c.setFont("Helvetica-Bold", 14)
    c.drawRightString(w - 18 * mm, y, brl(inv.amount))
    y -= 6 * mm
    c.line(18 * mm, y, w - 18 * mm, y)

    if inv.notes:
        y -= 10 * mm
        c.setFont("Helvetica", 10)
        for ln in inv.notes.splitlines()[:8]:
            c.drawString(18 * mm, y, ln[:100])
            y -= 5 * mm

    y -= 10 * mm
    c.setFillColor(colors.HexColor("#f0fdfa"))
    c.roundRect(18 * mm, y - 26 * mm, w - 36 * mm, 30 * mm, 3 * mm, fill=1, stroke=0)
    c.setFillColor(colors.black)
    c.setFont("Helvetica-Bold", 11)
    c.drawString(23 * mm, y - 3 * mm, _("Como pagar"))
    c.setFont("Helvetica", 10)
    yy = y - 10 * mm
    if d.pix_key:
        c.drawString(23 * mm, yy, _("Chave PIX: %(k)s") % {"k": d.pix_key})
        yy -= 5 * mm
    if d.payment_link:
        c.drawString(23 * mm, yy, _("Link de pagamento: %(l)s") % {"l": d.payment_link[:80]})
        yy -= 5 * mm
    if d.payment_note:
        c.drawString(23 * mm, yy, d.payment_note[:100])

    c.setFont("Helvetica", 8)
    c.setFillColor(colors.HexColor("#94a3b8"))
    c.drawString(18 * mm, 12 * mm, _("Gerado pelo wbook — www.wbook.com.br"))
    c.showPage()
    c.save()
    return buf.getvalue()
