"""Minimal iCalendar (RFC 5545) writer — no dependency."""

from datetime import UTC, datetime


def _esc(text):
    return (str(text or "")).replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\r\n", "\\n").replace("\n", "\\n")


def _dt(value):
    return value.astimezone(UTC).strftime("%Y%m%dT%H%M%SZ")


def _fold(line):
    raw = line.encode("utf-8")
    if len(raw) <= 75:
        return line
    out, cur = [], b""
    for ch in line:
        b = ch.encode("utf-8")
        if len(cur) + len(b) > (75 if not out else 74):
            out.append(cur.decode("utf-8"))
            cur = b""
        cur += b
    out.append(cur.decode("utf-8"))
    return "\r\n ".join(out)


def event_lines(ev):
    """ev: dict with uid, sequence, start, end, summary, location, description, url, status, alarm_minutes."""
    lines = [
        "BEGIN:VEVENT",
        f"UID:{ev['uid']}",
        f"SEQUENCE:{int(ev.get('sequence', 0))}",
        f"DTSTAMP:{_dt(datetime.now(UTC))}",
        f"DTSTART:{_dt(ev['start'])}",
        f"DTEND:{_dt(ev['end'])}",
        f"SUMMARY:{_esc(ev.get('summary'))}",
    ]
    if ev.get("location"):
        lines.append(f"LOCATION:{_esc(ev['location'])}")
    if ev.get("description"):
        lines.append(f"DESCRIPTION:{_esc(ev['description'])}")
    if ev.get("url"):
        lines.append(f"URL:{ev['url']}")
    lines.append(f"STATUS:{ev.get('status', 'CONFIRMED')}")
    if ev.get("alarm_minutes") and ev.get("status") != "CANCELLED":
        lines += [
            "BEGIN:VALARM",
            f"TRIGGER:-PT{int(ev['alarm_minutes'])}M",
            "ACTION:DISPLAY",
            f"DESCRIPTION:{_esc(ev.get('summary'))}",
            "END:VALARM",
        ]
    lines.append("END:VEVENT")
    return lines


def calendar(events, method="PUBLISH", name=None):
    lines = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//wbook//wbook.com.br//PT", "CALSCALE:GREGORIAN", f"METHOD:{method}"]
    if name:
        lines += [f"X-WR-CALNAME:{_esc(name)}", "X-PUBLISHED-TTL:PT1H", "REFRESH-INTERVAL;VALUE=DURATION:PT1H"]
    for ev in events:
        lines += event_lines(ev)
    lines.append("END:VCALENDAR")
    return ("\r\n".join(_fold(line) for line in lines) + "\r\n").encode("utf-8")
