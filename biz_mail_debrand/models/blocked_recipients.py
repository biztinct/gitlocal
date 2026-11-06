# Part of biz_mail_debrand — portable outgoing-email white-label layer.
# License LGPL-3.
"""Never hand mail for test / demo addresses to the real SMTP server.

Demo databases hold thousands of people whose addresses are made up
(``*@example.com``, ``*@payobook.local``). Every email to them was relayed by
the real outgoing server and bounced back into the sender's own mailbox, so
a click-through of a demo flow flooded the owner's inbox.

``biz_mail_debrand.blocked_domains`` (comma/space separated) lists the
domains that never receive mail. An entry blocks the domain itself and every
sub-domain of it (``local`` blocks ``x@payobook.local``). When the parameter
is absent the reserved, never-deliverable domains of RFC 2606 / RFC 6761
apply; set it to ``none`` to block nothing.
"""
import re

from odoo import tools

PARAM_BLOCKED_DOMAINS = "biz_mail_debrand.blocked_domains"
DEFAULT_BLOCKED_DOMAINS = (
    "example.com", "example.net", "example.org",
    "example", "invalid", "local", "localhost", "test",
)
# Shown on the failed-email row; end users can see it, so no vendor name.
BLOCKED_REASON = "Not sent: test or demo address."


def parse_domains(raw):
    """'*.local, @demo.com example.com' -> ('local', 'demo.com', 'example.com')."""
    if not isinstance(raw, str):  # get_param() answers False when unset
        return DEFAULT_BLOCKED_DOMAINS
    if raw.strip().lower() in ("", "none", "0", "off"):
        return ()
    entries = []
    for entry in re.split(r"[\s,;]+", raw.lower()):
        entry = entry.strip().lstrip("*@.").rstrip(".")
        if entry and entry not in entries:
            entries.append(entry)
    return tuple(entries)


def blocked_domains(env):
    return parse_domains(env["ir.config_parameter"].sudo().get_param(PARAM_BLOCKED_DOMAINS))


def is_blocked(email, domains):
    """True when the (possibly formatted) address belongs to a blocked domain."""
    if not domains or not email:
        return False
    normalized = tools.email_normalize(email) or ""
    domain = normalized.rpartition("@")[2]
    if not domain:
        return False
    return any(domain == d or domain.endswith("." + d) for d in domains)


def keep_allowed(emails, domains):
    """Drop the blocked addresses from a list of formatted addresses."""
    return [e for e in (emails or []) if not is_blocked(e, domains)]
