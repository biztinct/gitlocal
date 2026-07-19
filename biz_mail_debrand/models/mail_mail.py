# Part of biz_mail_debrand — portable outgoing-email white-label layer.
# License LGPL-3.
from odoo import models

from .debrand import debrand_html, debrand_text


class MailMail(models.Model):
    _inherit = "mail.mail"

    def _prepare_outgoing_body(self):
        # Same seam mail_debranding uses; both apply after super so they
        # compose regardless of module load order.
        body = super()._prepare_outgoing_body()
        return debrand_html(self.env, body)

    def _prepare_outgoing_list(self, mail_server=False, doc_to_followers=None):
        results = super()._prepare_outgoing_list(
            mail_server=mail_server, doc_to_followers=doc_to_followers
        )
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
