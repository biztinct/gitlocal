"""Company-scoped board publishing and signed application intake."""

import json
import uuid
from datetime import timedelta
from urllib.parse import urlsplit

import requests

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError
from odoo.tools import email_normalize, html2plaintext
from ..services import job_boards as contracts
from ..services.connection_crypto import encrypt, decrypt
from .connections import PROVIDERS, SPECS

PROVIDERS.extend(
    [
        ("linkedin", "LinkedIn job publishing"),
        ("seek", "JobStreet"),
        ("vietnamworks", "VietnamWorks access"),
    ]
)
SPECS.update(
    {
        "linkedin": dict(
            description="Review and submit jobs, verify listing status and receive signed applications.",
            help="Payobook engineering: connector contract tests. Account owner: request Apply Connect partner access and provider test organization; a normal demo login is insufficient. LinkedIn: approve the application and test resources. Enter the customer application credentials. Complete provider certification before production use.",
            fields=[
                ("environment", "Environment", False),
                (
                    "approval_reference",
                    "Provider approval / test-resource reference",
                    False,
                ),
                ("organization_id", "LinkedIn organization URN", False),
                ("application_id", "Customer application ID", False),
                ("client_id", "Customer client ID", False),
                ("client_secret", "Customer client secret", True),
            ],
        ),
        "seek": dict(
            description="Publish JobStreet ads through SEEK and import provider-hosted applications.",
            help="Account owner: request SEEK partner access, an unsearchable test hirer and approved ad products. Playground supports reads only. SEEK: provision credentials and certify the integration. Use one configured intake connection per hirer; complete live test-hirer acceptance before production.",
            fields=[
                ("environment", "Environment", False),
                (
                    "approval_reference",
                    "Provider approval / test-hirer reference",
                    False,
                ),
                ("hirer_id", "Hiring organization identifier", False),
                ("contact_name", "Posting contact name", False),
                ("contact_email", "Posting contact email", False),
                ("client_id", "Partner client ID", False),
                ("client_secret", "Partner client secret", True),
                ("webhook_secret", "Webhook signing secret", True),
            ],
        ),
        "vietnamworks": dict(
            description="Arrange the supported API contract and staging access with VietnamWorks.",
            help="VietnamWorks must confirm its current posting and application-export contract, staging host, credentials and test employer. Public legacy examples are insufficient to enable a live integration. Account owner supplies the employer details; Payobook engineering implements and tests the confirmed contract.",
            fields=[],
        ),
    }
)


class BoardConnection(models.Model):
    _inherit = "pb.hiring.connection"

    provider = fields.Selection(
        selection_add=[
            ("linkedin", "LinkedIn job publishing"),
            ("seek", "JobStreet"),
            ("vietnamworks", "VietnamWorks access"),
        ],
        ondelete={"linkedin": "cascade", "seek": "cascade", "vietnamworks": "cascade"},
    )

    board_token = fields.Text(groups="base.group_system", copy=False)
    board_token_until = fields.Datetime(groups="base.group_system", copy=False)

    def _card(self):
        card = super()._card()
        if self.provider in ("linkedin", "seek"):
            card["callback"] = card["callback"].replace(
                "/hiring/connect/", "/hiring/boards/"
            )
        return card

    def _board_json(self, method, url, **kwargs):
        try:
            r = requests.request(
                method, url, timeout=(5, 30), allow_redirects=False, **kwargs
            )
            if r.status_code >= 300:
                raise UserError(
                    _(
                        "The board returned HTTP %s. Verify API approval and credentials; check provider status before retrying a submission.",
                        r.status_code,
                    )
                )
            if len(r.content) > 4 * 1024 * 1024:
                raise UserError(_("The board response exceeded the permitted size."))
            data = r.json()
            if not isinstance(data, dict):
                raise ValueError()
            return data
        except (requests.RequestException, ValueError):
            raise UserError(
                _(
                    "The board response could not be verified. Check provider status before retrying; no automatic duplicate submission was made."
                )
            ) from None

    def _board_token_value(self):
        self.ensure_one()
        if (
            self.board_token
            and self.board_token_until
            and self.board_token_until > fields.Datetime.now() + timedelta(seconds=60)
        ):
            return decrypt(self.env, self.sudo().board_token)
        cfg = self._config()
        auth = dict(
            grant_type="client_credentials",
            client_id=cfg.get("client_id"),
            client_secret=self._secret("client_secret"),
        )
        if self.provider == "seek":
            auth["audience"] = (
                "https://test.graphql.seek.com"
                if cfg.get("environment") == "playground"
                else "https://graphql.seek.com"
            )
            data = self._board_json(
                "POST", "https://auth.seek.com/oauth/token", json=auth
            )
        else:
            data = self._board_json(
                "POST", "https://www.linkedin.com/oauth/v2/accessToken", data=auth
            )
        token = data.get("access_token")
        lifetime = data.get("expires_in")
        if (
            not isinstance(token, str)
            or not token
            or not isinstance(lifetime, (int, float))
            or lifetime <= 60
        ):
            raise UserError(_("The provider did not issue a usable access token."))
        self.sudo().write(
            {
                "board_token": encrypt(self.env, token),
                "board_token_until": fields.Datetime.now()
                + timedelta(seconds=min(lifetime, 86400)),
            }
        )
        return token

    def _li(self, method, path, **kwargs):
        return self._board_json(
            method,
            "https://api.linkedin.com/v2/" + path,
            headers={
                "Authorization": "Bearer " + self._board_token_value(),
                "LinkedIn-Version": contracts.LINKEDIN_VERSION,
                "X-RestLi-Protocol-Version": "2.0.0",
                **(
                    {"X-Restli-Method": "batch_create"}
                    if path == "simpleJobPostings"
                    else {}
                ),
            },
            **kwargs,
        )

    def _seek(self, query, variables):
        data = self._board_json(
            "POST",
            "https://graphql.seek.com/graphql",
            headers={
                "Authorization": "Bearer " + self._board_token_value(),
                "User-Agent": "Payobook-Recruit/1.0",
            },
            json={"query": query, "variables": variables},
        )
        if data.get("errors") or not isinstance(data.get("data"), dict):
            raise UserError(
                _(
                    "SEEK rejected the operation. Verify the hirer relationship, field identifiers and API permissions."
                )
            )
        return data["data"]

    def _check(self):
        if self.provider not in ("linkedin", "seek", "vietnamworks"):
            return super()._check()
        if self.provider == "vietnamworks":
            raise UserError(
                _(
                    "VietnamWorks must provide its current API contract and staging access before this connector can be completed."
                )
            )
        cfg = self._config()
        for key, label, secret in SPECS[self.provider]["fields"]:
            if not (self._secret(key) if secret else cfg.get(key)):
                raise UserError(_("Complete %s first.", label))
        allowed = (
            ("test", "production")
            if self.provider == "linkedin"
            else ("playground", "test", "production")
        )
        if cfg.get("environment") not in allowed:
            raise UserError(_("Choose a supported environment."))
        if self.provider == "linkedin":
            if not cfg["organization_id"].startswith("urn:li:organization:"):
                raise UserError(_("Enter the provider-approved organization URN."))
            data = self._li(
                "GET", "jobPostingStatus", params={"ids": "payobook-connection-check"}
            )
            if "results" not in data:
                raise UserError(_("Job-status API access was not confirmed."))
        else:
            hirer = self._seek(contracts.SEEK_CHECK, {"id": cfg["hirer_id"]}).get(
                "hiringOrganization"
            )
            if not hirer or hirer["id"]["value"] != cfg["hirer_id"]:
                raise UserError(
                    _("The configured hiring organization is not accessible.")
                )
            is_playground = "PublicTest:" in cfg["hirer_id"]
            if is_playground != (cfg["environment"] == "playground"):
                raise UserError(
                    _(
                        "The hiring organization does not match the selected environment."
                    )
                )
        return _(
            "Provider authentication and read access passed. Publishing, update, close and native application acceptance must still pass on provider-approved test resources."
        )

    def _board_media(self, url):
        try:
            contracts.media_url(self.provider, url)
        except ValueError:
            raise UserError(
                _("The provider returned an unexpected CV address.")
            ) from None
        try:
            with requests.get(
                url,
                headers={"Authorization": "Bearer " + self._board_token_value()},
                stream=True,
                timeout=(5, 30),
                allow_redirects=False,
            ) as r:
                if r.status_code == 404:
                    return None
                if r.status_code != 200:
                    raise UserError(
                        _(
                            "The application CV could not be downloaded. Retry intake after checking provider access."
                        )
                    )
                content = bytearray()
                for block in r.iter_content(65536):
                    content.extend(block)
                    if len(content) > 5 * 1024 * 1024:
                        raise UserError(
                            _(
                                "The application CV exceeds 5 MB. Obtain a smaller original."
                            )
                        )
                raw = bytes(content)
                if raw.startswith(b"%PDF-"):
                    return raw, "pdf", "application/pdf"
                if raw.startswith(b"PK\x03\x04"):
                    import io, zipfile

                    with zipfile.ZipFile(io.BytesIO(raw)) as z:
                        if "word/document.xml" in z.namelist():
                            return (
                                raw,
                                "docx",
                                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                            )
                raise UserError(
                    _(
                        "The imported CV is not a supported PDF or DOCX. Obtain a supported original."
                    )
                )
        except (requests.RequestException, ValueError):
            raise UserError(
                _(
                    "The application CV download failed. Retry intake after checking provider access."
                )
            ) from None


class BoardConnectionFacade(models.AbstractModel):
    _inherit = "pb.hiring"

    def connection_save(self, provider, values):
        self._require_write()
        if provider in ("linkedin", "seek") and isinstance(values, dict):
            conn = self.env["pb.hiring.connection"]._for_company(
                provider, self.env.company
            )
            used = (
                self.env["pb.hiring.role.channel"]
                .sudo()
                .search_count([("board_connection_id", "=", conn.id)])
                if conn
                else 0
            )
            if used and any(
                k in values
                and str(values[k] or "").strip() != conn._config().get(k, "")
                for k in (
                    "environment",
                    "organization_id",
                    "application_id",
                    "hirer_id",
                    "client_id",
                )
            ):
                raise UserError(
                    _(
                        "This account already owns board submissions. Reconcile them before changing its identity or environment. Secret rotation is allowed."
                    )
                )
        result = super().connection_save(provider, values)
        if provider in ("linkedin", "seek"):
            self.env["pb.hiring.connection"]._for_company(
                provider, self.env.company
            ).write({"board_token": False, "board_token_until": False})
        return result

    def _p7_rows(self, req):
        rows = super()._p7_rows(req)
        return rows | self.env["pb.hiring.role.channel"].sudo().search(
            [
                ("requisition_id", "=", req.id),
                ("board_reference", "!=", False),
                ("board_state", "!=", "closed"),
            ]
        )

    def _p7_row_payload(self, req, rc, apps, on_page, mail_on):
        result = super()._p7_row_payload(req, rc, apps, on_page, mail_on)
        if rc.channel_id.key in contracts.BOARD_PROVIDERS:
            result.update(
                api_supported=True,
                api_managed=bool(rc.board_reference),
                api_status=rc.board_note
                or _("API setup and provider acceptance required."),
            )
        return result

    def _board_manual_gate(self, payload):
        if self._p7_row(payload).board_reference:
            raise UserError(
                _(
                    "Use Review API publishing to update or close this provider-managed listing."
                )
            )

    def _act_p7_mark_posted(self, payload):
        self._board_manual_gate(payload)
        return super()._act_p7_mark_posted(payload)

    def _act_p7_unmark(self, payload):
        self._board_manual_gate(payload)
        return super()._act_p7_unmark(payload)

    def _act_p7_close(self, payload):
        self._board_manual_gate(payload)
        return super()._act_p7_close(payload)

    @api.model
    def board_open(self, role_channel_id):
        rc = self._p7_row({"role_channel_id": role_channel_id})
        rc.with_env(self.env).check_access("read")
        if rc.company_id not in self.env.companies:
            raise AccessError(_("This role belongs to another company."))
        if rc.channel_id.key not in contracts.BOARD_PROVIDERS:
            raise UserError(_("A supported board is required."))
        job = rc.requisition_id.job_id
        vals = dict(
            role_channel_id=rc.id,
            title=rc.requisition_id.title,
            description=job.website_description or "",
            location=rc.requisition_id.location or "",
            summary=rc.requisition_id.title,
        )
        vals.update(
            {k: v for k, v in (rc.board_values or {}).items() if k in BOARD_FIELDS}
        )
        wizard = self.env["pb.hiring.board.review"].create(vals)
        return {
            "type": "ir.actions.act_window",
            "name": _("Review board publishing"),
            "res_model": wizard._name,
            "res_id": wizard.id,
            "views": [(False, "form")],
            "target": "new",
        }


class BoardRoleChannel(models.Model):
    _inherit = "pb.hiring.role.channel"

    board_reference = fields.Char(readonly=True, copy=False, index=True)
    board_connection_id = fields.Many2one(
        "pb.hiring.connection", readonly=True, copy=False
    )
    board_remote_id = fields.Char(readonly=True, copy=False)
    board_task_id = fields.Char(readonly=True, copy=False)
    board_close_requested = fields.Boolean(readonly=True, copy=False)
    board_operation = fields.Char(readonly=True, copy=False)
    board_state = fields.Selection(
        [
            ("draft", "Draft"),
            ("queued", "Queued for submission"),
            ("pending", "Awaiting provider"),
            ("live", "Provider confirmed live"),
            ("closed", "Provider confirmed closed"),
            ("attention", "Needs attention"),
        ],
        default="draft",
        readonly=True,
        copy=False,
    )
    board_note = fields.Char(readonly=True, copy=False)
    board_values = fields.Json(
        readonly=True, copy=False, groups="pb_hiring.group_hiring_user"
    )
    board_idempotency = fields.Char(readonly=True, copy=False)

    @api.model_create_multi
    def create(self, vals_list):
        if not self.env.su and any(
            k.startswith("board_") for vals in vals_list for k in vals
        ):
            raise AccessError(
                _("Board delivery evidence is maintained by the verified integration.")
            )
        return super().create(vals_list)

    def write(self, vals):
        if (
            not self.env.su
            and {"state", "external_url", "posted_on", "closed_on"} & vals.keys()
            and self.filtered("board_reference")
        ):
            raise AccessError(
                _("Use the provider workflow for this API-managed listing.")
            )
        if any(k.startswith("board_") for k in vals) and not self.env.su:
            raise AccessError(
                _("Board delivery evidence is maintained by the verified integration.")
            )
        return super().write(vals)

    def _board_conn(self):
        self.ensure_one()
        provider = contracts.BOARD_PROVIDERS.get(self.channel_id.key)
        conn = self.env["pb.hiring.connection"]._for_company(provider, self.company_id)
        if not conn:
            raise UserError(_("Complete this board in Hiring connections first."))
        if self.board_connection_id and conn != self.board_connection_id:
            raise UserError(_("This posting belongs to another connection."))
        conn._ready()
        return conn

    def _board_send(self, values, operation):
        self.ensure_one()
        req = self.requisition_id
        if operation not in ("CREATE", "UPDATE", "CLOSE"):
            raise UserError(_("Unsupported board operation."))
        if operation != "CLOSE" and not self.channel_id._applies_to(req):
            raise UserError(_("This channel is not enabled for this role and country."))
        if operation != "CLOSE" and req.is_confidential:
            raise UserError(
                _("A confidential role cannot be sent to a public job board.")
            )
        if not req.job_id:
            raise UserError(_("Publish the approved role on the careers page first."))
        if operation != "CLOSE" and not req.job_id.is_published:
            raise UserError(
                _("The careers page must be published before board submission.")
            )
        conn = self._board_conn()
        cfg = conn._config()
        if cfg.get("environment") == "playground":
            raise UserError(
                _(
                    "SEEK Playground is read-only. Ask SEEK for an unsearchable test hirer to test publishing."
                )
            )
        if self.board_state in ("queued", "pending"):
            raise UserError(
                _(
                    "Check the pending provider operation before sending another request."
                )
            )
        if operation == "CREATE" and self.board_reference:
            raise UserError(
                _("Check provider status first. Use Update for an existing listing.")
            )
        if operation in ("UPDATE", "CLOSE") and not self.board_reference:
            raise UserError(_("Submit the advert before updating or closing it."))
        reference = self.board_reference or "%s-%s-%s" % (
            self.env["ir.config_parameter"].sudo().get_param("database.uuid"),
            req.id,
            self.channel_id.key,
        )
        idem = self.board_idempotency or str(uuid.uuid4())
        values = dict(
            values,
            apply_url=self._link(),
            listed_at=int(req.create_date.timestamp() * 1000),
        )
        if urlsplit(values["apply_url"]).scheme != "https":
            raise UserError(_("Use an HTTPS careers application address."))
        try:
            if conn.provider == "linkedin":
                contracts.linkedin_job(
                    values,
                    cfg,
                    reference,
                    "https://example.invalid/callback",
                    operation,
                )
            elif operation != "CLOSE":
                contracts.seek_profile(values, cfg, reference, idem)
        except ValueError as exc:
            raise UserError(str(exc)) from None
        # The UI only queues intent. A separate worker commits pending before HTTP.
        self.sudo().write(
            {
                "board_reference": reference,
                "board_idempotency": idem,
                "board_values": values,
                "board_connection_id": conn.id,
                "board_operation": operation,
                "board_state": "queued",
                "board_note": _(
                    "Queued for submission. The background worker will contact the provider."
                ),
            }
        )
        return True

    def _board_request_close(self):
        for rc in self:
            if not rc.board_reference or rc.board_state == "closed":
                continue
            if rc.board_state == "queued" and rc.board_operation == "CREATE":
                rc.sudo().write(
                    {
                        "board_reference": False,
                        "board_connection_id": False,
                        "board_idempotency": False,
                        "board_state": "draft",
                        "board_operation": False,
                        "board_close_requested": False,
                        "board_note": _(
                            "Cancelled before provider submission because the role is no longer public."
                        ),
                    }
                )
                continue
            rc.sudo().write({"board_close_requested": True})
            if rc.board_state not in ("queued", "pending"):
                try:
                    with self.env.cr.savepoint():
                        rc._board_send(rc.board_values or {}, "CLOSE")
                except Exception:
                    rc.sudo().write(
                        {
                            "board_note": _(
                                "Role is no longer public. Board closure still needs provider access and confirmation."
                            )
                        }
                    )

    def _board_deliver(self):
        self.ensure_one()
        if self.board_state != "pending":
            raise UserError(_("The delivery has not been claimed."))
        conn = self._board_conn()
        cfg = conn._config()
        if self.board_operation != "CLOSE" and (
            self.requisition_id.is_confidential
            or not self.requisition_id.job_id.is_published
        ):
            raise UserError(_("The role is no longer public; delivery was stopped."))
        values = self.board_values
        reference = self.board_reference
        idem = self.board_idempotency
        operation = self.board_operation
        try:
            if conn.provider == "linkedin":
                callback = conn._card()["callback"]
                payload = contracts.linkedin_job(
                    values, cfg, reference, callback, operation
                )
                data = conn._li("POST", "simpleJobPostings", json=payload)
                elements = data.get("elements") or []
                if (
                    len(elements) != 1
                    or elements[0].get("status") not in (200, 201, 202)
                    or not elements[0].get("id")
                ):
                    raise UserError(
                        _(
                            "The board did not acknowledge this job operation. Check its status before retrying."
                        )
                    )
                self.sudo().write({"board_task_id": elements[0]["id"]})
            else:
                if operation == "CLOSE":
                    if not self.board_remote_id:
                        raise UserError(
                            _("Check the posted profile identifier before closing.")
                        )
                    conn._seek(
                        contracts.SEEK_CLOSE,
                        {
                            "input": {
                                "positionProfile": {"profileId": self.board_remote_id}
                            }
                        },
                    )
                else:
                    payload = contracts.seek_profile(values, cfg, reference, idem)
                    if operation == "UPDATE":
                        if not self.board_remote_id:
                            raise UserError(
                                _(
                                    "Check the posted profile identifier before updating."
                                )
                            )
                        profile = payload["positionProfile"]
                        profile["profileId"] = self.board_remote_id
                        profile["postingInstructions"][0].pop("idempotencyId", None)
                        conn._seek(
                            contracts.SEEK_UPDATE,
                            {"input": {"positionProfile": profile}},
                        )
                    else:
                        data = conn._seek(contracts.SEEK_POST, {"input": payload})[
                            "postPosition"
                        ]
                        profile = (
                            data.get("positionProfile")
                            or data.get("conflictingPositionProfile")
                            or {}
                        )
                        remote = (profile.get("profileId") or {}).get("value")
                        if not remote:
                            raise UserError(
                                _("The provider did not return a posting reference.")
                            )
                        self.sudo().write({"board_remote_id": remote})
        except Exception as exc:
            note = (
                str(exc)
                if isinstance(exc, (UserError, ValueError))
                else _("Provider delivery could not be verified.")
            )
            self.sudo().write({"board_state": "attention", "board_note": note[:1000]})
        return True

    def _board_refresh(self):
        self.ensure_one()
        conn = self._board_conn()
        if self.board_state == "queued":
            raise UserError(_("The submission has not left Payobook yet."))
        if not self.board_reference:
            raise UserError(_("No API submission exists yet."))
        if conn.provider == "linkedin":
            if self.board_task_id:
                task = conn._li(
                    "GET", "simpleJobPostingTasks", params={"ids": self.board_task_id}
                )
                results = list((task.get("results") or {}).values())
                if (
                    not results
                    or task.get("errors")
                    or any(x.get("status") == "FAILED" for x in results)
                ):
                    self.sudo().write(
                        {
                            "board_state": "attention",
                            "board_note": _(
                                "Provider task failed or is unavailable. Review the provider console before retrying."
                            ),
                        }
                    )
                    return
                if any(x.get("status") != "SUCCEEDED" for x in results):
                    return
            data = conn._li(
                "GET", "jobPostingStatus", params={"ids": self.board_reference}
            )
            status = (data.get("results") or {}).get(self.board_reference) or {}
            listed = status.get("listingStatus") == "LISTED"
            closed = (
                status.get("listingStatus") == "NOT_LISTED"
                and self.board_operation == "CLOSE"
            )
            url = status.get("jobPostingUrl") or ""
            note = "Listing: %s; native apply: %s; promotion: %s" % (
                status.get("listingStatus", "Unknown"),
                status.get("linkedInApplyStatus", "Unknown"),
                status.get("promotionStatus", "Unknown"),
            )
            note += "; location: " + str(status.get("rawLocation") or "")
            for key in (
                "listingStatusDetail",
                "linkedInApplyStatusDetail",
                "promotionStatusDetail",
            ):
                if status.get(key):
                    note += (
                        "; "
                        + key
                        + ": "
                        + json.dumps(status[key], ensure_ascii=False)[:1500]
                    )
        else:
            if not self.board_remote_id:
                raise UserError(
                    _(
                        "Provider reference is missing; reconcile the submission with SEEK before retrying."
                    )
                )
            status = (
                conn._seek(contracts.SEEK_STATUS, {"id": self.board_remote_id}).get(
                    "positionProfile"
                )
                or {}
            )
            owners = [x["id"]["value"] for x in status.get("positionOrganizations", [])]
            if conn._config()["hirer_id"] not in owners:
                raise UserError(
                    _(
                        "This posting does not belong to the configured hiring organization."
                    )
                )
            code = status.get("seekStatusCode")
            listed = code == "Active"
            closed = code == "Expired"
            url = status.get("positionUri") or ""
            note = "Provider status: " + str(code or "Pending")
        vals = {
            "board_note": note,
            "board_state": "live" if listed else "closed" if closed else "pending",
        }
        if listed:
            vals.update(
                state="posted", posted_on=fields.Date.today(), posted_by=self.env.uid
            )
        elif closed:
            vals.update(state="closed", closed_on=fields.Date.today())
        if url and urlsplit(url).scheme == "https":
            vals["external_url"] = url
        if closed:
            vals["board_close_requested"] = False
        self.sudo().write(vals)
        if listed and self.board_close_requested:
            self._board_send(self.board_values, "CLOSE")


BOARD_FIELDS = (
    "title",
    "description",
    "location",
    "summary",
    "native_apply",
    "location_id",
    "category_id",
    "product_id",
    "currency",
    "salary_min",
    "salary_max",
    "pay_interval",
    "work_type",
    "arrangement",
)


class BoardReview(models.TransientModel):
    _name = "pb.hiring.board.review"
    _description = "Review board publishing"

    role_channel_id = fields.Many2one(
        "pb.hiring.role.channel", required=True, readonly=True
    )
    provider = fields.Char(compute="_compute_summary")
    status = fields.Text(compute="_compute_summary")
    intake_summary = fields.Text(compute="_compute_summary")
    delivery_state = fields.Char(compute="_compute_summary")
    title = fields.Char(required=True)
    description = fields.Html(required=True, sanitize=True)
    location = fields.Char(string="City, country", required=True)
    summary = fields.Char(string="Search summary")
    native_apply = fields.Boolean(
        string="Accept applications on the board", default=True
    )
    location_id = fields.Char(string="SEEK location identifier")
    category_id = fields.Char(string="SEEK job category identifier")
    product_id = fields.Char(string="Approved ad product identifier")
    currency = fields.Char(string="Salary currency (ISO code)")
    salary_min = fields.Float(string="Salary from")
    salary_max = fields.Float(string="Salary to")
    pay_interval = fields.Selection(
        [("Year", "Year"), ("Month", "Month"), ("Hour", "Hour")],
        string="Salary interval",
        default="Year",
    )
    work_type = fields.Selection(
        [
            ("FullTime", "Full time"),
            ("PartTime", "Part time"),
            ("ContractTemp", "Contract"),
            ("Casual", "Casual"),
        ],
        default="FullTime",
    )
    arrangement = fields.Selection(
        [("OnSite", "On site"), ("Hybrid", "Hybrid"), ("Remote", "Remote")],
        default="OnSite",
    )
    confirmed = fields.Boolean(
        string="I reviewed this advert, the selected environment and any provider charges"
    )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            rc = self.env["pb.hiring"]._p7_row(
                {"role_channel_id": vals.get("role_channel_id")}
            )
            rc.with_env(self.env).check_access("read")
            if rc.company_id not in self.env.companies:
                raise AccessError(_("This role belongs to another company."))
        return super().create(vals_list)

    def write(self, vals):
        if "role_channel_id" in vals:
            raise AccessError(_("Open a new review to select another role."))
        return super().write(vals)

    def _compute_summary(self):
        for w in self:
            rc = w.role_channel_id
            w.provider = contracts.BOARD_PROVIDERS.get(rc.channel_id.key, "")
            conn = self.env["pb.hiring.connection"]._for_company(
                w.provider, rc.company_id
            )
            w.status = "%s · %s · %s" % (
                rc.channel_id.name,
                conn._config().get("environment", "Not configured"),
                rc.board_note or "Provider approval and end-to-end acceptance required",
            )
            w.delivery_state = rc.board_state
            events = (
                self.env["pb.hiring.board.event"]
                .sudo()
                .search([("role_channel_id", "=", rc.id)])
            )
            failed = events.filtered(lambda e: e.state == "failed")
            w.intake_summary = _(
                "%(done)s imported · %(queued)s waiting · %(failed)s need attention",
                done=len(events.filtered(lambda e: e.state == "done")),
                queued=len(events.filtered(lambda e: e.state == "queued")),
                failed=len(failed),
            )
            if failed:
                w.intake_summary += "\n" + (failed[-1].note or "")

    def _gate(self):
        self.ensure_one()
        self.check_access("write")
        self.role_channel_id.check_access("read")
        if self.role_channel_id.company_id not in self.env.companies:
            raise AccessError(_("This role belongs to another company."))
        self.env["pb.hiring"]._require_recruit(self.role_channel_id.requisition_id)
        return self.role_channel_id

    def _values(self):
        keys = BOARD_FIELDS
        if (
            not (self.title or "").strip()
            or not html2plaintext(self.description or "").strip()
            or not (self.location or "").strip()
        ):
            raise UserError(_("Complete the title, advert and city/country."))
        return {k: self[k] for k in keys}

    def action_save(self):
        rc = self._gate()
        rc.sudo().write({"board_values": self._values()})
        return {"type": "ir.actions.act_window_close"}

    def _submit(self, operation):
        rc = self._gate()
        if not self.confirmed:
            raise UserError(
                _(
                    "Review the advert and confirm the environment and provider charges first."
                )
            )
        rc._board_send(self._values(), operation)
        return {"type": "ir.actions.act_window_close"}

    def action_submit(self):
        return self._submit("CREATE")

    def action_update(self):
        return self._submit("UPDATE")

    def action_close_listing(self):
        return self._submit("CLOSE")

    def action_refresh(self):
        self._gate()._board_refresh()
        return self.env["pb.hiring"].board_open(self.role_channel_id.id)

    def action_retry_intake(self):
        rc = self._gate()
        failed = (
            self.env["pb.hiring.board.event"]
            .sudo()
            .search([("role_channel_id", "=", rc.id), ("state", "=", "failed")])
        )
        failed.filtered("payload").write({"state": "queued", "note": False})
        return {"type": "ir.actions.act_window_close"}


class BoardEvent(models.Model):
    _name = "pb.hiring.board.event"
    _description = "Job board application receipt"
    _order = "id"
    connection_id = fields.Many2one(
        "pb.hiring.connection", required=True, ondelete="cascade"
    )
    external_id = fields.Char(required=True, index=True)
    role_channel_id = fields.Many2one("pb.hiring.role.channel", ondelete="set null")
    applicant_id = fields.Many2one("hr.applicant", ondelete="set null")
    payload = fields.Text(groups="base.group_system", copy=False)
    state = fields.Selection(
        [
            ("queued", "Waiting"),
            ("done", "Imported"),
            ("failed", "Needs attention"),
            ("removed", "Removed"),
        ],
        default="queued",
    )
    note = fields.Char()
    _event_unique = models.Constraint(
        "unique(connection_id, external_id)", "This board event was already received."
    )

    @api.model
    def _enqueue(self, conn, external_id, payload, rc=None):
        if (
            not isinstance(external_id, str)
            or not external_id
            or len(external_id) > 1000
        ):
            raise ValueError("Invalid event identifier")
        # Same-application webhook deliveries serialize without a uniqueness crash.
        self.env.cr.execute(
            "SELECT pg_advisory_xact_lock(hashtextextended(%s,0))",
            [f"board-event:{conn.id}:{external_id}"],
        )
        existing = self.sudo().search(
            [("connection_id", "=", conn.id), ("external_id", "=", external_id)],
            limit=1,
        )
        if existing:
            return existing
        return self.sudo().create(
            {
                "connection_id": conn.id,
                "external_id": external_id,
                "role_channel_id": rc.id if rc else False,
                "payload": encrypt(self.env, json.dumps(payload)),
            }
        )

    def _import_one(self):
        self.ensure_one()
        if self.state != "queued" or not self.payload:
            return
        conn = self.connection_id
        conn._ready()
        data = json.loads(decrypt(self.env, self.payload))
        if conn.provider == "linkedin":
            appdata = data
        else:
            profile = conn._seek(
                contracts.SEEK_APPLICATION, {"id": data["profile_id"]}
            ).get("candidateProfile")
            if not profile:
                raise UserError(_("The provider application is not available."))
            appdata = contracts.seek_application(profile, conn._config()["hirer_id"])
        field = "board_reference" if conn.provider == "linkedin" else "board_remote_id"
        rc = (
            self.env["pb.hiring.role.channel"]
            .sudo()
            .search(
                [
                    ("board_connection_id", "=", conn.id),
                    (field, "=", appdata["job_id"]),
                    ("company_id", "=", conn.company_id.id),
                ],
                limit=1,
            )
        )
        if not rc:
            raise UserError(
                _(
                    "No matching role for this provider and company. Reconcile the posting reference before retrying."
                )
            )
        self.role_channel_id = rc
        email = email_normalize(appdata["email"])
        if not email:
            raise UserError(_("The application email is invalid."))
        self.env.cr.execute(
            "SELECT pg_advisory_xact_lock(hashtextextended(%s,0))",
            [f"board-app:{rc.requisition_id.id}:{email}"],
        )
        Applicant = self.env["hr.applicant"].sudo().with_context(active_test=False)
        app = Applicant.search(
            [
                ("pb_requisition_id", "=", rc.requisition_id.id),
                ("email_normalized", "=", email),
            ],
            limit=1,
        )
        if app and app.pb_anonymised_on:
            self.write(
                {
                    "state": "removed",
                    "payload": False,
                    "note": _("Candidate was removed; this delivery was not imported."),
                }
            )
            return
        media = (
            conn._board_media(appdata["resume_url"])
            if appdata.get("resume_url")
            else None
        )
        if not app:
            app = Applicant.with_context(
                mail_create_nolog=True,
                mail_notrack=True,
                tracking_disable=True,
                pb_no_automation=True,
            ).create(
                {
                    "partner_name": appdata["name"][:200],
                    "email_from": email,
                    "partner_phone": appdata.get("phone", "")[:100],
                    "company_id": conn.company_id.id,
                    "pb_requisition_id": rc.requisition_id.id,
                    "job_id": rc.requisition_id.job_id.id,
                    "source_id": rc.channel_id.utm_source_id.id,
                    "pb_channel_id": rc.channel_id.id,
                    "stage_id": self.env["hr.recruitment.stage"]
                    ._pb_stage("screening")
                    .id,
                }
            )
        if media and not app._current_cv():
            raw, ext, mime = media
            self.env["ir.attachment"].sudo().create(
                {
                    "name": "board-application." + ext,
                    "raw": raw,
                    "mimetype": mime,
                    "res_model": "hr.applicant",
                    "res_id": app.id,
                    "pb_form_key": "cv",
                }
            )
        self.write(
            {
                "applicant_id": app.id,
                "state": "done",
                "payload": False,
                "note": _(
                    "Application imported. Review the CV and collect any missing role-specific answers and consent before advancing the candidate."
                )
                if media
                else _(
                    "Application imported without a CV. Obtain the original if required."
                ),
            }
        )

    @api.model
    def _run_queue(self):
        # Isolated committed claims prevent retries of ambiguous outbound effects.
        from odoo.modules.registry import Registry
        from odoo import SUPERUSER_ID

        with Registry(self.env.cr.dbname).cursor() as cr:
            worker = api.Environment(cr, SUPERUSER_ID, {})
            cr.execute(
                "SELECT id FROM pb_hiring_role_channel WHERE board_state='queued' ORDER BY id FOR UPDATE SKIP LOCKED LIMIT 1"
            )
            row = cr.fetchone()
            if row:
                rc = worker["pb.hiring.role.channel"].browse(row[0])
                rc.write(
                    {
                        "board_state": "pending",
                        "board_note": "Contacting provider; do not repeat submission.",
                    }
                )
                cr.commit()
                try:
                    with cr.savepoint():
                        rc._board_deliver()
                except Exception:
                    rc.write(
                        {
                            "board_state": "attention",
                            "board_note": "Delivery needs attention. Check the provider before any resubmission.",
                        }
                    )
                cr.commit()
            closing = worker["pb.hiring.role.channel"].search(
                [
                    ("board_close_requested", "=", True),
                    ("board_state", "in", ["live", "attention"]),
                ],
                limit=3,
            )
            closing._board_request_close()
            pending = worker["pb.hiring.role.channel"].search(
                [
                    ("board_state", "=", "pending"),
                    ("write_date", "<", fields.Datetime.now() - timedelta(minutes=5)),
                ],
                order="write_date",
                limit=3,
            )
            for rc in pending:
                try:
                    with cr.savepoint():
                        rc._board_refresh()
                except Exception:
                    rc.write(
                        {
                            "board_note": "Status verification failed. Check provider access; do not repeat submission."
                        }
                    )
            cr.execute(
                "SELECT id FROM pb_hiring_board_event WHERE state='queued' ORDER BY id FOR UPDATE SKIP LOCKED LIMIT 2"
            )
            for row in cr.fetchall():
                event = worker["pb.hiring.board.event"].browse(row[0])
                try:
                    with cr.savepoint():
                        event._import_one()
                except Exception:
                    event.write(
                        {
                            "state": "failed",
                            "note": "Application intake failed. Check provider access and role mapping, then retry intake from the board publishing review.",
                        }
                    )
            worker["pb.hiring.board.event"].search(
                [
                    ("payload", "!=", False),
                    ("create_date", "<", fields.Datetime.now() - timedelta(days=30)),
                ]
            ).write(
                {
                    "payload": False,
                    "state": "removed",
                    "note": "Unprocessed intake content expired after 30 days.",
                }
            )
            cr.commit()


class BoardApplicantPrivacy(models.Model):
    _inherit = "hr.applicant"

    def _pb_anonymise(self):
        self.env["pb.hiring.board.event"].sudo().search(
            [("applicant_id", "in", self.ids)]
        ).write(
            {"payload": False, "state": "removed", "note": "Candidate data removed."}
        )
        return super()._pb_anonymise()


class BoardJobPublication(models.Model):
    _inherit = "hr.job"

    def write(self, vals):
        result = super().write(vals)
        if ("website_published" in vals and not vals["website_published"]) or (
            "is_published" in vals and not vals["is_published"]
        ):
            self.env["pb.hiring.role.channel"].sudo().search(
                [
                    ("requisition_id.job_id", "in", self.ids),
                    ("board_reference", "!=", False),
                ]
            )._board_request_close()
        return result
