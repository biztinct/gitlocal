# Part of biz_mail_debrand — portable outgoing-email white-label layer.
# License LGPL-3.
import logging

from odoo import models, tools

from .blocked_recipients import BLOCKED_REASON, blocked_domains, is_blocked, keep_allowed
from .debrand import debrand_html, debrand_text

_logger = logging.getLogger(__name__)


class MailMail(models.Model):
    _inherit = "mail.mail"

    def _biz_all_recipients_blocked(self, domains):
        """Every address this mail would go to is a blocked one."""
        self.ensure_one()
        emails = tools.mail.email_split_and_format_normalize(self.email_to or "")
        emails += tools.mail.email_split_and_format_normalize(self.email_cc or "")
        emails += [p.email for p in self.recipient_ids if p.email]
        return bool(emails) and all(is_blocked(e, domains) for e in emails)

    def _send(self, *args, **kwargs):
        # A mail whose every recipient is blocked must never reach super():
        # with nothing left to send it would neither be marked sent nor
        # failed, and the queue would retry it for ever. Close it here.
        domains = blocked_domains(self.env)
        if not domains:
            return super()._send(*args, **kwargs)
        blocked = self.filtered(
            lambda m: m.state == "outgoing" and m._biz_all_recipients_blocked(domains)
        )
        if blocked:
            blocked.write({
                "state": "cancel",
                "failure_type": False,
                "failure_reason": BLOCKED_REASON,
            })
            self.env["mail.notification"].sudo().search([
                ("mail_mail_id", "in", blocked.ids),
                ("notification_type", "=", "email"),
            ]).write({"notification_status": "canceled"})
            _logger.info("Blocked %s mail.mail to test/demo addresses: %s",
                         len(blocked), blocked.ids)
        rest = self - blocked
        if not rest:
            return True
        return super(MailMail, rest)._send(*args, **kwargs)

    def _prepare_outgoing_body(self):
        # Same seam mail_debranding uses; both apply after super so they
        # compose regardless of module load order.
        body = super()._prepare_outgoing_body()
        return debrand_html(self.env, body)

    def _prepare_outgoing_list(self, mail_server=False, doc_to_followers=None):
        results = super()._prepare_outgoing_list(
            mail_server=mail_server, doc_to_followers=doc_to_followers
        )
        # Mixed mail: strip the blocked addresses and drop the entries the
        # strip emptied. _send() already closed the mails where nobody is
        # left. An entry that had no address to begin with (a partner without
        # an email) stays, so stock records it as "email missing".
        domains = blocked_domains(self.env)
        if domains:
            kept = []
            for values in results:
                had_any = bool(values.get("email_to") or values.get("email_cc"))
                values["email_to"] = keep_allowed(values.get("email_to"), domains)
                values["email_cc"] = keep_allowed(values.get("email_cc"), domains)
                values["email_to_normalized"] = keep_allowed(
                    values.get("email_to_normalized"), domains
                )
                if values["email_to"] or values["email_cc"] or not had_any:
                    kept.append(values)
            results = kept
        # The headers dict is shared between all entries of one mail —
        # only mutate each distinct dict once.
        seen_headers = set()
        for values in results:
            if values.get("subject"):
                values["subject"] = debrand_text(self.env, values["subject"])
            if values.get("email_from"):
                values["email_from"] = debrand_text(self.env, values["email_from"])
            headers = values.get("headers")
            if headers and id(headers) not in seen_headers:
                seen_headers.add(id(headers))
                for key in [k for k in headers if k.lower().startswith("x-odoo")]:
                    headers.pop(key, None)
        return results
