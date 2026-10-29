"""wa.me links only (no WhatsApp API)."""

import re
from urllib.parse import quote


def digits(number):
    d = re.sub(r"\D", "", number or "")
    if not d:
        return ""
    if len(d) in (10, 11):  # Brazilian number without country code
        d = "55" + d
    return d


def wa_link(number, text=""):
    d = digits(number)
    if not d:
        return ""
    return f"https://wa.me/{d}" + (f"?text={quote(text)}" if text else "")


def wa_share(text):
    return f"https://wa.me/?text={quote(text)}"
