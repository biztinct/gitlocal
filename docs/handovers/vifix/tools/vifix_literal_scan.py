#!/usr/bin/env python3
"""VIFIX P1 scope B: user-facing English that never reaches the Vietnamese screen (offline).

Run:  python3 docs/handovers/vifix/tools/vifix_literal_scan.py [--json out.json] [--md out.md]

The translation map a screen uses is global: the web client loads the code terms of every
installed module and looks a string up by its English text. So a string is "covered" when
some module of ours has it as an effective msgid (after the .pot merge, vifix_po_scan) with
a non-empty msgstr and the right marker (odoo-javascript for JS/QWeb, odoo-python for Python).

Finding classes (each row: module, file:line, English, class):
  xml_text        QWeb text node in static/src/**/*.xml with no covered msgid
  xml_attr        translatable attribute (title, placeholder, aria-label, alt, label, string,
                  help, data-tooltip, confirm...) with no covered msgid
  xml_expr        an English string literal inside a template expression (t-esc, t-out,
                  t-att-*, t-attf-*, t-if...). Never extracted: English in every language
  js_unwrapped    an English UI string in static/src/**/*.js that is not inside _t()
  js_wrapped_uncovered   _t("...") whose text has no covered msgid (.pot needs regenerating
                  and translating)
  js_concat       a sentence glued from pieces (`_t("a") + x + " b"`, template literal with
                  English and ${...}): can never be translated whole
  py_unwrapped    an English UI string in Python not inside _() / _lt(): dict values under UI
                  keys (label, title, name, hint, text, message, sentence, help, description...),
                  and the first argument of UserError/ValidationError/AccessError
  py_wrapped_uncovered   _("...") with no covered msgid

"English UI string": has an English word of >= 3 letters (vifix_common.classify_word) and is
not an identifier, class list, selector, path, model name, format code or log message.
"""
import argparse
import ast
import collections
import json
import os
import re
import sys
import xml.etree.ElementTree as ET

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import vifix_common as C  # noqa: E402
import vifix_po_scan as PS  # noqa: E402

TRANSLATED_ATTRS = {"string", "add-label", "help", "sum", "avg", "confirm", "placeholder", "alt", "title",
                    "aria-label", "aria-keyshortcuts", "aria-placeholder", "aria-roledescription",
                    "aria-valuetext", "value_label", "data-tooltip", "label", "cancel-label", "confirm-label"}
UI_KEYS = {"label", "title", "name", "hint", "text", "message", "sentence", "help", "description", "placeholder",
           "tooltip", "caption", "subtitle", "heading", "body", "empty", "summary", "note", "tip", "line", "lead",
           "kicker", "cta", "button", "action_label", "headline", "detail", "why", "short", "long", "chip",
           "badge", "status_label", "state_label", "verb", "blurb", "question", "answer", "reason", "warning",
           "error", "info", "success", "tagline", "plural", "singular", "unit", "suffix", "prefix"}
USER_ERRORS = {"UserError", "ValidationError", "AccessError", "RedirectWarning", "MissingError", "AccessDenied"}


# ---------------------------------------------------------------------------- coverage
EXCLUDED = {"pb_learn"}  # Learn content is LEARNREV's (VIFIX non-goal); scanned there


def coverage():
    """msgid (stripped) -> set of markers with a non-empty msgstr: 'js' (any module: the web
    client looks in the calling module, then in every loaded module, standard ones included,
    see web/static/src/core/l10n/translation.js), 'py:<module>' (Python _() reads only the
    calling module's file, odoo/tools/translate.py get_python_translations(module, lang)),
    'model'."""
    cov = collections.defaultdict(set)
    std = os.path.join(C.DATA, "standard_js_terms_vi.json")
    if os.path.exists(std):
        for t in json.load(open(std, encoding="utf-8")):
            cov[t].add("js")
    for m in C.our_modules():
        po = os.path.join(C.REPO, m, "i18n", "vi_VN.po")
        if not os.path.exists(po):
            continue
        pot = os.path.join(C.REPO, m, "i18n", m + ".pot")
        entries, _dropped, _ = PS.effective_entries(po, pot if os.path.exists(pot) else None)
        for e in entries:
            if not e.msgstr.strip() or PS.check_markers(e) and any(p.startswith("crash") for p in PS.check_markers(e)):
                continue
            comment = e.comment or ""
            for occ, _ in e.occurrences:
                if occ.startswith("code:"):
                    if "odoo-javascript" in comment:
                        cov[e.msgid.strip()].add("js")
                    if "odoo-python" in comment:
                        cov[e.msgid.strip()].add("py:" + m)
                elif occ.startswith(("model:", "model_terms:")):
                    cov[e.msgid.strip()].add("model")
    return cov


# ---------------------------------------------------------------------------- heuristics
IDENT_ONLY = re.compile(r"^[\w.\-/:#\[\]=>*~^$|()'\"@!?,+ ]*$")


def looks_ui(s, key=None):
    """English UI text, not code."""
    t = (s or "").strip()
    if len(t) < 3 or not re.search(r"[A-Za-z]{3}", t):
        return False
    if re.match(r"^(https?:|/|\.|#|\[|@|mailto:|data:|tel:)", t) or t.startswith(("o_", "fa-", "fa ", "btn", "pb", "biz")):
        return False
    if re.fullmatch(r"[a-z0-9_.\-]+(\s+[a-z0-9_.\-]+)*", t) and ("-" in t or "_" in t or "." in t):
        return False  # class lists, snake_case, dotted names, kebab-case
    if re.fullmatch(r"[a-z]+(\.[a-z_]+)+", t) or re.fullmatch(r"[A-Z_]{2,}", t):
        return False
    if re.search(r"[{};]|=>|\)\s*\{|\bfunction\b|\breturn\b|^\w+\(", t):
        return False
    if re.fullmatch(r"[%A-Za-z/\-.: ]*(YYYY|MM|DD|HH|mm|ss|yyyy|LLL|dd)[%A-Za-z/\-.: ]*", t):
        return False
    words = C.latin_words(t)
    en = [w for w in words if len(w) >= 3 and C.classify_word(w) == "en"]
    if not en:
        return False
    if " " in t or (t[0].isupper() and t[1:2].islower()) or (key and key in UI_KEYS):
        return True
    return False


# ---------------------------------------------------------------------------- JS tokenizer
JS_TOKEN = re.compile(r"""
    (?P<lc>//[^\n]*) | (?P<bc>/\*.*?\*/) |
    (?P<s>'(?:\\.|[^'\\\n])*'|"(?:\\.|[^"\\\n])*") |
    (?P<tl>`(?:\\.|[^`\\])*`)
""", re.S | re.X)


def js_unescape(lit):
    body = lit[1:-1]
    try:
        return bytes(body, "utf-8").decode("unicode_escape").encode("latin-1").decode("utf-8")
    except Exception:
        return body.replace("\\'", "'").replace('\\"', '"').replace("\\n", "\n")


SKIP_CALL = re.compile(r"(console\.\w+|_logger\.\w+|querySelector(All)?|addEventListener|removeEventListener|classList\.\w+|"
                       r"useService|registry\.category|\.category|\.add|\.get|\.call|rpc|orm\.\w+|import|require|"
                       r"new Error|new RegExp|RegExp|setAttribute|getAttribute|closest|matches|t-name|loadJS|loadCSS|"
                       r"\.startsWith|\.endsWith|\.includes|\.split|\.join|\.replace|\.indexOf|\.test|\.match|"
                       r"sessionStorage\.\w+|localStorage\.\w+|\.dispatchEvent|CustomEvent|Event|\.on|\.off|"
                       r"\.trigger|bus\.\w+|env\.services\.\w+|\.notify|doAction|\.navigate|redirect|"
                       r"Date|parseISO|DateTime\.\w+|toFormat|format|luxon\.\w+|markup|\.has|\.delete|\.set|"
                       r"getItem|setItem|removeItem|createElement|key|keys|prop|field|fields)\s*\(\s*$")


def _js_literals(src):
    """String literals (comments skipped), with chains `"a" + "b"` merged into one."""
    toks = []
    for m in JS_TOKEN.finditer(src):
        if m.group("lc") or m.group("bc"):
            continue
        lit = m.group("s") or m.group("tl")
        tl = bool(m.group("tl"))
        toks.append([m.start(), m.end(), js_unescape(lit) if not tl else lit[1:-1], tl])
    merged = []
    for t in toks:
        if merged and not t[3] and not merged[-1][3] and re.fullmatch(r"\s*\+\s*", src[merged[-1][1]:t[0]]):
            merged[-1][1] = t[1]
            merged[-1][2] += t[2]
        else:
            merged.append(t)
    return merged


NOT_TEXT = re.compile(r'="|<[a-z/]|\[data-|^[.#\[]|\bpx\b.*\b(sans|serif|system-ui)|^\s*[a-z-]+\s*:\s*[^ ]+;'
                      r'|^\((prefers-|max-|min-|orientation)')


def scan_js(path, module, cov, out):
    src = open(path, encoding="utf-8", errors="replace").read()
    rel = C.rel(path)
    for start, end, text, tl in _js_literals(src):
        line = src.count("\n", 0, start) + 1
        before = src[max(0, start - 80):start]
        after = src[end:end + 30]
        if NOT_TEXT.search(text):
            continue
        wrapped = re.search(r"\b_l?t\(\s*$", before)
        if tl and "${" in text:
            static = re.sub(r"\$\{[^}]*\}", " ", text)
            if looks_ui(static):
                out.append(dict(module=module, file=rel, line=line, cls="js_concat", text=text.strip()[:200]))
            continue
        if re.match(r"^\s*(import|export)\b", src[src.rfind("\n", 0, start) + 1:start]):
            continue
        if SKIP_CALL.search(before) and not wrapped:
            continue
        keym = re.search(r"([A-Za-z_$][\w$]*)\s*:\s*$", before)
        key = keym.group(1) if keym else None
        if re.search(r"(\.|\[)\s*$", before) or re.match(r"\s*(===|!==|==|!=)", after) \
                or re.search(r"(===|!==|==|!=|case)\s*$", before):
            continue  # property access, object key or a comparison: an identifier, not text
        if not looks_ui(text, key):
            continue
        glued = re.match(r"\s*\)?\s*\+\s*[\w(]", after) or re.search(r"[\w)]\s*\+\s*$", before)
        if wrapped:
            if "js" not in cov.get(text.strip(), ()):
                out.append(dict(module=module, file=rel, line=line, cls="js_wrapped_uncovered", text=text.strip()))
            if re.match(r"\s*\)\s*\+", after) or re.search(r"\+\s*_l?t\(\s*$", before):
                out.append(dict(module=module, file=rel, line=line, cls="js_concat", text=text.strip()))
            continue
        if glued:
            out.append(dict(module=module, file=rel, line=line, cls="js_concat", text=text.strip()))
            continue
        out.append(dict(module=module, file=rel, line=line, cls="js_unwrapped", text=text.strip(), key=key or ""))


# ---------------------------------------------------------------------------- QWeb XML
EXPR_ATTR = re.compile(r"^(t-esc|t-out|t-raw|t-if|t-elif|t-set|t-value|t-att-[\w-]+|t-attf-[\w-]+|t-att|t-props|t-call-context)$")
STR_IN_EXPR = re.compile(r"'((?:\\.|[^'\\])*)'|\"((?:\\.|[^\"\\])*)\"")


def _line_index(src):
    starts = [0]
    for i, ch in enumerate(src):
        if ch == "\n":
            starts.append(i + 1)
    return starts


def scan_xml(path, module, cov, out):
    src = open(path, encoding="utf-8", errors="replace").read()
    rel = C.rel(path)
    try:
        root = ET.fromstring(src)
    except ET.ParseError as e:
        out.append(dict(module=module, file=rel, line=0, cls="xml_parse_error", text=str(e)))
        return
    # ElementTree has no line numbers: find the text in the source for a line number.
    cursor = {"pos": 0}

    def line_of(needle):
        if not needle:
            return 0
        i = src.find(needle, cursor["pos"])
        if i < 0:
            i = src.find(needle)
        if i < 0:
            return 0
        cursor["pos"] = i
        return src.count("\n", 0, i) + 1

    def covered(t):
        return "js" in cov.get(t.strip(), ())

    def walk(el, in_untranslated=False):
        tag = el.tag if isinstance(el.tag, str) else ""
        untrans = in_untranslated or el.get("t-translation") == "off" or tag in ("script", "style", "code", "pre")
        for k, v in el.attrib.items():
            if k in TRANSLATED_ATTRS and not untrans and v.strip() and looks_ui(v, "label"):
                if not covered(v):
                    out.append(dict(module=module, file=rel, line=line_of(v), cls="xml_attr", attr=k, text=v.strip()))
            elif EXPR_ATTR.match(k) or (k.startswith("t-att") ):
                if k.startswith("t-attf-"):
                    static = re.sub(r"\{\{.*?\}\}|#\{.*?\}", " ", v)
                    if k[7:] in TRANSLATED_ATTRS and looks_ui(static, "label"):
                        out.append(dict(module=module, file=rel, line=line_of(v), cls="xml_expr", attr=k, text=v.strip()))
                    # and literals inside the {{ }} parts
                    exprs = " ".join(re.findall(r"\{\{(.*?)\}\}|#\{(.*?)\}", v) and
                                     [a or b for a, b in re.findall(r"\{\{(.*?)\}\}|#\{(.*?)\}", v)])
                else:
                    exprs = v
                for mm in STR_IN_EXPR.finditer(exprs or ""):
                    lit = mm.group(1) or mm.group(2) or ""
                    pre, post = exprs[:mm.start()], exprs[mm.end():]
                    if re.search(r"(===|!==|==|!=|\b(ic|icon|iconSvg|svg|lucide)\(\s*)\s*$", pre) or \
                            re.match(r"\s*(===|!==|==|!=|:)", post) and not re.search(r"\?\s*$", pre) or \
                            re.search(r"\b_t\(\s*$", pre) or NOT_TEXT.search(lit) or k == "t-set":
                        continue
                    if looks_ui(lit):
                        out.append(dict(module=module, file=rel, line=line_of(lit), cls="xml_expr", attr=k, text=lit.strip()))
        texts = [el.text] + [c.tail for c in el]
        for t in texts:
            if not t or untrans or not t.strip():
                continue
            tt = re.sub(r"\s+", " ", t).strip()
            if looks_ui(tt) and not covered(tt) and not covered(t.strip()):
                out.append(dict(module=module, file=rel, line=line_of(t.strip()[:40]), cls="xml_text", text=tt))
        for c in el:
            walk(c, untrans)

    walk(root)


# ---------------------------------------------------------------------------- Python
class PyVisitor(ast.NodeVisitor):
    def __init__(self, module, rel, cov, out):
        self.module, self.rel, self.cov, self.out = module, rel, cov, out
        self.wrapped = set()

    def _is_tr(self, node):
        return isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in ("_", "_lt") \
            or isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "_"

    def visit_Call(self, node):
        if self._is_tr(node) and node.args and isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str):
            s = node.args[0].value
            self.wrapped.add(id(node.args[0]))
            if looks_ui(s, "label") and ("py:" + self.module) not in self.cov.get(s.strip(), ()):
                self.out.append(dict(module=self.module, file=self.rel, line=node.lineno, cls="py_wrapped_uncovered", text=s.strip()))
        name = node.func.id if isinstance(node.func, ast.Name) else (node.func.attr if isinstance(node.func, ast.Attribute) else "")
        if name in USER_ERRORS and node.args:
            a0 = node.args[0]
            if isinstance(a0, ast.Constant) and isinstance(a0.value, str) and looks_ui(a0.value, "message"):
                self.out.append(dict(module=self.module, file=self.rel, line=node.lineno, cls="py_unwrapped",
                                     text=a0.value.strip(), key=name))
            elif isinstance(a0, ast.JoinedStr):
                static = "".join(v.value for v in a0.values if isinstance(v, ast.Constant))
                if looks_ui(static, "message"):
                    self.out.append(dict(module=self.module, file=self.rel, line=node.lineno, cls="py_unwrapped",
                                         text=static.strip(), key=name + " f-string"))
        self.generic_visit(node)

    def visit_Dict(self, node):
        for k, v in zip(node.keys, node.values):
            if isinstance(k, ast.Constant) and isinstance(k.value, str) and k.value in UI_KEYS:
                if isinstance(v, ast.Constant) and isinstance(v.value, str) and looks_ui(v.value, k.value):
                    self.out.append(dict(module=self.module, file=self.rel, line=v.lineno, cls="py_unwrapped",
                                         text=v.value.strip(), key=k.value))
                elif isinstance(v, ast.JoinedStr):
                    static = "".join(x.value for x in v.values if isinstance(x, ast.Constant))
                    if looks_ui(static, k.value):
                        self.out.append(dict(module=self.module, file=self.rel, line=v.lineno, cls="py_unwrapped",
                                             text=static.strip(), key=k.value + " f-string"))
        self.generic_visit(node)

    def visit_keyword(self, node):
        if node.arg in UI_KEYS and isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
            # fields.Char(string="..") are model terms: extracted automatically; skip "string"/"help".
            pass
        self.generic_visit(node)


def scan_py(path, module, cov, out):
    src = open(path, encoding="utf-8", errors="replace").read()
    try:
        tree = ast.parse(src)
    except SyntaxError as e:
        out.append(dict(module=module, file=C.rel(path), line=e.lineno or 0, cls="py_parse_error", text=str(e)))
        return
    PyVisitor(module, C.rel(path), cov, out).visit(tree)


# ---------------------------------------------------------------------------- driver
def iter_files(module):
    base = os.path.join(C.REPO, module)
    for root, dirs, files in os.walk(base):
        dirs[:] = sorted(d for d in dirs if d not in ("tests", "lib", "__pycache__", "node_modules", "migrations", "i18n"))
        for f in sorted(files):
            p = os.path.join(root, f)
            r = os.path.relpath(p, base)
            if f.endswith(".js") and r.startswith("static/src") and not f.endswith((".test.js", ".min.js")):
                yield "js", p
            elif f.endswith(".xml") and r.startswith("static/src"):
                yield "xml", p
            elif f.endswith(".py") and not f.startswith("test_") and f != "__manifest__.py" \
                    and not r.startswith(("static", "tests")):
                yield "py", p


def scan():
    cov = coverage()
    rows = []
    for m in C.our_modules():
        if m in EXCLUDED:
            continue
        for kind, p in iter_files(m):
            if kind == "js":
                scan_js(p, m, cov, rows)
            elif kind == "xml":
                scan_xml(p, m, cov, rows)
            else:
                scan_py(p, m, cov, rows)
    # de-duplicate (same file, line, class, text)
    seen, uniq = set(), []
    for r in rows:
        k = (r["file"], r["line"], r["cls"], r["text"])
        if k not in seen:
            seen.add(k)
            r["installed"] = r["module"] in C.INSTALLED
            uniq.append(r)
    uniq.sort(key=lambda r: (r["module"], r["file"], r["line"], r["cls"], r["text"]))
    return uniq


CLASSES = ["xml_text", "xml_attr", "xml_expr", "js_unwrapped", "js_wrapped_uncovered", "js_concat",
           "py_unwrapped", "py_wrapped_uncovered", "xml_parse_error", "py_parse_error"]


def to_md(rows, limit=60):
    out = ["# VIFIX P1 — unextracted / untranslated literal scan (generated by vifix_literal_scan.py)", ""]
    inst = [r for r in rows if r["installed"]]
    out += ["Findings: %d (%d in modules installed on payobook)." % (len(rows), len(inst)), "",
            "| Class | Findings | Installed | Modules |", "|---|---|---|---|"]
    for c in CLASSES:
        rr = [r for r in rows if r["cls"] == c]
        if rr:
            out.append("| %s | %d | %d | %d |" % (c, len(rr), len([r for r in rr if r["installed"]]), len({r["module"] for r in rr})))
    per = collections.defaultdict(collections.Counter)
    for r in rows:
        per[r["module"]][r["cls"]] += 1
    out += ["", "## Per module (installed modules first, by total)", "",
            "| Module | Installed | Total | " + " | ".join(CLASSES[:8]) + " |", "|---|---|---|" + "---|" * 8]
    for m, cnt in sorted(per.items(), key=lambda kv: (not (kv[0] in C.INSTALLED), -sum(kv[1].values()), kv[0])):
        out.append("| %s | %s | %d | %s |" % (m, "yes" if m in C.INSTALLED else "no", sum(cnt.values()),
                                              " | ".join(str(cnt.get(c, 0)) for c in CLASSES[:8])))
    out += ["", "## First %d findings per class (installed modules)" % limit]
    for c in CLASSES:
        rr = [r for r in inst if r["cls"] == c]
        if not rr:
            continue
        out += ["", "### %s (%d)" % (c, len(rr)), "", "| Module | File:line | English |", "|---|---|---|"]
        for r in rr[:limit]:
            out.append("| %s | %s:%s | %s |" % (r["module"], r["file"], r["line"],
                                                 PS.short(r["text"], 110).replace("|", "\\|")))
    return "\n".join(out) + "\n"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--json")
    ap.add_argument("--md")
    a = ap.parse_args()
    rows = scan()
    if a.json:
        json.dump(rows, open(a.json, "w", encoding="utf-8"), ensure_ascii=False, indent=1, sort_keys=True)
    md = to_md(rows)
    if a.md:
        open(a.md, "w", encoding="utf-8").write(md)
    else:
        sys.stdout.write(md)


if __name__ == "__main__":
    main()
