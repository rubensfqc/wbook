import csv
import io
import json
import zipfile

from django.db import models
from django.utils import timezone

from . import codec
from .spec import FORMAT, TABLES, VERSION, table_for_model


def _key_value(obj):
    t = table_for_model(obj.__class__)
    return str(getattr(obj, t.key)) if t else ""


def rows_for(table, qs, include_passwords=True):
    header = [f.name for f in table.fields]
    rows = []
    for obj in qs:
        row = []
        for f in table.fields:
            if isinstance(f, models.ForeignKey):
                target = getattr(obj, f.name)
                row.append(_key_value(target) if target is not None else "")
            elif f.name == "password" and not include_passwords:
                row.append("")
            else:
                row.append(codec.to_raw(f, getattr(obj, f.name)))
        rows.append(row)
    return header, rows


def collect(dentists=None, include_passwords=True, include_platform=True):
    from .spec import scoped_queryset

    out = []
    for t in TABLES:
        if t.platform and not include_platform:
            continue
        qs = scoped_queryset(t, dentists)
        header, rows = rows_for(t, qs, include_passwords)
        files = []
        for f in t.file_fields():
            idx = header.index(f.name)
            for obj, row in zip(qs, rows):
                if row[idx]:
                    files.append(getattr(obj, f.name))
        out.append((t, header, rows, files))
    return out


def manifest(data, dentists):
    return {
        "format": FORMAT, "version": VERSION, "created_at": timezone.now().isoformat(),
        "scope": "all" if dentists is None else [d.slug for d in dentists],
        "tables": {t.name: len(rows) for t, _h, rows, _f in data},
    }


README = """Exportação do wbook
====================
Cada arquivo .csv é uma tabela (UTF-8). As colunas de ligação (ex.: patient, dentist) contêm a chave da linha
referenciada (ref, e-mail ou uuid), nunca o id do banco. Para editar em massa: altere as planilhas e importe de volta
em /operador/dados/ — a importação mostra uma prévia antes de gravar e nunca apaga nada.
A pasta files/ contém os arquivos (PDFs, fotos, logos) no mesmo caminho do armazenamento.
"""


def export_bundle(fmt="zip", dentists=None, include_files=True, include_passwords=True, include_platform=True):
    data = collect(dentists, include_passwords, include_platform)
    man = manifest(data, dentists)
    if fmt == "toml":
        import tomli_w

        doc = {"manifest": man}
        for t, header, rows, _files in data:
            doc[t.name] = [dict(zip(header, r)) for r in rows]
        return tomli_w.dumps(doc).encode("utf-8")
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("manifest.json", json.dumps(man, ensure_ascii=False, indent=2))
        zf.writestr("LEIA-ME.txt", README)
        for t, header, rows, files in data:
            s = io.StringIO()
            s.write("﻿")
            w = csv.writer(s)
            w.writerow(header)
            w.writerows(rows)
            zf.writestr(f"{t.name}.csv", s.getvalue())
            if include_files:
                for ff in files:
                    try:
                        with ff.open("rb") as fh:
                            zf.writestr(f"files/{ff.name}", fh.read())
                    except Exception:  # noqa: BLE001 — missing file: the row still travels
                        pass
    return buf.getvalue()
