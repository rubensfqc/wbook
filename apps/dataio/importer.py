"""Upsert import of a wbook export (ZIP of CSVs or TOML). All-or-nothing; nothing is ever deleted."""

import csv
import io
import json
import tomllib
import uuid
import zipfile
from dataclasses import dataclass, field

from django.contrib.auth.hashers import identify_hasher
from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.db import models, transaction

from apps.core.signals import file_cleanup_suspended

from . import codec
from .spec import BY_NAME, FORMAT, TABLES, VERSION, table_for_model, tenant_of

MAX_UNCOMPRESSED = 2 * 1024**3


@dataclass
class Report:
    ok: bool = True
    dry_run: bool = True
    counts: dict = field(default_factory=dict)  # table -> {"created": n, "updated": n}
    errors: list = field(default_factory=list)
    warnings: list = field(default_factory=list)
    manifest: dict = field(default_factory=dict)

    def error(self, msg):
        self.ok = False
        self.errors.append(msg)


class _Abort(Exception):
    pass


def read_bundle(raw):
    """Returns (manifest, {table: [dict rows]}, {path: bytes-getter})."""
    if raw[:2] == b"PK":
        zf = zipfile.ZipFile(io.BytesIO(raw))
        total = 0
        for info in zf.infolist():
            n = info.filename
            if n.startswith("/") or ".." in n.split("/") or "\\" in n:
                raise ValueError(f"caminho inseguro no ZIP: {n}")
            total += info.file_size
        if total > MAX_UNCOMPRESSED:
            raise ValueError("ZIP grande demais (mais de 2 GB descompactado)")
        man = json.loads(zf.read("manifest.json").decode("utf-8"))
        tables = {}
        for t in TABLES:
            name = f"{t.name}.csv"
            if name in zf.namelist():
                text = zf.read(name).decode("utf-8-sig")
                tables[t.name] = list(csv.DictReader(io.StringIO(text)))
        files = {n[len("files/"):]: (lambda n=n: zf.read(n)) for n in zf.namelist() if n.startswith("files/") and not n.endswith("/")}
        return man, tables, files
    doc = tomllib.loads(raw.decode("utf-8"))
    man = doc.pop("manifest", {})
    tables = {k: [{kk: ("" if vv is None else str(vv)) for kk, vv in r.items()} for r in v] for k, v in doc.items() if k in BY_NAME}
    return man, tables, {}


def run_import(raw, dry_run=True):
    rep = Report(dry_run=dry_run)
    try:
        man, tables, files = read_bundle(raw)
    except Exception as exc:  # noqa: BLE001
        rep.error(f"Arquivo inválido: {exc}")
        return rep
    rep.manifest = man
    if man.get("format") != FORMAT:
        rep.error("Este arquivo não é uma exportação do wbook (manifest.format).")
        return rep
    if int(man.get("version", 0)) > VERSION:
        rep.error("Exportação de uma versão mais nova do wbook.")
        return rep
    written = []
    try:
        with file_cleanup_suspended(), transaction.atomic():
            _Importer(tables, files, rep, dry_run, written).run()
            if not rep.ok or dry_run:
                raise _Abort
    except _Abort:
        pass
    if not rep.ok or dry_run:
        for name in written:
            default_storage.delete(name)
    return rep


class _Importer:
    def __init__(self, tables, files, rep, dry_run, written):
        self.tables, self.files, self.rep, self.dry_run, self.written = tables, files, rep, dry_run, written
        self.cache = {}  # (table, key) -> obj
        self.late = []  # (obj, field, table_name, key)

    def lookup(self, table_name, key):
        if key in ("", None):
            return None
        ck = (table_name, str(key))
        if ck in self.cache:
            return self.cache[ck]
        t = BY_NAME[table_name]
        try:
            val = str(key).lower() if t.key == "email" else (int(key) if t.key == "id" else uuid.UUID(str(key)))
            obj = t.model.objects.filter(**{t.key: val}).first()
        except (ValueError, TypeError):
            obj = None
        if obj is not None:
            self.cache[ck] = obj
        return obj

    def run(self):
        for t in TABLES:
            rows = self.tables.get(t.name)
            if rows is None:
                continue
            c = self.rep.counts.setdefault(t.name, {"created": 0, "updated": 0})
            for i, row in enumerate(rows, start=2):
                self.row(t, i, row, c)
        for obj, f, target_table, key, where in self.late:
            target = self.lookup(target_table, key)
            if target is None:
                self.rep.error(f"{where}: {f.name} → chave {key} não encontrada")
                continue
            if tenant_of(target) != tenant_of(obj):
                self.rep.error(f"{where}: {f.name} aponta para outro dentista")
                continue
            setattr(obj, f.name, target)
            obj.save(update_fields=[f.name])

    def row(self, t, line, row, counts):
        key = (row.get(t.key) or "").strip()
        where = f"{t.name} · linha {line} ({key or 'nova'})"
        model = t.model
        if t.key == "email":
            key = key.lower()
        existing = self.lookup(t.name, key) if key else None
        obj = existing or model()
        try:
            auto_values = {}
            for f in t.fields:
                if f.name not in row:
                    continue
                raw = row[f.name]
                if isinstance(f, models.ForeignKey):
                    target_t = table_for_model(f.related_model)
                    if target_t is None:
                        continue
                    if f.name in t.late_fks:
                        if raw:
                            self.late.append((obj, f, target_t.name, raw, where))
                        continue
                    target = self.lookup(target_t.name, raw) if raw else None
                    if raw and target is None:
                        raise ValueError(f"{f.name} → chave {raw} não encontrada")
                    if target is None and not f.null:
                        raise ValueError(f"{f.name} é obrigatório")
                    setattr(obj, f.name, target)
                    continue
                if f.name == "password":
                    if raw:
                        try:
                            identify_hasher(raw)
                        except ValueError as exc:
                            raise ValueError("password precisa ser um hash do Django (texto puro é recusado)") from exc
                        obj.password = raw
                    elif not existing:
                        obj.set_unusable_password()
                        self.rep.warnings.append(f"{where}: sem senha — use \"Esqueci minha senha\"")
                    continue
                if isinstance(f, models.FileField):
                    obj_name = (raw or "").strip()
                    if obj_name:
                        self.file(obj_name, where)
                    setattr(obj, f.attname, obj_name)
                    continue
                value = codec.from_raw(f, raw)
                if getattr(f, "auto_now", False) or getattr(f, "auto_now_add", False):
                    if value is not None:
                        auto_values[f.name] = value
                    continue
                if f.name == t.key and value in (None, "") and t.key == "ref":
                    continue
                setattr(obj, f.name, value)
            if t.key == "ref" and not getattr(obj, "ref", None):
                obj.ref = uuid.uuid4()
            self.rules(t, obj, existing, where)
            exclude = [f.name for f in t.fields if f.name in t.late_fks] + ["password"]
            obj.full_clean(exclude=exclude, validate_unique=True, validate_constraints=True)
            with transaction.atomic():
                obj.save()
                if auto_values:
                    model.objects.filter(pk=obj.pk).update(**auto_values)
            counts["updated" if existing else "created"] += 1
            self.cache[(t.name, str(getattr(obj, t.key)))] = obj
        except ValidationError as exc:
            msgs = "; ".join(f"{k}: {' '.join(v)}" for k, v in exc.message_dict.items()) if hasattr(exc, "message_dict") else " ".join(exc.messages)
            self.rep.error(f"{where}: {msgs}")
        except Exception as exc:  # noqa: BLE001
            self.rep.error(f"{where}: {exc}")

    def file(self, name, where):
        if default_storage.exists(name):
            return
        getter = self.files.get(name)
        if getter is None:
            self.rep.warnings.append(f"{where}: arquivo {name} não está no pacote nem no armazenamento")
            return
        if self.dry_run:
            return
        saved = default_storage.save(name, ContentFile(getter()))
        self.written.append(saved)

    def rules(self, t, obj, existing, where):
        from apps.accounts.models import User

        if t.name == "users":
            if existing is not None and (existing.is_staff or existing.is_superuser or existing.role == User.Role.OPERATOR):
                raise ValueError("contas de operador não podem ser alteradas por importação")
            if obj.role not in (User.Role.DENTIST, User.Role.PATIENT):
                raise ValueError("role precisa ser DENTIST ou PATIENT")
            obj.is_staff = False
            obj.is_superuser = False
        if t.name == "dentists" and obj.user_id and obj.user.role != User.Role.DENTIST:
            raise ValueError("o usuário do dentista precisa ter role DENTIST")
        if t.name == "patients" and obj.user_id and obj.user.role != User.Role.PATIENT:
            raise ValueError("o usuário do paciente precisa ter role PATIENT")
        if t.name in ("dentists", "patients"):
            other = getattr(obj.user, "dentist_profile" if t.name == "patients" else "patient_profile", None)
            if other is not None:
                raise ValueError("este usuário já tem outro perfil")
        if t.name == "appointments" and bool(obj.patient_id) == bool(obj.lead_id):
            raise ValueError("a consulta precisa ter um paciente OU um lead")
        # cross-tenant: every FK target must belong to the same dentist as the row
        mine = tenant_of(obj)
        for f in t.fk_fields():
            if f.name in t.late_fks or f.name == "user" or f.related_model._meta.label_lower == "accounts.user":
                continue
            target = getattr(obj, f.name, None)
            if target is not None and mine is not None and tenant_of(target) not in (None, mine):
                raise ValueError(f"{f.name} pertence a outro dentista")
