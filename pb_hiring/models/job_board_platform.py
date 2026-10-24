"""Shared partner apps with server-owned tenant bindings and child provisioning."""

import hashlib
import json
from urllib.parse import urlsplit

from odoo import _, fields, models
from odoo.exceptions import UserError
from ..services.board_platform import read_platform
from ..services.connection_crypto import encrypt, decrypt
from ..services.job_boards import LINKEDIN_VERSION
from .connections import SPECS, PROVIDERS

# JobStreet is the customer-facing board; SEEK operates its partner API.
PROVIDERS[:] = [
    (key, "JobStreet" if key == "seek" else title) for key, title in PROVIDERS
]
SPECS["seek"]["fields"] = [
    f
    for f in SPECS["seek"]["fields"]
    if f[0] not in ("client_id", "client_secret", "webhook_secret")
]
SPECS["seek"]["help"] = (
    "Payobook owns the shared JobStreet partner app through SEEK. The platform operator authorizes each tenant’s hirer and callback signing secret centrally. Enter the matching hirer and posting contact here. SEEK must approve an unsearchable test hirer and ad product; Playground is read-only. No tenant receives the shared app secret."
)
SPECS["linkedin"]["help"] = (
    "Payobook manages the shared parent integration once approved. Each tenant gets its own customer application, organization binding and encrypted credentials. Save the test environment and organization, then provision the tenant application. Existing approved child credentials can be reused. LinkedIn partner approval and certification are required; a normal login is insufficient."
)


class BoardPlatformConnection(models.Model):
    _inherit = "pb.hiring.connection"

    provider = fields.Selection(selection_add=[("seek", "JobStreet")])
    board_provision_state = fields.Selection(
        [
            ("queued", "Queued"),
            ("pending", "Awaiting provider"),
            ("done", "Provisioned"),
            ("attention", "Needs attention"),
        ],
        readonly=True,
        copy=False,
    )
    board_provision_note = fields.Char(readonly=True, copy=False)

    def _tenant_key(self):
        self.ensure_one()
        return "%s:%s" % (self.env.cr.dbname, self.company_id.id)

    def _partner_config(self):
        self.ensure_one()
        try:
            data = read_platform(
                self.provider, self._config().get("environment"), self._tenant_key()
            )
        except ValueError as exc:
            raise UserError(str(exc)) from None
        if self._config().get("environment") == "production" and not data.get(
            "certified"
        ):
            raise UserError(
                _(
                    "Payobook's shared integration must complete provider certification before production activation. Use approved test resources first."
                )
            )
        key = "hirer_id" if self.provider == "seek" else "organization_id"
        if not data["tenant"].get(key) or data["tenant"][key] != self._config().get(
            key
        ):
            raise UserError(
                _(
                    "This board account is not authorized for this tenant. Ask the Payobook platform operator to verify the binding."
                )
            )
        return data

    def _ready(self):
        result = super()._ready()
        if self.provider in ("linkedin", "seek"):
            self._partner_config()
        return result

    def _check(self):
        if self.provider in ("linkedin", "seek"):
            self._partner_config()
        return super()._check()

    def _secret(self, key):
        if self.provider == "seek" and key == "webhook_secret":
            return self._partner_config()["tenant"].get("webhook_secret", "")
        return super()._secret(key)

    def _board_token_value(self):
        if self.provider != "seek":
            return super()._board_token_value()
        from datetime import timedelta

        cfg = self._partner_config()
        if (
            self.board_token
            and self.board_token_until
            and self.board_token_until > fields.Datetime.now() + timedelta(seconds=60)
        ):
            return decrypt(self.env, self.sudo().board_token)
        data = self._board_json(
            "POST",
            "https://auth.seek.com/oauth/token",
            json={
                "grant_type": "client_credentials",
                "client_id": cfg["client_id"],
                "client_secret": cfg["client_secret"],
                "audience": "https://test.graphql.seek.com"
                if self._config().get("environment") == "playground"
                else "https://graphql.seek.com",
            },
        )
        token, lifetime = data.get("access_token"), data.get("expires_in")
        if (
            not isinstance(token, str)
            or not token
            or not isinstance(lifetime, (int, float))
            or lifetime <= 60
        ):
            raise UserError(_("The partner app did not receive a usable access token."))
        self.sudo().write(
            {
                "board_token": encrypt(self.env, token),
                "board_token_until": fields.Datetime.now()
                + timedelta(seconds=min(lifetime, 86400)),
            }
        )
        return token

    def _card(self):
        card = super()._card()
        if self.provider in ("linkedin", "seek"):
            card.update(
                tenant_reference=self._tenant_key(),
                platform_managed=True,
                provision_state=self.board_provision_state or "",
                provision_note=self.board_provision_note or "",
            )
        return card

    def _provision_child(self):
        self.ensure_one()
        if self.provider != "linkedin" or self.board_provision_state != "pending":
            raise UserError(_("No claimed customer application request exists."))
        config = self._partner_config()
        token = self._board_json(
            "POST",
            "https://www.linkedin.com/oauth/v2/accessToken",
            data={
                "grant_type": "client_credentials",
                "client_id": config["client_id"],
                "client_secret": config["client_secret"],
            },
        ).get("access_token")
        if not isinstance(token, str) or not token:
            raise UserError(_("Partner authorization failed."))
        domain = config["tenant"].get("domain", "")
        parsed = urlsplit(domain)
        if (
            parsed.scheme != "https"
            or not parsed.hostname
            or parsed.path not in ("", "/")
            or parsed.username
            or parsed.password
            or parsed.query
            or parsed.fragment
        ):
            raise UserError(
                _("Payobook must configure the approved HTTPS tenant domain.")
            )
        foreign = (
            self._tenant_key()
            + ":"
            + self.env["ir.config_parameter"].sudo().get_param("database.uuid", "")
        )
        foreign = "payobook-" + hashlib.sha256(foreign.encode()).hexdigest()
        data = self._board_json(
            "POST",
            "https://api.linkedin.com/v2/provisionedApplications",
            headers={
                "Authorization": "Bearer " + token,
                "LinkedIn-Version": LINKEDIN_VERSION,
                "X-RestLi-Protocol-Version": "2.0.0",
            },
            json={
                "uniqueForeignId": foreign,
                "name": ("Payobook - " + self.company_id.name)[:50],
                "description": "Payobook customer recruitment integration",
                "validJsSdkDomains": [domain.rstrip("/")],
            },
        )
        credentials = data.get("credentials") or {}
        app_urn = data.get("key", "")
        if (
            not credentials.get("client_id")
            or not credentials.get("client_secret")
            or not app_urn.startswith("urn:li:developerApplication:")
        ):
            raise UserError(
                _(
                    "Provisioning response was incomplete. Ask the platform operator to reconcile the customer application before retrying."
                )
            )
        settings = dict(
            self._config(),
            client_id=credentials["client_id"],
            application_id=app_urn.rsplit(":", 1)[-1],
        )
        secrets = json.loads(decrypt(self.env, self.credentials))
        secrets["client_secret"] = credentials["client_secret"]
        self.sudo().write(
            {
                "settings": settings,
                "credentials": encrypt(self.env, json.dumps(secrets)),
                "board_provision_state": "done",
                "board_provision_note": _(
                    "Tenant application created. Complete customer enablement and provider acceptance."
                ),
                "enabled": False,
                "check_ok": False,
                "board_token": False,
                "board_token_until": False,
            }
        )


class BoardPlatformFacade(models.AbstractModel):
    _inherit = "pb.hiring"

    def board_provision_customer(self):
        self._require_write()
        conn = self.env["pb.hiring.connection"]._for_company(
            "linkedin", self.env.company
        )
        if not conn:
            raise UserError(_("Save the LinkedIn environment and organization first."))
        conn._partner_config()
        if conn._config().get("application_id"):
            raise UserError(
                _(
                    "A tenant application already exists. Reuse it; do not create another."
                )
            )
        if conn.board_provision_state in ("queued", "pending", "attention"):
            raise UserError(
                _(
                    "Provisioning is pending or needs reconciliation. Ask the platform operator to check its unique tenant reference before retrying."
                )
            )
        conn.write(
            {
                "board_provision_state": "queued",
                "board_provision_note": _(
                    "Tenant application creation queued. Check again after the background job runs."
                ),
            }
        )
        return conn._card()


class BoardPlatformJobs(models.Model):
    _inherit = "pb.hiring.board.event"

    def _run_queue(self):
        from odoo.modules.registry import Registry
        from odoo import api, SUPERUSER_ID

        with Registry(self.env.cr.dbname).cursor() as cr:
            worker = api.Environment(cr, SUPERUSER_ID, {})
            cr.execute(
                "SELECT id FROM pb_hiring_connection WHERE board_provision_state='queued' ORDER BY id FOR UPDATE SKIP LOCKED LIMIT 1"
            )
            row = cr.fetchone()
            if row:
                conn = worker["pb.hiring.connection"].browse(row[0])
                conn.write({"board_provision_state": "pending"})
                cr.commit()
                try:
                    with cr.savepoint():
                        conn._provision_child()
                except Exception:
                    conn.write(
                        {
                            "board_provision_state": "attention",
                            "board_provision_note": "Provisioning needs reconciliation. Check the provider application by its unique tenant reference; do not create a second application.",
                        }
                    )
                cr.commit()
        return super()._run_queue()
