"""Value <-> text for CSV/TOML cells. Accepts ISO and pt-BR spreadsheet styles on the way in."""

import datetime as dt
import re
import uuid
from decimal import Decimal, InvalidOperation

from django.db import models
from django.utils import timezone

TRUE = {"1", "true", "sim", "s", "yes", "y", "verdadeiro", "x"}
FALSE = {"0", "false", "não", "nao", "n", "no", "falso", ""}


def to_raw(f, value):
    if value is None:
        return ""
    if isinstance(f, models.BooleanField):
        return "sim" if value else "não"
    if isinstance(f, models.DateTimeField):
        return value.astimezone(dt.UTC).isoformat()
    if isinstance(f, (models.DateField, models.TimeField)):
        return value.isoformat()
    if isinstance(f, models.FileField):
        return value.name or ""
    return str(value)


def _decimal(s):
    s = s.replace("R$", "").replace(" ", "")
    if re.match(r"^-?\d{1,3}(\.\d{3})*(,\d+)?$", s) or ("," in s and "." not in s):
        s = s.replace(".", "").replace(",", ".")
    try:
        return Decimal(s)
    except InvalidOperation as exc:
        raise ValueError(f"número inválido: {s}") from exc


def _date(s):
    m = re.match(r"^(\d{2})/(\d{2})/(\d{4})$", s)
    if m:
        return dt.date(int(m.group(3)), int(m.group(2)), int(m.group(1)))
    return dt.date.fromisoformat(s[:10])


def _datetime(s):
    m = re.match(r"^(\d{2})/(\d{2})/(\d{4})[ T](\d{2}):(\d{2})(?::(\d{2}))?$", s)
    if m:
        d, mo, y, h, mi, se = m.groups()
        v = dt.datetime(int(y), int(mo), int(d), int(h), int(mi), int(se or 0))
    else:
        v = dt.datetime.fromisoformat(s.replace("Z", "+00:00"))
    if timezone.is_naive(v):
        v = timezone.make_aware(v)
    return v


def from_raw(f, raw):
    s = "" if raw is None else str(raw).strip()
    if isinstance(f, models.BooleanField):
        low = s.lower()
        if low in TRUE:
            return True
        if low in FALSE:
            return False
        raise ValueError(f"sim/não inválido: {s}")
    if s == "":
        if isinstance(f, (models.CharField, models.TextField, models.FileField)) and not f.null:
            return ""
        if f.has_default() and not f.null:
            return f.get_default()
        return None
    if isinstance(f, models.DateTimeField):
        return _datetime(s)
    if isinstance(f, models.DateField):
        return _date(s)
    if isinstance(f, models.TimeField):
        return dt.time.fromisoformat(s)
    if isinstance(f, models.DecimalField):
        return _decimal(s)
    if isinstance(f, (models.IntegerField, models.BigAutoField, models.AutoField)):
        return int(_decimal(s))
    if isinstance(f, models.UUIDField):
        return uuid.UUID(s)
    return s
