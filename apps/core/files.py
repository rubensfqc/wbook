"""Authorized file streaming with HTTP Range support (local storage and S3)."""

import re

from django.http import FileResponse, HttpResponse, StreamingHttpResponse

RANGE_RE = re.compile(r"bytes=(\d*)-(\d*)$")


def _iter(fh, length, chunk=256 * 1024):
    remaining = length
    while remaining > 0:
        data = fh.read(min(chunk, remaining))
        if not data:
            break
        remaining -= len(data)
        yield data
    fh.close()


def stream_file(request, fieldfile, filename, content_type, inline=True, cache="private, max-age=300"):
    size = fieldfile.size
    disposition = "inline" if inline and not request.GET.get("download") else "attachment"
    header = request.META.get("HTTP_RANGE", "")
    m = RANGE_RE.match(header.strip()) if header else None
    if m and (m.group(1) or m.group(2)):
        start_s, end_s = m.groups()
        if start_s == "":
            length = min(int(end_s), size)
            start, end = size - length, size - 1
        else:
            start = int(start_s)
            end = min(int(end_s), size - 1) if end_s else size - 1
        if start >= size or start > end:
            resp = HttpResponse(status=416)
            resp["Content-Range"] = f"bytes */{size}"
            return resp
        fh = fieldfile.open("rb")
        fh.seek(start)
        length = end - start + 1
        resp = StreamingHttpResponse(_iter(fh, length), status=206, content_type=content_type)
        resp["Content-Range"] = f"bytes {start}-{end}/{size}"
        resp["Content-Length"] = str(length)
    else:
        fh = fieldfile.open("rb")
        resp = FileResponse(fh, content_type=content_type)
        resp["Content-Length"] = str(size)
    resp["Accept-Ranges"] = "bytes"
    resp["Content-Disposition"] = f'{disposition}; filename="{filename}"'
    resp["Cache-Control"] = cache
    resp["X-Content-Type-Options"] = "nosniff"
    return resp


def validate_pdf(f):
    from django.conf import settings
    from django.core.exceptions import ValidationError
    from django.utils.translation import gettext as _

    if not f.name.lower().endswith(".pdf"):
        raise ValidationError(_("Envie um arquivo PDF."))
    if f.size > settings.MAX_UPLOAD_MB * 1024 * 1024:
        raise ValidationError(_("O arquivo passa do limite de %(mb)s MB.") % {"mb": settings.MAX_UPLOAD_MB})
    pos = f.tell() if hasattr(f, "tell") else 0
    head = f.read(5)
    f.seek(pos)
    if head != b"%PDF-":
        raise ValidationError(_("Este arquivo não parece ser um PDF válido."))


def validate_image(f):
    from django.core.exceptions import ValidationError
    from django.utils.translation import gettext as _

    if f.size > 5 * 1024 * 1024:
        raise ValidationError(_("A imagem passa do limite de 5 MB."))
