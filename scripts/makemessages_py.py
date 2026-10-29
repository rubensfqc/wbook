"""Pure-Python message extraction (no GNU gettext needed) → locale/en/LC_MESSAGES/django.po.

Extracts _("..."), gettext("..."), gettext_lazy("..."), _l("..."), ngettext from .py files and
{% translate %}, {% blocktranslate %} (with count/plural) and _("...") from templates. Existing translations are kept.
Usage: python scripts/makemessages_py.py
"""

import ast
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PO = ROOT / "locale" / "en" / "LC_MESSAGES" / "django.po"
FUNCS = {"_", "gettext", "gettext_lazy", "_l", "pgettext"}


def py_strings(path):
    out = []
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except SyntaxError:
        return out
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            name = getattr(node.func, "id", None) or getattr(node.func, "attr", None)
            if name in FUNCS and node.args and isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str):
                out.append((node.args[0].value, None))
            if name in ("ngettext", "ngettext_lazy") and len(node.args) >= 2 and all(isinstance(a, ast.Constant) for a in node.args[:2]):
                out.append((node.args[0].value, node.args[1].value))
    return out


T_TRANS = re.compile(r"""\{%\s*(?:translate|trans)\s+(?:"((?:[^"\\]|\\.)*)"|'((?:[^'\\]|\\.)*)')""")
T_UNDERSCORE = re.compile(r"""_\(\s*"((?:[^"\\]|\\.)*)"\s*\)""")
T_BLOCK = re.compile(r"\{%\s*blocktrans(?:late)?\b(.*?)%\}(.*?)\{%\s*endblocktrans(?:late)?\s*%\}", re.S)
VAR = re.compile(r"\{\{\s*(\w+)\s*\}\}")


def _block_text(s):
    return VAR.sub(lambda m: f"%({m.group(1)})s", s.replace("%", "%%"))


def tpl_strings(path):
    text = path.read_text(encoding="utf-8")
    out = []
    for m in T_TRANS.finditer(text):
        out.append(((m.group(1) if m.group(1) is not None else m.group(2)), None))
    for m in T_UNDERSCORE.finditer(text):
        out.append((m.group(1), None))
    for m in T_BLOCK.finditer(text):
        args, body = m.group(1), m.group(2)
        trimmed = "trimmed" in args
        if "{% plural %}" in body:
            sing, plur = body.split("{% plural %}", 1)
        else:
            sing, plur = body, None
        def norm(s, trimmed=trimmed):
            s = _block_text(s)
            return " ".join(s.split()) if trimmed else s
        out.append((norm(sing), norm(plur) if plur is not None else None))
    return out


def esc(s):
    return s.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n").replace("\t", "\\t")


def unesc(s):
    return s.encode("latin-1", "backslashescape").decode("unicode_escape").encode("latin-1").decode("utf-8") if "\\" in s else s


def read_po(path):
    entries, cur, key = {}, {}, None
    if not path.exists():
        return entries
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            if cur.get("msgid") is not None:
                entries[(cur["msgid"], cur.get("msgid_plural"))] = cur
            cur, key = {}, None
            continue
        m = re.match(r'^(msgid|msgid_plural|msgstr(?:\[\d\])?)\s+"(.*)"$', line)
        if m:
            key = m.group(1)
            cur[key] = _po_unescape(m.group(2))
        elif line.startswith('"') and key:
            cur[key] += _po_unescape(line[1:-1])
    if cur.get("msgid") is not None:
        entries[(cur["msgid"], cur.get("msgid_plural"))] = cur
    return entries


def _po_unescape(s):
    return s.replace('\\"', '"').replace("\\n", "\n").replace("\\t", "\t").replace("\\\\", "\\")


def main():
    found = {}
    for p in sorted((ROOT / "apps").rglob("*.py")):
        if "migrations" in p.parts:
            continue
        for s, pl in py_strings(p):
            found.setdefault((s, pl), set()).add(str(p.relative_to(ROOT)))
    for p in sorted((ROOT / "templates").rglob("*.html")):
        for s, pl in tpl_strings(p):
            found.setdefault((s, pl), set()).add(str(p.relative_to(ROOT)))
    old = read_po(PO)
    lines = [
        'msgid ""', 'msgstr ""',
        '"Content-Type: text/plain; charset=UTF-8\\n"', '"Language: en\\n"',
        '"Plural-Forms: nplurals=2; plural=(n != 1);\\n"', "",
    ]
    missing = 0
    for (s, pl), files in sorted(found.items(), key=lambda kv: kv[0][0]):
        if not s:
            continue
        prev = old.get((s, pl), {})
        lines.append("#: " + " ".join(sorted(files))[:200])
        if "%(" in s:
            lines.append("#, python-format")
        lines.append(f'msgid "{esc(s)}"')
        if pl is not None:
            lines.append(f'msgid_plural "{esc(pl)}"')
            s0, s1 = prev.get("msgstr[0]", ""), prev.get("msgstr[1]", "")
            missing += not (s0 and s1)
            lines += [f'msgstr[0] "{esc(s0)}"', f'msgstr[1] "{esc(s1)}"']
        else:
            t = prev.get("msgstr", "")
            missing += not t
            lines.append(f'msgstr "{esc(t)}"')
        lines.append("")
    PO.parent.mkdir(parents=True, exist_ok=True)
    PO.write_text("\n".join(lines), encoding="utf-8")
    print(f"{len(found)} strings, {missing} untranslated → {PO.relative_to(ROOT)}")
    return missing


if __name__ == "__main__":
    missing = main()
    sys.exit(1 if missing and "--check" in sys.argv else 0)
