# Part of biz_debrand — portable Odoo 19 white-label layer. License LGPL-3.
"""Brand resolution + the single canonical text-rewrite used by every seam.

Everything that rewrites a user-visible string — the Python ``_()`` patch, the
QWeb tree walker, the Apps-list ``read()`` override, the data scrub and the
JavaScript runtime — goes through :func:`debrand_text` so the rules stay in one
place and behave identically on both sides of the wire.

The brand is per-database (this deployment is DB-per-tenant SaaS), so it is
cached per db name and refreshed by ``ir.config_parameter._register_hook`` on
every registry load and by ``_biz_debrand_apply_brand`` on every save.

THE PRODUCT RULE (ERRORS E3-2) IS OPT-IN AND MUST STAY THAT WAY
---------------------------------------------------------------
The vendor rules above rewrite a word nobody's *data* is called. The product
rule is the mirror image: it rewrites the name of THIS product, and a tenant
may perfectly well have a company, a partner or an employer on a payslip
genuinely named "Payobook Vietnam JSC". Renaming one of those is a silent data
corruption, and it would be far worse than the bug the rule exists to fix.

So ``debrand_text`` takes the product name as an explicit fourth argument that
defaults to ``None``, and only the seams that rewrite text coming from SOURCE
pass it:

  ON   translate_patch      a ``_()`` msgid / catalogue entry, before the args
                            are interpolated
  ON   ir_ui_view           a server-rendered QWeb template's static prose
  ON   base.get_view        a backend view arch
  ON   ir_model_fields      a field label / tooltip / selection label
  ON   ir_module_module     Apps-list text, re-imported from __manifest__.py
  ON   JS seam 1 + seam 2   ``_t()`` templates and static OWL templates

  OFF  scrub.py             STORED ROWS. This is the one that would rename a
                            customer's company.
  OFF  JS seam 3            the notification service sees the FINISHED message,
                            interpolated record names and all
  OFF  debrand_url          ``payobook.com`` is a host that resolves; rewriting
                            it invents one that does not
"""
import logging
import re
import threading
from functools import lru_cache

_logger = logging.getLogger(__name__)

DEFAULT_BRAND = "BizApp"
DEFAULT_WEBSITE = "https://example.com"

# Cheap pre-filter: skip the expensive work for the ~99.9% of strings that
# never mention the vendor at all. Deliberately loose (no word boundary).
HAS_ODOO_RE = re.compile(r"odoo", re.IGNORECASE)

# Rewrite rules, applied in this order. Earlier rules consume the shapes that
# the generic word rule must not see.
DOC_URL_RE = re.compile(r"https?://(?:www\.)?odoo\.com/documentation/?", re.IGNORECASE)
# Anchored at a label boundary so a vendor SUBDOMAIN is left intact: rewriting
# only the tail of `apps.odoo.com` would yield `apps.<brand>.com`, a host that
# does not exist. Such links are reported, not silently half-rewritten.
DOMAIN_RE = re.compile(r"(?<![.\w])(?:www\.)?odoo\.com\b", re.IGNORECASE)
BOT_RE = re.compile(r"\bodoo[\s_-]*bot\b", re.IGNORECASE)
SA_RE = re.compile(r"\bodoo\s+s\.?\s?a\.?(?![\w.])", re.IGNORECASE)

# The generic rule. It must never touch code: the surrounding-character guards
# exclude the JS namespace (``odoo.define``, ``odoo[``, ``odoo =``), module
# hints (``@odoo-module``, ``odoo-bin``) and paths (``/odoo/``, ``/odoo``).
# Mirrored character-for-character by debrandText() in the JS runtime.
WORD_RE = re.compile(
    r"(?<![.\w/-])odoo(?![\w/\[-])(?!\.\w)(?!\s*=)",
    re.IGNORECASE,
)

# Whole sentences that must be REPLACED, not word-swapped, and therefore run
# before every rule above. They point the reader at a vendor SERVICE the brand
# does not operate, so rewriting the domain would invent a help desk that never
# answers — worse than leaving the vendor name in place. Mirrored character for
# character by PHRASES in the JS runtime. See ERRORS E2-4.
PHRASES = [
    # o_spreadsheet's own crash line. The library routes its strings through
    # Odoo's _t (spreadsheet/static/src/o_spreadsheet/odoo_module.js), so the
    # sentence reaches a screen through the JS seam; the rule lives here too so
    # the two sides stay identical.
    (
        re.compile(
            r"An unexpected error occurred\.\s*"
            r"Submit a support ticket at (?:www\.)?odoo\.com/help\.?",
            re.IGNORECASE,
        ),
        "Something went wrong on our side. "
        "If it keeps happening, let your administrator know.",
    ),
    (
        re.compile(
            r"Submit a support ticket at (?:www\.)?odoo\.com/help\.?",
            re.IGNORECASE,
        ),
        "If it keeps happening, let your administrator know.",
    ),
]


# ---------------------------------------------------------------------------
# The product rule — see the module docstring for why it is opt-in per seam
# ---------------------------------------------------------------------------
# Built from the actual occurrences on this build (229 of them across pb_* and
# biz_*), not by analogy with the vendor rule. Counting the character that
# follows the product name in every source file gives:
#
#   ' ' 635   '.' 385   "'" 146   '_' 53   '<' 39   '"' 39   ',' 18   ']' 11
#   ':' 7     letter 8  '`' 5     '\' 4    '-' 3    '/' 2
#
# and the character before it: space, quote, '.', '>', '_', '@', '/', '[', '`'.
# Four shapes must survive untouched and each is held by one guard:
#
#   payobook.com, demo@payobook.com   (?!\.\w)        a host that resolves
#   payobook_template, PayobookHeader (?![\w/\[-])    db name, JS identifier
#   /payobook/..., .payobook          (?<![.\w/-])    a path, an attribute
#   Payobook-navy                     (?![\w/\[-])    a hyphenated compound
#
# Everything else — "Welcome to Payobook", "Payobook's", "[Payobook] %s",
# "…from Payobook.</span>" — is prose and is rewritten. A lowercase standalone
# `payobook` outside those shapes does not occur anywhere in the source, which
# is why the rule can afford to be case-insensitive like the vendor one.
_PRODUCT_GUARDS = r"(?![\w/\[-])(?!\.\w)(?!\s*=)"


@lru_cache(maxsize=16)
def product_rules(product, brand):
    """``(prefilter, word_rule)`` for ``product``, or ``None`` when the rule is off.

    The rule is off when no product name is configured, when it is the brand
    already (``payobook`` and ``abm``, where the rewrite would be a no-op and
    must cost nothing), or when it is too short to be a name.
    """
    product = (product or "").strip()
    brand = (brand or "").strip()
    if len(product) < 2 or product.lower() == brand.lower():
        return None
    escaped = re.escape(product)
    return (
        # One pre-filter for both families, so the hot path stays a single scan.
        re.compile(r"odoo|" + escaped, re.IGNORECASE),
        re.compile(r"(?<![.\w/-])" + escaped + _PRODUCT_GUARDS, re.IGNORECASE),
    )


def prefilter_for(brand, product=None):
    """The cheap "is there anything to do at all?" scan for a big string.

    Same question :func:`debrand_text` asks per string, hoisted out for callers
    that hold one very large one — a view arch — and want to skip parsing it.
    """
    rules = product_rules(product, brand) if product else None
    return rules[0] if rules else HAS_ODOO_RE


# db name -> (brand, website, product); refreshed on registry load and on save.
_BRAND_CACHE = {}


def website_host(website):
    """``https://payobook.com/`` -> ``payobook.com``."""
    host = re.sub(r"^https?://", "", (website or "").strip()).strip("/")
    return host or "example.com"


# ---------------------------------------------------------------------------
# ERRORS E4-6 — repairing a URL another layer has already broken
# ---------------------------------------------------------------------------
# ``web_debranding.debrand_links`` (models/ir_translation.py:27) is
#
#     re.sub(r"\bodoo.com\b", new_website, source)
#
# and ``new_website`` is a FULL URL (``https://payobook.com``), not a host. So
# every vendor link in an arch comes out with two schemes in it:
#
#     https://www.odoo.com/pricing   ->  https://www.https://payobook.com/pricing
#     href="https://apps.odoo.com/…" ->  https://apps.https://rize.payobook.com/…
#
# which is not a naming bug at all — it is a dead link on a settings screen.
# Both of web_debranding's entry points run inside our own ``super()`` calls
# (``base.get_view`` and ``ir.ui.view.get_combined_arch``), so by the time any
# biz_debrand seam sees the string the damage is already done and the repair
# belongs here, in the one rewrite every seam shares. web_debranding itself is
# gutted and OPL-1 and is never edited (ER20/ER26).
#
# The rule is "a URL prefix immediately followed by another complete URL", so
# it drops the dead prefix and keeps the real address. A URL that legitimately
# carries another one — ``?next=https://…`` — is not matched, because the
# character class stops at ``/`` and ``?``.
NESTED_URL_RE = re.compile(r"\bhttps?://[\w.\-]*(?=https?://)", re.IGNORECASE)


def repair_nested_url(text):
    """Drop the dead prefix a full-URL substitution left in front of a URL.

    Cheap-exits on the ``://`` that any such damage must contain, so it costs a
    substring scan on the overwhelming majority of strings. Returns ``text``
    unchanged (same object) when there is nothing to repair.
    """
    if not text or not isinstance(text, str) or text.count("://") < 2:
        return text
    out = NESTED_URL_RE.sub("", text)
    return out if out != text else text


def debrand_url(url, website):
    """Repoint vendor URLs at the brand's own site.

    Only the domain rules are applied — never the generic word rule — so
    ``/odoo/action-1`` (a working backend route) and ``odoocdn.com`` asset URLs
    survive untouched while a visitable ``https://odoo.com`` link does not.
    """
    # E4-6 first, and OUTSIDE the vendor pre-filter: a link web_debranding has
    # already mangled no longer contains the vendor's name at all, so the
    # pre-filter below would return early and leave it broken.
    url = repair_nested_url(url)
    if not url or not isinstance(url, str) or not HAS_ODOO_RE.search(url):
        return url
    host = website_host(website)
    doc_url = (website or DEFAULT_WEBSITE).rstrip("/") + "/documentation/"
    out = DOC_URL_RE.sub(lambda m: doc_url, url)
    return DOMAIN_RE.sub(lambda m: host, out)


def debrand_text(text, brand, website, product=None):
    """Rewrite every user-visible vendor reference in ``text``.

    Returns ``text`` unchanged (same object) when there is nothing to do, so
    callers can cheaply detect a no-op.

    ``product`` is the master product name to replace with ``brand`` — the
    opt-in rule of ERRORS E3-2. It is **off unless a caller asks for it**, and
    only a caller rewriting SOURCE text may ask; the module docstring lists the
    seams that do and the seams that must not.
    """
    if not text or not isinstance(text, str):
        return text
    # E4-6, and it has to happen BEFORE the pre-filter: a link web_debranding
    # has already mangled carries no vendor name any more, so the pre-filter
    # would return early and leave a dead URL on the screen. This is the shape
    # that reaches a PROSE attribute — `placeholder="https://www.odoo.com"` —
    # rather than a URL one; debrand_url covers the other half.
    repaired = repair_nested_url(text)
    rules = product_rules(product, brand) if product else None
    if not (rules[0] if rules else HAS_ODOO_RE).search(repaired):
        return repaired
    text = repaired
    host = website_host(website)
    doc_url = (website or DEFAULT_WEBSITE).rstrip("/") + "/documentation/"
    out = text
    for pattern, replacement in PHRASES:
        out = pattern.sub(replacement, out)
    out = DOC_URL_RE.sub(lambda m: doc_url, out)
    out = DOMAIN_RE.sub(lambda m: host, out)
    out = BOT_RE.sub(lambda m: brand, out)
    out = SA_RE.sub(lambda m: brand, out)
    out = WORD_RE.sub(lambda m: brand, out)
    if rules:
        out = rules[1].sub(lambda m: brand, out)
    return out


# ---------------------------------------------------------------------------
# Brand resolution
# ---------------------------------------------------------------------------
def brand_for_env(env):
    """Read the brand straight from the database. Never cached here."""
    icp = env["ir.config_parameter"].sudo()
    brand = (
        icp.get_param("biz_debrand.brand_name")
        or icp.get_param("web_debranding.new_name")
        or DEFAULT_BRAND
    ).strip()
    website = (
        icp.get_param("biz_debrand.brand_website")
        or icp.get_param("web_debranding.new_website")
        or DEFAULT_WEBSITE
    ).strip()
    return brand, website


def product_for_env(env):
    """The master product name this database should rewrite, or ``''``.

    Empty by default, which is the whole rollback for ERRORS E3-2: unset, not a
    single string anywhere changes. Set it only on a database whose brand is
    NOT the master product name — on ``payobook`` and ``abm`` the two are the
    same word and ``product_rules`` turns the rule off for nothing.
    """
    return (
        env["ir.config_parameter"].sudo().get_param("biz_debrand.product_name") or ""
    ).strip()


def source_brand(env):
    """``(brand, website, product)`` for a seam that rewrites SOURCE text.

    The third member is what makes this different from :func:`brand_for_env`,
    and calling this function is a seam declaring that the text it is about to
    rewrite came from a template, a manifest or a ``_()`` call — never from a
    row a customer typed. See the module docstring.
    """
    brand, website = brand_for_env(env)
    return brand, website, product_for_env(env)


def cache_brand(env):
    """Refresh the process cache for this env's database."""
    try:
        triple = source_brand(env)
    except Exception:
        _logger.warning("biz_debrand: could not resolve brand", exc_info=True)
        return None
    _BRAND_CACHE[env.cr.dbname] = triple
    return triple


def invalidate(dbname=None):
    if dbname:
        _BRAND_CACHE.pop(dbname, None)
    else:
        _BRAND_CACHE.clear()


def current_brand():
    """``(brand, website, product)`` for the calling thread's database, or ``None``.

    Used by the ``_()`` patch, which has no ``env``. Deliberately **fails
    open**: if the cache has not been primed yet (very early boot, an odd
    thread) it returns ``None`` and the caller leaves the string untouched
    rather than opening a cursor on a hot path.
    """
    try:
        from odoo.http import request

        db = request.db if request else None
    except Exception:
        db = None
    if not db:
        db = getattr(threading.current_thread(), "dbname", None)
    if not db:
        return None
    return _BRAND_CACHE.get(db)


# ---------------------------------------------------------------------------
# XML / QWeb tree walking
# ---------------------------------------------------------------------------
# Attributes that hold prose a human reads. Everything else — and anything
# starting with ``t-`` — is an expression or a technical value and is skipped.
PROSE_ATTRS = frozenset(
    {
        "alt",
        "aria-label",
        "aria-placeholder",
        "confirm",
        "content",
        "data-tooltip",
        "help",
        "label",
        "placeholder",
        "string",
        "title",
    }
)

# Attributes holding a URL. Only the domain rules apply to these — see
# debrand_url — so a clickable https://odoo.com link is repointed at the brand
# while backend routes and CDN asset URLs keep working.
URL_ATTRS = frozenset({"href", "src", "action", "data-url", "data-src"})

# Element text we must never touch: executable/stylistic payloads, and code
# samples — help panels quote real Python (`from odoo import models`) and JS,
# which the generic word rule would happily rewrite into something that no
# longer runs.
OPAQUE_TAGS = frozenset({"script", "style", "code", "pre", "samp", "kbd"})

# The author's own opt-out: ``data-biz-brand="keep"`` on an element leaves that
# element AND everything inside it exactly as written.
#
# It exists because E3-2's product rule cannot tell two different sentences
# apart. "Welcome to Payobook" on a tenant's screen is the bug. "Powered by
# Payobook" in that same tenant's footer is a deliberate statement about who
# built the platform, and rewriting it to "Powered by Rize" is not a fix, it is
# nonsense on the page. Without a hatch the only remedy for one such line would
# be turning the whole rule off for the database — a dead end.
#
# Narrow on purpose: one attribute, one value, whole subtree, no expression
# evaluated. Mirrored by the tree walker in biz_debrand_runtime.js.
KEEP_ATTR = "data-biz-brand"
KEEP_VALUE = "keep"


def debrand_tree(element, brand, website, product=None):
    """In-place rewrite of prose inside a parsed template/view tree.

    Only static template text and whitelisted prose attributes are touched.
    Data interpolated at render time arrives through ``t-out``/``t-esc``
    expressions, which are attributes we skip — so a customer record actually
    named "Odoo Ltd" is never rewritten.

    That same skip is what makes a tree walk safe to run the product rule over:
    everything it reaches is template SOURCE, and a company genuinely called
    "Payobook Vietnam JSC" arrives through an expression this walker does not
    read.

    An element carrying ``data-biz-brand="keep"`` is left alone along with
    everything inside it — see :data:`KEEP_ATTR`.
    """
    changed = False
    # An explicit stack rather than ``element.iter()``: a KEEP_ATTR element has
    # to take its whole SUBTREE out of the walk, and iter() is flat.
    stack = [element]
    while stack:
        el = stack.pop()
        tag = el.tag
        if not isinstance(tag, str):  # comments, processing instructions
            continue
        # ``tail`` is the text that follows this element's closing tag, which
        # belongs to the PARENT's content — so it is rewritten either way, even
        # for an element whose own subtree is kept.
        if el.tail:
            new = debrand_text(el.tail, brand, website, product)
            if new is not el.tail:
                el.tail = new
                changed = True
        if el.get(KEEP_ATTR) == KEEP_VALUE:
            continue  # the author said this says what it means
        stack.extend(el)
        opaque = tag.rsplit("}", 1)[-1].lower() in OPAQUE_TAGS
        if not opaque and el.text:
            new = debrand_text(el.text, brand, website, product)
            if new is not el.text:
                el.text = new
                changed = True
        for name, value in list(el.attrib.items()):
            if name.startswith("t-"):
                continue  # QWeb expression: rewriting it would break the render
            if name in PROSE_ATTRS:
                new = debrand_text(value, brand, website, product)
            elif name in URL_ATTRS:
                new = debrand_url(value, website)
            else:
                continue
            if new is not value:
                el.set(name, new)
                changed = True
    return changed
