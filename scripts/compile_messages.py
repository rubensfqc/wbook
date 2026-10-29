"""Pure-Python .po → .mo compiler (no GNU gettext). Usage: python scripts/compile_messages.py"""

import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from makemessages_py import read_po  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent


def compile_po(po_path):
    entries = read_po(po_path)
    msgs = {}
    for (msgid, plural), e in entries.items():
        if plural is not None:
            s0, s1 = e.get("msgstr[0]", ""), e.get("msgstr[1]", "")
            if s0 and s1:
                msgs[msgid + "\0" + plural] = s0 + "\0" + s1
        elif msgid == "":
            msgs[""] = e.get("msgstr", "")
        elif e.get("msgstr"):
            msgs[msgid] = e["msgstr"]
    keys = sorted(msgs)
    ids = b"".join(k.encode() + b"\0" for k in keys)
    strs = b"".join(msgs[k].encode() + b"\0" for k in keys)
    n = len(keys)
    koffsets, voffsets, o1, o2 = [], [], 0, 0
    for k in keys:
        kb, vb = k.encode(), msgs[k].encode()
        koffsets.append((len(kb), o1))
        voffsets.append((len(vb), o2))
        o1 += len(kb) + 1
        o2 += len(vb) + 1
    keystart = 7 * 4 + 16 * n
    valuestart = keystart + len(ids)
    out = struct.pack("Iiiiiii", 0x950412DE, 0, n, 7 * 4, 7 * 4 + n * 8, 0, 0)
    out += b"".join(struct.pack("ii", ln, keystart + off) for ln, off in koffsets)
    out += b"".join(struct.pack("ii", ln, valuestart + off) for ln, off in voffsets)
    out += ids + strs
    mo = po_path.with_suffix(".mo")
    mo.write_bytes(out)
    return n


for po in (ROOT / "locale").rglob("*.po"):
    print(po.relative_to(ROOT), compile_po(po), "messages")
