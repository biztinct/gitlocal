# -*- coding: utf-8 -*-
"""Payobook mail debranding.

Odoo's core notification layout (used by e.g. the "Security Update: Password
Changed" email) renders an "OdooBot" author and a "Powered by Odoo" footer that
links to odoo.com. The product is Payobook — none of that should surface.

We debrand at ``mail.mail.create`` rather than by inheriting the core layout
template: the outgoing mail's ``body_html`` already contains the fully-rendered
layout, so a single, version-robust hook here catches every outgoing email no
matter which template/layout produced it. (The "OdooBot" *author name* is fixed
separately by renaming ``base.partner_root`` — see data/payobook_bot_debrand.xml.)
"""
import re

from markupsafe import Markup

from odoo import api, models

# Whole <a ...odoo.com...>…</a> anchor (e.g. the "Powered by Odoo" link).
_ODOO_ANCHOR_RE = re.compile(r"<a\b[^>]*odoo\.com[^>]*>.*?</a>", re.IGNORECASE | re.DOTALL)


def _debrand(body):
    """Replace Odoo branding with Payobook in a rendered email body."""
    if not body:
        return body
    is_markup = hasattr(body, "__html__")
    text = str(body)
    if "odoo" not in text.lower():
        return body
    # "Powered by <a ...odoo.com...>Odoo</a>"  ->  "Powered by Payobook"
    text = _ODOO_ANCHOR_RE.sub("Payobook", text)
    # Plain-text fallbacks.
    text = text.replace("Powered by Odoo", "Powered by Payobook")
    text = text.replace("OdooBot", "Payobook")
    return Markup(text) if is_markup else text


class MailMail(models.Model):
    _inherit = "mail.mail"

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("body_html"):
                vals["body_html"] = _debrand(vals["body_html"])
        return super().create(vals_list)


class ResPartner(models.Model):
    _inherit = "res.partner"

    def init(self):
        """Rename the system bot partner ("OdooBot") to "Payobook".

        ``base.partner_root`` is a ``noupdate="1"`` base record, so a data-XML
        ``<record>`` override is silently skipped on module *update* — it only
        writes on a fresh install. ``init()`` runs on every install AND upgrade,
        so this reliably keeps the bot named "Payobook". This is the name that
        appears as the sender on security / password-change notification emails.
        """
        root = self.env.ref("base.partner_root", raise_if_not_found=False)
        if root and root.name != "Payobook":
            root.sudo().write({"name": "Payobook"})
