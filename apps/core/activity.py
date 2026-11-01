"""Activity log: one line per action in a rotating file, read by operators at /operador/atividade/."""

import logging
import re

logger = logging.getLogger("wbook.activity")

CATEGORIES = [
    "auth", "agenda", "booking", "patient", "treatment", "file", "quote", "invoice",
    "lead", "export", "alert", "email", "settings", "operator",
]
_CLEAN = re.compile(r"[\r\n|]+")


def _clean(value):
    return _CLEAN.sub(" ", str(value)).strip()


def _who(actor):
    user = getattr(actor, "user", actor)
    if user is None or not getattr(user, "is_authenticated", False):
        return "anônimo"
    return f"{user.email} ({user.role})"


def log_action(actor, category, message, level=logging.INFO, **values):
    """Never raises: logging must not break the action being logged."""
    from django.utils import timezone

    try:
        if values:
            message = message % {k: _clean(v) for k, v in values.items()}
        stamp = timezone.localtime().strftime("%Y-%m-%d %H:%M:%S")
        level_name = logging.getLevelName(level)
        logger.log(level, "%s | %s | %s | %s | %s", stamp, level_name, _clean(category), _clean(_who(actor)), _clean(message))
    except Exception:  # noqa: BLE001
        logging.getLogger("wbook").exception("activity log failed")


def read_lines(path, limit=5000):
    """Newest first, current file + .1."""
    import os

    lines = []
    for p in (path + ".1", path):
        if os.path.exists(p):
            with open(p, encoding="utf-8", errors="replace") as fh:
                lines.extend(fh.read().splitlines())
    out = []
    for raw in reversed(lines[-limit:]):
        parts = [p.strip() for p in raw.split(" | ", 4)]
        if len(parts) == 5:
            out.append({"when": parts[0], "level": parts[1], "category": parts[2], "who": parts[3], "message": parts[4]})
    return out
