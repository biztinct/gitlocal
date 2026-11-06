# Part of biz_mail_debrand — portable outgoing-email white-label layer.
# License LGPL-3.
"""Brand-agnostic 'Odoo' scrubbing for outgoing email content.

The word-replacement regex is derived from web_debranding's proven
``debrand()`` (web_debranding/models/ir_translation.py) with one extra
guard: ``/odoo/`` URL path segments are never rewritten, because backend
deep-links such as ``/odoo/action-…`` appear inside stock mail templates
and rewriting the path would break them (biz_deroute 301s ``/odoo`` for
real visitors).
"""
import re

from markupsafe import Markup

# https://www.odoo.com/documentation/... -> brand documentation base
DOC_LINK_RE = re.compile(r"https?://www\.odoo\.com/documentation/", re.IGNORECASE)
# odoo.com / www.odoo.com (also inside e-mail addresses) -> brand domain.
# Deliberately does NOT match other-domain lookalikes such as odoo.example.com
# (the \b before 'odoo' plus the literal '.com' anchor the full domain).
DOMAIN_RE = re.compile(r"\b(?:www\.)?odoo\.com\b", re.IGNORECASE)
# OdooBot / odoobot -> brand name (biz_debrand renames the bot partner the same way)
BOT_RE = re.compile(r"\bodoobot\b", re.IGNORECASE)
# The bare word 'odoo'. Skips technical usages:
#   .odoo / odoo.SMTH (JS namespaces, sub-domains), odoo = / odoo[ / odooSMTH
#   (code), and /odoo (URL path segments) on either side.
WORD_RE = re.compile(
    r"\b(?<!\.)(?<!/)odoo(?!\.\S|\s?=|\w|\[|/)\b", re.IGNORECASE
)
ODOO_ANYWHERE_RE = re.compile(r"odoo", re.IGNORECASE)


def scrub(source, brand_name, brand_domain, docs_url):
    """Pure text transform (str -> str). Order matters: docs URL first,
    then the bare domain, then bot/word replacement."""
    if not source or not ODOO_ANYWHERE_RE.search(source):
        return source
    source = DOC_LINK_RE.sub(docs_url, source)
    source = DOMAIN_RE.sub(brand_domain, source)
    source = BOT_RE.sub(brand_name, source)
    source = WORD_RE.sub(brand_name, source)
    return source


def brand_params(env):
    """Resolve (brand_name, brand_domain, docs_url) from config parameters.

    First hit wins — own knob, then biz_debrand, then web_debranding, then
    sane instance-level fallbacks. Mirrors the chain used by
    biz_theme/models/ir_http.py for the browser title.
    """
    icp = env["ir.config_parameter"].sudo()

    def first(*keys):
        for key in keys:
            value = icp.get_param(key)
            if value and value.strip():
                return value.strip()
        return None

    name = (
        first(
            "biz_mail_debrand.brand_name",
            "biz_debrand.brand_name",
            "web_debranding.new_name",
        )
        or env.company.name
        or "App"
    )
    website = (
        first(
            "biz_mail_debrand.brand_website",
            "biz_debrand.brand_website",
            "web_debranding.new_website",
            "web.base.url",
        )
        or "example.com"
    )
    domain = re.sub(r"^https?://", "", website, flags=re.IGNORECASE).rstrip("/")
    docs = first("web_debranding.new_documentation_website") or (
        website if "://" in website else "https://" + domain
    )
    if not docs.endswith("/"):
        docs += "/"
    return name, domain, docs


def debrand_text(env, source):
    """Scrub a plain-text value (subject, email_from, record names)."""
    if not source:
        return source
    name, domain, docs = brand_params(env)
    return scrub(source, name, domain, docs)


def debrand_html(env, source):
    """Scrub an HTML value, preserving Markup-ness of the input."""
    if not source:
        return source
    was_markup = isinstance(source, Markup)
    result = debrand_text(env, str(source))
    return Markup(result) if was_markup else result
