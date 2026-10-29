"""/arquivos/ — every private file passes an authorization check first."""

from django.contrib.auth.decorators import login_required
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404

from apps.core.activity import log_action
from apps.core.files import stream_file

from .invoice_pdf import render_invoice_pdf
from .models import Invoice, TreatmentFile


def _files_for(user):
    if user.is_dentist and hasattr(user, "dentist_profile"):
        return TreatmentFile.objects.for_dentist(user.dentist_profile)
    if user.is_patient and hasattr(user, "patient_profile"):
        return TreatmentFile.objects.for_patient(user.patient_profile)
    raise Http404


@login_required
def document(request, pk):
    f = get_object_or_404(_files_for(request.user).filter(kind="PDF"), pk=pk)
    log_action(request, "file", "Documento #%(id)s aberto (tratamento #%(t)s)", id=f.pk, t=f.treatment_id)
    name = (f.title or "documento").replace('"', "")[:60]
    if not name.lower().endswith(".pdf"):
        name += ".pdf"
    return stream_file(request, f.file, name, "application/pdf")


@login_required
def photo(request, pk):
    f = get_object_or_404(_files_for(request.user).filter(kind="PHOTO"), pk=pk)
    thumb = bool(request.GET.get("thumb")) and f.thumb
    if not thumb:
        log_action(request, "file", "Foto #%(id)s aberta (tratamento #%(t)s)", id=f.pk, t=f.treatment_id)
    return stream_file(request, f.thumb if thumb else f.file, f"foto-{f.pk}.jpg", "image/jpeg")


@login_required
def invoice(request, pk):
    user = request.user
    if user.is_dentist and hasattr(user, "dentist_profile"):
        qs = Invoice.objects.for_dentist(user.dentist_profile)
    elif user.is_patient and hasattr(user, "patient_profile"):
        qs = Invoice.objects.for_patient(user.patient_profile)
    else:
        raise Http404
    inv = get_object_or_404(qs.select_related("treatment__patient__user", "dentist"), pk=pk)
    pdf = render_invoice_pdf(inv, language=getattr(request, "LANGUAGE_CODE", "pt-br"))
    resp = HttpResponse(pdf, content_type="application/pdf")
    disp = "attachment" if request.GET.get("download") else "inline"
    resp["Content-Disposition"] = f'{disp}; filename="fatura-{inv.number:04d}.pdf"'
    resp["Cache-Control"] = "private, no-store"
    return resp


@login_required
def quote_attachment(request, pk):
    from apps.quotes.models import Quote

    if not (request.user.is_dentist and hasattr(request.user, "dentist_profile")):
        raise Http404
    q = get_object_or_404(Quote.objects.for_dentist(request.user.dentist_profile), pk=pk)
    if not q.attachment:
        raise Http404
    return stream_file(request, q.attachment, f"orcamento-{q.pk}.pdf", "application/pdf")
