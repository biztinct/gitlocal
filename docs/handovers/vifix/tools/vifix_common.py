"""Shared helpers for the VIFIX audit tools (offline, stdlib + polib).

Module scope
------------
"Ours" = a repo directory with a ``__manifest__.py`` whose name starts with one of
``pb_``, ``biz_``, ``biztinct_`` (VIFIX P1 handover, scope A) AND is not in the
server's standard addon set (``data/standard_addons.txt``, taken on 2026-10-21 from
``git -C /odoo/odoo-server ls-files addons | cut -d/ -f2 | sort -u``, the CLAUDE.md rule).
``data/installed_payobook.txt`` is ``ir_module_module`` state=installed on DB payobook
(2026-10-21); the tools mark modules that are not installed there, since nobody sees them.

Word classes (ledger VF1)
-------------------------
* ALLOW: words that legitimately stay Latin on a Vietnamese screen: brand and product
  names, file types, standard codes and acronyms, currency codes, units.
* LOANWORD: English loanwords that are common in Vietnamese business software
  (email, file, online...). They are NOT counted as mixed-language findings; they are
  listed separately so the glossary can decide each one.
* A Latin word is treated as Vietnamese-without-tone-marks when it parses as one
  Vietnamese syllable (initial + vowel nucleus + final). That keeps "trong", "thanh",
  "theo" out of the English-word findings.
"""
import os
import re
import unicodedata

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", "..", ".."))
DATA = os.path.join(HERE, "data")

OUR_PREFIXES = ("pb_", "biz_", "biztinct_")


def _read_set(name):
    path = os.path.join(DATA, name)
    if not os.path.exists(path):
        return set()
    with open(path, encoding="utf-8") as f:
        return {l.strip() for l in f if l.strip()}


STANDARD = _read_set("standard_addons.txt")
INSTALLED = _read_set("installed_payobook.txt")


def our_modules(repo=REPO):
    out = []
    for name in sorted(os.listdir(repo)):
        if not name.startswith(OUR_PREFIXES) or name in STANDARD:
            continue
        if os.path.isfile(os.path.join(repo, name, "__manifest__.py")):
            out.append(name)
    return out


def other_nonstandard_modules(repo=REPO):
    out = []
    for name in sorted(os.listdir(repo)):
        if name.startswith(OUR_PREFIXES) or name in STANDARD or name.startswith("."):
            continue
        if os.path.isfile(os.path.join(repo, name, "__manifest__.py")):
            out.append(name)
    return out


# ---------------------------------------------------------------- word classes
ALLOW = {w.lower() for w in """
payobook payai biztinct zoho excel google microsoft gmail outlook whatsapp zalo openai chatgpt
gpt tesseract voip lucide sudima rize thaco abm misa bravo sap oracle workday xero quickbooks
pdf csv xlsx xls docx json xml html api url uri id ok sms otp qr vat kpi okr sql ics ical png jpg jpeg svg zip
bhxh bhyt bhtn tncn mst cccd cmnd kpcđ kpcd ctv ncc vnd usd sgd idr thb myr khr inr eur aud gbp jpy cny
cpf sdl shg ssf epf socso eis pcb bpjs pph pf esi tds lwf hrms erp crm ios android
gross net ytd mtd utc gmt ip ssl dns www http https ai iso swift iban bic ach napas vcb vietcombank
techcombank bidv vietinbank agribank acb mbbank tpbank vpbank sacombank hdbank
singapore indonesia malaysia philippines brunei myanmar kesehatan ketenagakerjaan jht jkk jkm jp
mac windows linux chrome safari firefox edge iphone ipad calendly campuchia
ctrl cmd esc enter shift alt del backspace aa
""".split()}

LOANWORD = {w.lower() for w in """
email e-mail file online offline website web logo mail app chat link server tab menu token
password login logout cookie internet wifi video audio camera fax pin code template
portal dashboard upload download import export inbox
""".split()}

VI_CHARS = "àáạảãâầấậẩẫăằắặẳẵèéẹẻẽêềếệểễìíịỉĩòóọỏõôồốộổỗơờớợởỡùúụủũưừứựửữỳýỵỷỹđ"
VI_RE = re.compile("[" + VI_CHARS + VI_CHARS.upper() + "]")

_INIT = "(?:ngh|ng|nh|ch|gh|gi|kh|ph|qu|th|tr|b|c|d|g|h|k|l|m|n|p|r|s|t|v|x)?"
_NUC = ("(?:uyê|uya|uyu|oai|oao|oay|oeo|uây|uôi|ươi|ươu|iêu|yêu|uay|"
        "ai|ao|au|ay|âu|ây|eo|êu|ia|iê|iu|oa|oă|oe|oi|ôi|ơi|ua|uâ|uê|ui|uô|uơ|ưa|ưi|ươ|ưu|uy|yê|"
        "a|ă|â|e|ê|i|o|ô|ơ|u|ư|y|"
        "ieu|yeu|uye|uoi|uou|uu|ie|ye|uo|ue|eu)")
_FIN = "(?:ch|ng|nh|c|m|n|p|t)?"
VI_SYLLABLE_RE = re.compile("^" + _INIT + _NUC + _FIN + "$")


def strip_accents(s):
    s = s.replace("đ", "d").replace("Đ", "D")
    return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")


def looks_vietnamese_syllable(word):
    w = word.lower()
    return bool(VI_SYLLABLE_RE.match(w)) or bool(VI_SYLLABLE_RE.match(strip_accents(w)))


def has_vietnamese(s):
    return bool(VI_RE.search(s or ""))


PLACEHOLDER_RE = re.compile(
    r"%\([A-Za-z_][\w]*\)[-+ #0]*\d*(?:\.\d+)?[sdifrxXeEgGc]"   # %(name)s
    r"|%[-+#0]*\d*(?:\.\d+)?[sdif]"                                # %s %d %.2f (not "% rise")
    r"|\{\{.*?\}\}"                                                # {{ expr }}
    r"|\{[A-Za-z_][\w.]*(?:![rsa])?(?::[^{}]*)?\}"                 # {name} {0.x}
    r"|\{\d*(?::[^{}]*)?\}"                                        # {} {0}
    r"|\$\{[^}]*\}"                                                # ${expr}
)
TAG_RE = re.compile(r"<[^>]+>")
URL_RE = re.compile(r"(?:https?://|www\.)\S+|\S+@\S+\.\w+|/[\w\-./]+")
WORD_RE = re.compile(r"[A-Za-zÀ-ỹĐđ][A-Za-zÀ-ỹĐđ'’-]*")


def bare_percent(s):
    """A '%' that is neither '%%' nor a placeholder, in a string that has %-placeholders:
    Python %-formatting raises ValueError ("incomplete format") or mis-formats on it."""
    s = s or ""
    if not re.search(r"%\(|%[sdif]", s):
        return False
    rest = PLACEHOLDER_RE.sub("", s.replace("%%", ""))
    return "%" in rest


def placeholders(s):
    """Multiset of placeholders (sorted list); positional %s keep their count."""
    return sorted(m.group(0) for m in PLACEHOLDER_RE.finditer(s or "") if m.group(0) != "%%")


IDENT_RE = re.compile(
    r"\b[\w-]+(?:[._][\w-]+)+\b"        # dotted.or_snake identifiers, file names
    r"|\b\w+=\S+"                       # key=value
    r"|\bfa-[\w-]+|\bo_[\w-]+"          # icon / css classes
    r"|`[^`]*`"                         # inline code
    r"|\b(?:Google|Microsoft|Zoho|Apple)(?: [A-Z][a-z]+)+"   # product names: Google Calendar
)


def clean_text(s):
    s = (s or "").replace("%%", "")
    s = PLACEHOLDER_RE.sub(" ", s)
    s = TAG_RE.sub(" ", s)
    s = URL_RE.sub(" ", s)
    s = IDENT_RE.sub(" ", s)
    s = re.sub(r"&\w+;", " ", s)
    return s


def latin_words(s):
    """ASCII-only words of the cleaned text."""
    return [w for w in WORD_RE.findall(clean_text(s)) if w.isascii()]


def classify_word(w):
    """Return 'allow' | 'loan' | 'code' | 'vi' | 'en'."""
    lw = w.lower().strip("'’-")
    if len(lw) <= 1:
        return "allow"
    if lw in ALLOW:
        return "allow"
    if lw in LOANWORD:
        return "loan"
    if (w.isupper() and len(w) <= 6) or re.search(r"[a-z][A-Z]|_|\d", w):
        return "code"          # acronym, CamelCase or snake_case identifier
    if looks_vietnamese_syllable(lw):
        return "vi"
    return "en"


def english_words(s, min_len=4):
    return [w for w in latin_words(s) if len(w) >= min_len and classify_word(w) == "en"]


def loanwords(s):
    return [w for w in latin_words(s) if classify_word(w) == "loan"]


def same_text_is_legit(msgid):
    """True when a msgstr identical to the English needs no translation (VF1)."""
    if has_vietnamese(msgid):
        return True  # the source is already bilingual ("Bonus / Thưởng")
    words = latin_words(msgid)
    if not words:
        return True  # only placeholders, numbers, punctuation, tags
    return all(classify_word(w) in ("allow", "code", "loan") for w in words)


def norm(s):
    s = re.sub(r"\s+", " ", (s or "").strip())
    return s.rstrip(" .:…").lower()


def rel(path, repo=REPO):
    return os.path.relpath(path, repo)
