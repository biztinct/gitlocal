# Part of biz_debrand — portable Odoo 19 white-label layer. License LGPL-3.
"""Brand resolution + the single canonical text-rewrite used by every seam.

Everything that rewrites a user-visible string — the Python ``_()`` patch, the
QWeb tree walker, the Apps-list ``read()`` override, the data scrub and the
JavaScript runtime — goes through :func:`debrand_text` so the rules stay in one
place and behave identically on both sides of the wire.

The brand is per-database (this deployment is DB-per-tenant SaaS), so it is
cached per db name and refreshed by ``ir.config_parameter._register_hook`` on
every registry load and by ``_biz_debrand_apply_brand`` on every save.
"""
import logging
import re
import threading

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

# db name -> (brand, website); refreshed on registry load and on save.
_BRAND_CACHE = {}


def website_host(website):
    """``https://payobook.com/`` -> ``payobook.com``."""
    host = re.sub(r"^https?://", "", (website or "").strip()).strip("/")
    return host or "example.com"


def debrand_url(url, website):
    """Repoint vendor URLs at the brand's own site.

    Only the domain rules are applied — never the generic word rule — so
    ``/odoo/action-1`` (a working backend route) and ``odoocdn.com`` asset URLs
    survive untouched while a visitable ``https://odoo.com`` link does not.
    """
    if not url or not isinstance(url, str) or not HAS_ODOO_RE.search(url):
        return url
    host = website_host(website)
    doc_url = (website or DEFAULT_WEBSITE).rstrip("/") + "/documentation/"
    out = DOC_URL_RE.sub(lambda m: doc_url, url)
    return DOMAIN_RE.sub(lambda m: host, out)


def debrand_text(text, brand, website):
    """Rewrite every user-visible vendor reference in ``text``.

    Returns ``text`` unchanged (same object) when there is nothing to do, so
    callers can cheaply detect a no-op.
    """
    if not text or not isinstance(text, str) or not HAS_ODOO_RE.search(text):
        return text
    host = website_host(website)
    doc_url = (website or DEFAULT_WEBSITE).rstrip("/") + "/documentation/"
    out = DOC_URL_RE.sub(lambda m: doc_url, text)
    out = DOMAIN_RE.sub(lambda m: host, out)
    out = BOT_RE.sub(lambda m: brand, out)
    out = SA_RE.sub(lambda m: brand, out)
    out = WORD_RE.sub(lambda m: brand, out)
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


def cache_brand(env):
    """Refresh the process cache for this env's database."""
    try:
        pair = brand_for_env(env)
    except Exception:
        _logger.warning("biz_debrand: could not resolve brand", exc_info=True)
        return None
    _BRAND_CACHE[env.cr.dbname] = pair
    return pair


def invalidate(dbname=None):
    if dbname:
        _BRAND_CACHE.pop(dbname, None)
    else:
        _BRAND_CACHE.clear()


def current_brand():
    """Brand for the database of the calling thread, or ``None``.

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


def debrand_tree(element, brand, website):
    """In-place rewrite of prose inside a parsed template/view tree.

    Only static template text and whitelisted prose attributes are touched.
    Data interpolated at render time arrives through ``t-out``/``t-esc``
    expressions, which are attributes we skip — so a customer record actually
    named "Odoo Ltd" is never rewritten.
    """
    changed = False
    for el in element.iter():
        tag = el.tag
        if not isinstance(tag, str):  # comments, processing instructions
            continue
        opaque = tag.rsplit("}", 1)[-1].lower() in OPAQUE_TAGS
        if not opaque and el.text:
            new = debrand_text(el.text, brand, website)
            if new is not el.text:
                el.text = new
                changed = True
        if el.tail:
            new = debrand_text(el.tail, brand, website)
            if new is not el.tail:
                el.tail = new
                changed = True
        for name, value in list(el.attrib.items()):
            if name.startswith("t-"):
                continue  # QWeb expression: rewriting it would break the render
            if name in PROSE_ATTRS:
                new = debrand_text(value, brand, website)
            elif name in URL_ATTRS:
                new = debrand_url(value, website)
            else:
                continue
            if new is not value:
                el.set(name, new)
                changed = True
    return changed
