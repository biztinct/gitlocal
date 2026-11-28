# -*- coding: utf-8 -*-
from datetime import timedelta

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class PbZohoSsoIdentity(models.Model):
    _name = "pb.zoho.sso.identity"
    _description = "Zoho SSO identity"
    _order = "state, email, id"
    _rec_name = "email"

    zoho_user_id = fields.Char(string="Zoho user ID", required=True, index=True, readonly=True)
    accounts_url = fields.Char(string="Zoho data centre", required=True, readonly=True)
    email = fields.Char(required=True, index=True, readonly=True)
    display_name = fields.Char(readonly=True)
    user_id = fields.Many2one(
        "res.users",
        string="Payobook user",
        ondelete="cascade",
        domain=[("active", "=", True)],
    )
    state = fields.Selection(
        [("pending", "Awaiting approval"), ("linked", "Linked"), ("blocked", "Blocked")],
        default="pending",
        required=True,
        index=True,
    )
    last_login_at = fields.Datetime(readonly=True)
    last_seen_at = fields.Datetime(readonly=True)

    _unique_zoho_identity = models.Constraint(
        "unique(accounts_url, zoho_user_id)",
        "This Zoho identity is already registered.",
    )
    _unique_payobook_user = models.Constraint(
        "unique(user_id)",
        "This Payobook user is already linked to a Zoho identity.",
    )

    @api.onchange("user_id")
    def _onchange_user_id(self):
        for identity in self:
            if identity.user_id and identity.state == "pending":
                identity.state = "linked"

    @api.constrains("state", "user_id")
    def _check_linked_identity_has_user(self):
        for identity in self:
            if identity.state == "linked" and not identity.user_id:
                raise ValidationError(_("A linked Zoho identity must have a Payobook user."))


class PbZohoSsoTransaction(models.Model):
    _name = "pb.zoho.sso.transaction"
    _description = "Short-lived Zoho SSO transaction"
    _order = "create_date desc"

    state_hash = fields.Char(required=True, index=True, readonly=True)
    browser_nonce_hash = fields.Char(required=True, readonly=True)
    code_verifier = fields.Char(required=True, readonly=True, groups="base.group_system")
    target_path = fields.Char(required=True, readonly=True)
    expires_at = fields.Datetime(required=True, index=True, readonly=True)
    status = fields.Selection(
        [
            ("pending", "Pending"),
            ("processing", "Processing"),
            ("verified", "Verified"),
            ("consumed", "Consumed"),
            ("failed", "Failed"),
        ],
        default="pending",
        required=True,
        index=True,
        readonly=True,
    )
    user_id = fields.Many2one("res.users", readonly=True, ondelete="set null")
    credential_hash = fields.Char(readonly=True, groups="base.group_system")
    remote_ip = fields.Char(readonly=True)

    _unique_state_hash = models.Constraint(
        "unique(state_hash)",
        "An SSO transaction with this state already exists.",
    )

    @api.autovacuum
    def _gc_zoho_sso_transactions(self):
        cutoff = fields.Datetime.now() - timedelta(days=1)
        self.sudo().search([("create_date", "<", cutoff)]).unlink()


class PbZohoSsoAudit(models.Model):
    _name = "pb.zoho.sso.audit"
    _description = "Zoho SSO audit event"
    _order = "create_date desc"

    event = fields.Selection(
        [
            ("started", "Started"),
            ("success", "Successful login"),
            ("pending", "Approval required"),
            ("denied", "Denied"),
            ("failed", "Failed"),
        ],
        required=True,
        index=True,
    )
    user_id = fields.Many2one("res.users", readonly=True, ondelete="set null")
    identity_id = fields.Many2one("pb.zoho.sso.identity", readonly=True, ondelete="set null")
    email = fields.Char(readonly=True)
    remote_ip = fields.Char(readonly=True)
    user_agent = fields.Char(readonly=True)
    detail = fields.Char(readonly=True)
