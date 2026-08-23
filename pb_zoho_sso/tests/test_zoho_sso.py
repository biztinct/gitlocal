# -*- coding: utf-8 -*-
import hashlib
from datetime import timedelta

from odoo import fields
from odoo.exceptions import AccessDenied
from odoo.tests.common import TransactionCase, tagged

from odoo.addons.pb_zoho_sso.controllers.main import _pkce_challenge, _resolve_target
from odoo.addons.pb_zoho_sso.models.res_config_settings import normalise_accounts_url


@tagged("post_install", "-at_install")
class TestZohoSso(TransactionCase):
    def test_target_is_always_same_origin(self):
        self.assertEqual(_resolve_target("action-1156"), "/bizapp/action-1156")
        self.assertEqual(_resolve_target("payslip_studio"), "/bizapp/action-1156")
        self.assertEqual(_resolve_target("https://evil.example"), "/bizapp")
        self.assertEqual(_resolve_target("//evil.example"), "/bizapp")

    def test_accounts_url_allowlist(self):
        self.assertEqual(normalise_accounts_url("https://accounts.zoho.com.au/"), "https://accounts.zoho.com.au")
        self.assertFalse(normalise_accounts_url("http://accounts.zoho.com"))
        self.assertFalse(normalise_accounts_url("https://accounts.zoho.com.evil.example"))

    def test_pkce_is_urlsafe(self):
        challenge = _pkce_challenge("a" * 64)
        self.assertNotIn("=", challenge)
        self.assertNotIn("+", challenge)
        self.assertNotIn("/", challenge)

    def test_one_time_credential_is_bound_to_user_and_transaction(self):
        user = self.env["res.users"].with_context(no_reset_password=True).create({
            "name": "Zoho SSO test user",
            "login": "zoho-sso-test@example.com",
            "email": "zoho-sso-test@example.com",
        })
        token = "one-time-secret"
        transaction = self.env["pb.zoho.sso.transaction"].sudo().create({
            "state_hash": hashlib.sha256(b"state").hexdigest(),
            "browser_nonce_hash": hashlib.sha256(b"browser").hexdigest(),
            "code_verifier": "verifier",
            "target_path": "/bizapp",
            "expires_at": fields.Datetime.now() + timedelta(minutes=5),
            "status": "verified",
            "user_id": user.id,
            "credential_hash": hashlib.sha256(token.encode()).hexdigest(),
        })
        auth_info = user.with_user(user)._check_credentials({
            "type": "pb_zoho_sso",
            "transaction_id": transaction.id,
            "token": token,
        }, {"interactive": True})
        self.assertEqual(auth_info["uid"], user.id)
        self.assertEqual(auth_info["mfa"], "skip")
        with self.assertRaises(AccessDenied):
            user.with_user(user)._check_credentials({
                "type": "pb_zoho_sso",
                "transaction_id": transaction.id,
                "token": "wrong",
            }, {"interactive": True})
