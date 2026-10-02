# -*- coding: utf-8 -*-
from urllib.parse import urlsplit

from odoo import api, fields, models


ZOHO_ACCOUNTS_URLS = {
    "https://accounts.zoho.com",
    "https://accounts.zoho.eu",
    "https://accounts.zoho.in",
    "https://accounts.zoho.com.au",
    "https://accounts.zoho.jp",
    "https://accounts.zoho.ca",
    "https://accounts.zoho.com.cn",
    "https://accounts.zoho.sa",
}
ZOHO_LOGIN_SCOPE = "AaaServer.profile.READ,email"


def normalise_accounts_url(value):
    """Return an approved Zoho Accounts origin or an empty string.

    The client secret is POSTed to this origin, so a free-form URL would turn a
    configuration typo (or a compromised settings account) into secret
    exfiltration/SSRF.  Keep the list deliberately explicit.
    """
    value = (value or "").strip().rstrip("/")
    parsed = urlsplit(value)
    if parsed.scheme != "https" or parsed.path or parsed.query or parsed.fragment:
        return ""
    return value if value in ZOHO_ACCOUNTS_URLS else ""


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    pb_zoho_sso_enabled = fields.Boolean(
        string="Enable Zoho single sign-on",
        config_parameter="pb_zoho_sso.enabled",
    )
    pb_zoho_sso_client_id = fields.Char(
        string="Client ID",
        config_parameter="pb_zoho_sso.client_id",
    )
    pb_zoho_sso_client_secret = fields.Char(
        string="Client Secret",
        config_parameter="pb_zoho_sso.client_secret",
        groups="base.group_system",
    )
    pb_zoho_sso_accounts_url = fields.Selection(
        selection=[
            ("https://accounts.zoho.com", "United States / Global (.com)"),
            ("https://accounts.zoho.eu", "Europe (.eu)"),
            ("https://accounts.zoho.in", "India (.in)"),
            ("https://accounts.zoho.com.au", "Australia (.com.au)"),
            ("https://accounts.zoho.jp", "Japan (.jp)"),
            ("https://accounts.zoho.ca", "Canada (.ca)"),
            ("https://accounts.zoho.com.cn", "China (.com.cn)"),
            ("https://accounts.zoho.sa", "Saudi Arabia (.sa)"),
        ],
        string="Zoho data centre",
        default="https://accounts.zoho.com",
        config_parameter="pb_zoho_sso.accounts_url",
    )
    pb_zoho_sso_auto_link_email = fields.Boolean(
        string="Automatically link existing users",
        config_parameter="pb_zoho_sso.auto_link_email",
        help="Link a Zoho identity to one active Payobook user whose login or "
             "email matches exactly. This is only used for an allowed email domain.",
    )
    pb_zoho_sso_allowed_domains = fields.Char(
        string="Allowed email domains",
        config_parameter="pb_zoho_sso.allowed_domains",
        help="Comma-separated company domains, for example example.com,example.com.au. "
             "Leave empty to require every identity to be approved manually.",
    )
    pb_zoho_sso_default_target = fields.Char(
        string="Default Payobook destination",
        default="action-1156",
        config_parameter="pb_zoho_sso.default_target",
        help="A logical destination such as home or action-1156. Raw external URLs are never accepted.",
    )
    pb_zoho_sso_callback_url = fields.Char(
        string="Authorized redirect URI",
        compute="_compute_pb_zoho_sso_callback_url",
    )
    pb_zoho_sso_button_url = fields.Char(
        string="Zoho People button URL",
        compute="_compute_pb_zoho_sso_callback_url",
    )
    pb_zoho_sso_scope = fields.Char(
        string="OAuth scope",
        compute="_compute_pb_zoho_sso_callback_url",
    )

    @api.depends("pb_zoho_sso_default_target")
    def _compute_pb_zoho_sso_callback_url(self):
        base_url = self.env["ir.config_parameter"].sudo().get_param("web.base.url", "").rstrip("/")
        for settings in self:
            settings.pb_zoho_sso_callback_url = f"{base_url}/auth/zoho/callback" if base_url else ""
            target = (settings.pb_zoho_sso_default_target or "home").strip()
            settings.pb_zoho_sso_button_url = (
                f"{base_url}/auth/zoho/start?target={target}" if base_url else ""
            )
            settings.pb_zoho_sso_scope = ZOHO_LOGIN_SCOPE
