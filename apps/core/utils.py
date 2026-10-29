import hashlib
import re
from decimal import Decimal

from django.conf import settings
from django.core.cache import cache


def client_ip(request):
    fwd = request.META.get("HTTP_X_FORWARDED_FOR", "")
    return (fwd.split(",")[0].strip() if fwd else request.META.get("REMOTE_ADDR", "")) or "0.0.0.0"


def ip_hash(request):
    return hashlib.sha256(f"{settings.IP_HASH_SALT}:{client_ip(request)}".encode()).hexdigest()[:32]


def rate_limited(request, key, limit, window_s):
    """True when the caller already used `limit` hits in `window_s` seconds."""
    k = f"rl:{key}:{ip_hash(request)}"
    n = cache.get(k, 0)
    if n >= limit:
        return True
    cache.set(k, n + 1, window_s)
    return False


def brl(value):
    if value in (None, ""):
        return ""
    q = Decimal(value).quantize(Decimal("0.01"))
    s = f"{q:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"R$ {s}"


BOTS = re.compile(
    r"whatsapp|facebookexternalhit|facebot|slack|telegram|twitterbot|linkedinbot|discordbot|googlebot|bingbot|"
    r"skypeuripreview|embedly|pinterest|bot\b|crawler|spider|preview",
    re.I,
)


def is_bot(request):
    return bool(BOTS.search(request.META.get("HTTP_USER_AGENT", "")))


def describe_user_agent(ua):
    ua = ua or ""
    device = "mobile" if re.search(r"Mobile|Android|iPhone", ua) else ("tablet" if "iPad" in ua else "desktop")
    browser = "outro"
    for name, pat in (("Edge", r"Edg/"), ("Chrome", r"Chrome/"), ("Firefox", r"Firefox/"), ("Safari", r"Safari/")):
        if re.search(pat, ua):
            browser = name
            break
    os_name = "outro"
    for name, pat in (("Android", "Android"), ("iOS", r"iPhone|iPad"), ("Windows", "Windows"), ("macOS", "Mac OS X"), ("Linux", "Linux")):
        if re.search(pat, ua):
            os_name = name
            break
    return device, browser, os_name
