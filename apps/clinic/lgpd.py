"""LGPD export of one patient's data as a ZIP (JSON + files)."""

import io
import json
import zipfile

from django.utils import timezone


def _iso(v):
    return v.isoformat() if v else None


def patient_zip(patient, include_unshared=False):
    u = patient.user
    data = {
        "exported_at": timezone.now().isoformat(),
        "dentist": {"name": patient.dentist.name, "clinic": patient.dentist.clinic_name, "cro": patient.dentist.cro_number},
        "patient": {"name": u.name, "email": u.email, "phone": u.phone, "whatsapp": patient.whatsapp, "cpf": patient.cpf,
                    "birth_date": _iso(patient.birth_date), "consent_at": _iso(patient.consent_at)},
        "appointments": [
            {"start": _iso(a.start), "end": _iso(a.end), "type": a.type.name, "status": a.status, "note": a.patient_note}
            for a in patient.appointments.select_related("type").order_by("start")
        ],
        "treatments": [],
    }
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for t in patient.treatments.all():
            if not include_unshared and not t.is_visible_to_patient:
                continue
            files = t.files.all() if include_unshared else t.files.filter(shared=True)
            item = {
                "title": t.title, "description": t.description, "region": t.region, "status": t.status, "progress": t.progress,
                "start_date": _iso(t.start_date), "expected_end": _iso(t.expected_end),
                "entries": [{"at": _iso(e.created_at), "kind": e.kind, "text": e.text} for e in t.entries.all()],
                "invoices": [{"number": i.display_number, "title": i.title, "amount": str(i.amount), "status": i.status}
                             for i in t.invoices.all()],
                "files": [],
            }
            for f in files:
                ext = "pdf" if f.kind == "PDF" else "jpg"
                path = f"files/tratamento-{t.pk}/{f.get_kind_display()}-{f.pk}.{ext}"
                try:
                    with f.file.open("rb") as fh:
                        zf.writestr(path, fh.read())
                    item["files"].append({"path": path, "phase": f.phase, "title": f.title or f.caption, "date": _iso(f.taken_on)})
                except Exception:  # noqa: BLE001
                    pass
            data["treatments"].append(item)
        zf.writestr("dados.json", json.dumps(data, ensure_ascii=False, indent=2))
    return buf.getvalue()
