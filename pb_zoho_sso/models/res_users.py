# -*- coding: utf-8 -*-
import hashlib
import hmac

from odoo import fields, models
from odoo.exceptions import AccessDenied


class ResUsers(models.Model):
    _inherit = "res.users"

    zoho_sso_identity_ids = fields.One2many(
        "pb.zoho.sso.identity",
        "user_id",
        string="Zoho SSO identities",
    )

    def _check_credentials(self, credential, env):
        try:
            return super()._check_credentials(credential, env)
        except AccessDenied:
            if credential.get("type") != "pb_zoho_sso":
                raise
            transaction_id = credential.get("transaction_id")
            token = credential.get("token")
            if not transaction_id or not token or not self.active:
                raise
            transaction = self.env["pb.zoho.sso.transaction"].sudo().browse(int(transaction_id)).exists()
            if (
                not transaction
                or transaction.status != "verified"
                or transaction.user_id != self
                or transaction.expires_at < fields.Datetime.now()
                or not transaction.credential_hash
            ):
                raise
            supplied_hash = hashlib.sha256(token.encode()).hexdigest()
            if not hmac.compare_digest(transaction.credential_hash, supplied_hash):
                raise
            return {"uid": self.id, "auth_method": "zoho_sso", "mfa": "skip"}
