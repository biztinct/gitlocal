# -*- coding: utf-8 -*-
import base64
import hashlib
import hmac
import logging
import re
import secrets
from datetime import timedelta
from urllib.parse import urlencode

import requests

from odoo import fields, http
from odoo.exceptions import AccessDenied
from odoo.http import request
from odoo.addons.web.controllers.utils import _get_login_redirect_url

from ..models.res_config_settings import ZOHO_LOGIN_SCOPE, normalise_accounts_url


_logger = logging.getLogger(__name__)
_ACTION_TARGET = re.compile(r"^action-[1-9][0-9]{0,8}$")
_COOKIE_PREFIX = "pb_zoho_sso_"
_TRANSACTION_TTL = timedelta(minutes=5)
_HTTP_TIMEOUT = 10


def _sha256(value):
    return hashlib.sha256(value.encode()).hexdigest()


def _pkce_challenge(verifier):
    digest = hashlib.sha256(verifier.encode()).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode()


def _resolve_target(target, default_target="home"):
    """Map a short logical target to a same-origin Payobook route."""
    target = (target or default_target or "home").strip().lower()
    if target in {"home", "payobook"}:
        return "/bizapp"
    if target == "payslip_studio":
        return "/bizapp/action-1156"
    if _ACTION_TARGET.fullmatch(target):
        return f"/bizapp/{target}"
    return "/bizapp"


class PayobookZohoSsoController(http.Controller):
    def _config(self):
        icp = request.env["ir.config_parameter"].sudo()
        return {
            "enabled": icp.get_param("pb_zoho_sso.enabled") == "True",
            "client_id": (icp.get_param("pb_zoho_sso.client_id") or "").strip(),
            "client_secret": icp.get_param("pb_zoho_sso.client_secret") or "",
            "accounts_url": normalise_accounts_url(
                icp.get_param("pb_zoho_sso.accounts_url") or "https://accounts.zoho.com"
            ),
            "auto_link": icp.get_param("pb_zoho_sso.auto_link_email") == "True",
            "allowed_domains": {
                domain.strip().lower().lstrip("@")
                for domain in (icp.get_param("pb_zoho_sso.allowed_domains") or "").split(",")
                if domain.strip()
            },
            "default_target": icp.get_param("pb_zoho_sso.default_target") or "action-1156",
        }

    def _callback_url(self):
        return request.httprequest.url_root.rstrip("/") + "/auth/zoho/callback"

    def _remote_ip(self):
        return (request.httprequest.remote_addr or "")[:64]

    def _audit(self, event, **values):
        safe = {
            "event": event,
            "remote_ip": self._remote_ip(),
            "user_agent": (request.httprequest.user_agent.string or "")[:512],
        }
        safe.update({key: value for key, value in values.items() if value})
        return request.env["pb.zoho.sso.audit"].sudo().create(safe)

    def _error(self, title, message, status=400):
        response = request.render(
            "pb_zoho_sso.sso_error_page",
            {"title": title, "message": message},
        )
        response.status_code = status
        return response

    @http.route("/auth/zoho/start", type="http", auth="none", methods=["GET"], sitemap=False)
    def zoho_start(self, target=None, **_kw):
        config = self._config()
        target_path = _resolve_target(target, config["default_target"])
        if request.session.uid:
            return request.redirect(target_path, 303)
        if not config["enabled"] or not config["client_id"] or not config["client_secret"]:
            return self._error(
                "Zoho sign-in is not configured",
                "An administrator needs to finish the Zoho SSO settings in Payobook.",
                503,
            )
        if not config["accounts_url"]:
            return self._error(
                "Zoho data centre is invalid",
                "Ask an administrator to select a supported Zoho data centre.",
                503,
            )

        Transaction = request.env["pb.zoho.sso.transaction"].sudo()
        recent = Transaction.search_count([
            ("remote_ip", "=", self._remote_ip()),
            ("create_date", ">=", fields.Datetime.now() - timedelta(minutes=5)),
        ])
        if recent >= 30:
            self._audit("denied", detail="Start rate limit")
            return self._error("Too many sign-in attempts", "Please wait a few minutes and try again.", 429)

        state = secrets.token_urlsafe(32)
        browser_nonce = secrets.token_urlsafe(32)
        verifier = secrets.token_urlsafe(64)
        Transaction.create({
            "state_hash": _sha256(state),
            "browser_nonce_hash": _sha256(browser_nonce),
            "code_verifier": verifier,
            "target_path": target_path,
            "expires_at": fields.Datetime.now() + _TRANSACTION_TTL,
            "remote_ip": self._remote_ip(),
        })
        self._audit("started")

        params = {
            "client_id": config["client_id"],
            "response_type": "code",
            "redirect_uri": self._callback_url(),
            "scope": ZOHO_LOGIN_SCOPE,
            "access_type": "online",
            "state": state,
            "code_challenge": _pkce_challenge(verifier),
            "code_challenge_method": "S256",
        }
        response = request.redirect(
            f"{config['accounts_url']}/oauth/v2/auth?{urlencode(params)}",
            303,
            local=False,
        )
        response.set_cookie(
            _COOKIE_PREFIX + state[:12],
            browser_nonce,
            max_age=600,
            secure=True,
            httponly=True,
            samesite="Lax",
            path="/auth/zoho",
        )
        return response

    @http.route("/auth/zoho/callback", type="http", auth="none", methods=["GET"], sitemap=False)
    def zoho_callback(self, code=None, state=None, error=None, **_kw):
        if not state or len(state) > 256:
            return self._error("Sign-in could not be verified", "Return to Zoho People and try again.")
        state_hash = _sha256(state)
        request.env.cr.execute(
            "SELECT id FROM pb_zoho_sso_transaction WHERE state_hash = %s FOR UPDATE",
            [state_hash],
        )
        row = request.env.cr.fetchone()
        transaction = (
            request.env["pb.zoho.sso.transaction"].sudo().browse(row[0]).exists()
            if row else request.env["pb.zoho.sso.transaction"]
        )
        cookie_name = _COOKIE_PREFIX + state[:12]
        browser_nonce = request.httprequest.cookies.get(cookie_name) or ""
        if (
            not transaction
            or transaction.status != "pending"
            or transaction.expires_at < fields.Datetime.now()
            or not browser_nonce
            or not hmac.compare_digest(transaction.browser_nonce_hash, _sha256(browser_nonce))
        ):
            self._audit("denied", detail="Invalid, expired, or replayed state")
            return self._error("This sign-in link has expired", "Return to Zoho People and try again.")
        if error:
            transaction.write({"status": "failed"})
            self._audit("denied", detail="Zoho authorization was declined")
            return self._error("Zoho sign-in was cancelled", "No Payobook session was created.")
        if not code or len(code) > 2048:
            transaction.write({"status": "failed"})
            return self._error("Zoho did not return an authorization code", "Return to Zoho People and try again.")

        config = self._config()
        if not config["enabled"] or not config["accounts_url"]:
            transaction.write({"status": "failed"})
            return self._error("Zoho sign-in is unavailable", "Ask an administrator to check the Payobook SSO settings.", 503)
        transaction.write({"status": "processing"})

        try:
            token_response = requests.post(
                f"{config['accounts_url']}/oauth/v2/token",
                data={
                    "grant_type": "authorization_code",
                    "client_id": config["client_id"],
                    "client_secret": config["client_secret"],
                    "redirect_uri": self._callback_url(),
                    "code": code,
                    "code_verifier": transaction.code_verifier,
                },
                timeout=_HTTP_TIMEOUT,
                allow_redirects=False,
            )
            token_response.raise_for_status()
            access_token = token_response.json().get("access_token")
            if not access_token:
                raise ValueError("Zoho token response omitted access_token")
            profile_response = requests.get(
                f"{config['accounts_url']}/oauth/user/info",
                headers={"Authorization": f"Bearer {access_token}", "Accept": "application/json"},
                timeout=_HTTP_TIMEOUT,
                allow_redirects=False,
            )
            profile_response.raise_for_status()
            profile = profile_response.json()
        except (requests.RequestException, ValueError, TypeError):
            transaction.write({"status": "failed"})
            self._audit("failed", detail="Zoho token or profile validation failed")
            _logger.exception("Zoho SSO token/profile validation failed")
            return self._error(
                "Zoho could not verify your account",
                "Please try again. If the problem continues, ask an administrator to check the Zoho client settings.",
                502,
            )

        zoho_user_id = str(profile.get("ZUID") or profile.get("zuid") or "").strip()
        email = str(profile.get("Email") or profile.get("email") or "").strip().lower()
        display_name = str(
            profile.get("Display_Name") or profile.get("display_name") or profile.get("name") or email
        ).strip()
        if not zoho_user_id or "@" not in email:
            transaction.write({"status": "failed"})
            self._audit("failed", detail="Zoho profile omitted stable identity")
            return self._error("Zoho returned an incomplete profile", "Ask an administrator to check the configured OAuth scope.")

        domain = email.rsplit("@", 1)[1]
        if config["allowed_domains"] and domain not in config["allowed_domains"]:
            transaction.write({"status": "failed"})
            self._audit("denied", email=email, detail="Email domain not allowed")
            return self._error("This Zoho organisation is not allowed", "Use the company Zoho account approved for this Payobook tenant.", 403)

        Identity = request.env["pb.zoho.sso.identity"].sudo()
        identity = Identity.search([
            ("accounts_url", "=", config["accounts_url"]),
            ("zoho_user_id", "=", zoho_user_id),
        ], limit=1)
        if not identity:
            identity = Identity.create({
                "accounts_url": config["accounts_url"],
                "zoho_user_id": zoho_user_id,
                "email": email,
                "display_name": display_name,
            })
        else:
            identity.write({"email": email, "display_name": display_name, "last_seen_at": fields.Datetime.now()})

        if identity.state == "pending" and not identity.user_id and config["auto_link"] and config["allowed_domains"]:
            Users = request.env["res.users"].sudo().with_context(active_test=False)
            matches = Users.search(["|", ("login", "=ilike", email), ("email", "=ilike", email)], limit=2)
            active_matches = matches.filtered("active")
            if len(active_matches) == 1:
                identity.write({"user_id": active_matches.id, "state": "linked"})

        user = identity.user_id
        if identity.state != "linked" or not user or not user.active:
            transaction.write({"status": "failed"})
            event = "denied" if identity.state == "blocked" else "pending"
            self._audit(event, identity_id=identity.id, email=email, detail="Identity is not linked")
            return self._error(
                "Your Zoho account needs Payobook approval",
                "Your identity was verified, but it has not yet been linked to an active Payobook user. An administrator can approve it under Settings → Zoho SSO.",
                403,
            )

        credential_token = secrets.token_urlsafe(32)
        transaction.write({
            "status": "verified",
            "user_id": user.id,
            "credential_hash": _sha256(credential_token),
        })
        try:
            credential = {
                "login": user.login,
                "type": "pb_zoho_sso",
                "transaction_id": transaction.id,
                "token": credential_token,
            }
            auth_info = request.session.authenticate(request.env, credential)
            transaction.write({"status": "consumed", "credential_hash": False})
            identity.write({"last_login_at": fields.Datetime.now(), "last_seen_at": fields.Datetime.now()})
            self._audit("success", user_id=user.id, identity_id=identity.id, email=email)
            response = request.redirect(
                _get_login_redirect_url(auth_info["uid"], transaction.target_path),
                303,
            )
            response.autocorrect_location_header = False
            response.delete_cookie(cookie_name, path="/auth/zoho")
            return response
        except AccessDenied:
            transaction.write({"status": "failed", "credential_hash": False})
            self._audit("failed", user_id=user.id, identity_id=identity.id, email=email, detail="Odoo session authentication failed")
            return self._error("Payobook could not start your session", "Ask an administrator to confirm that your Payobook user is active.", 403)
