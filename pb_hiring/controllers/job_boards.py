"""Authenticate and enqueue provider callbacks without making external calls."""

import hashlib
import hmac
import json
from datetime import datetime, timezone

from odoo import http
from odoo.http import request
from ..services import job_boards as contracts


class HiringBoardWebhooks(http.Controller):
    @http.route(
        "/hiring/boards/<provider>/<key>",
        type="http",
        auth="public",
        methods=["GET", "POST"],
        csrf=False,
        save_session=False,
    )
    def webhook(self, provider, key, **params):
        if provider not in ("linkedin", "seek"):
            return request.make_response("", status=404)
        conn = (
            request.env["pb.hiring.connection"]
            .sudo()
            .search(
                [
                    ("provider", "=", provider),
                    ("webhook_key", "=", key),
                    ("enabled", "=", True),
                    ("check_ok", "=", True),
                ],
                limit=1,
            )
        )
        if not conn:
            return request.make_response("", status=403)
        try:
            conn._ready()
            secret = conn._secret(
                "client_secret" if provider == "linkedin" else "webhook_secret"
            )
        except Exception:
            return request.make_response("", status=403)
        if request.httprequest.method == "GET":
            challenge = params.get("challengeCode", "")
            if (
                provider != "linkedin"
                or not secret
                or not challenge
                or len(challenge) > 4096
                or params.get("applicationId") != conn._config().get("application_id")
            ):
                return request.make_response("", status=403)
            return request.make_json_response(
                {
                    "challengeCode": challenge,
                    "challengeResponse": hmac.new(
                        secret.encode(), challenge.encode(), hashlib.sha256
                    ).hexdigest(),
                }
            )
        raw = request.httprequest.stream.read(1024 * 1024 + 1)
        if len(raw) > 1024 * 1024:
            return request.make_response("", status=413)
        signature = request.httprequest.headers.get(
            "X-LI-Signature" if provider == "linkedin" else "Seek-Signature", ""
        )
        if not contracts.signed(provider, secret, raw, signature):
            return request.make_response("", status=403)
        try:
            data = json.loads(raw)
            if not isinstance(data, dict):
                raise ValueError()
            # Atomic batch validation: do not acknowledge a partially accepted batch.
            with request.env.cr.savepoint():
                Event = request.env["pb.hiring.board.event"].sudo()
                if provider == "linkedin":
                    app = contracts.linkedin_application(data)
                    rc = (
                        request.env["pb.hiring.role.channel"]
                        .sudo()
                        .search(
                            [
                                ("board_connection_id", "=", conn.id),
                                ("board_reference", "=", app["job_id"]),
                                ("company_id", "=", conn.company_id.id),
                            ],
                            limit=1,
                        )
                    )
                    if not rc:
                        raise ValueError()
                    Event._enqueue(conn, app["external_id"], app, rc)
                else:
                    expiry = datetime.fromisoformat(
                        data["expireDateTime"].replace("Z", "+00:00")
                    )
                    if not expiry.tzinfo or expiry <= datetime.now(timezone.utc):
                        raise ValueError()
                    events = data["events"]
                    if not isinstance(events, list) or not 1 <= len(events) <= 10:
                        raise ValueError()
                    for item in events:
                        if item.get(
                            "type"
                        ) != "CandidateApplicationCreated" or item.get(
                            "hirerId"
                        ) != conn._config().get("hirer_id"):
                            raise ValueError()
                        profile = item["candidateApplicationProfileId"]
                        if (
                            not isinstance(profile, str)
                            or not profile
                            or len(profile) > 1000
                        ):
                            raise ValueError()
                        Event._enqueue(conn, profile, {"profile_id": profile})
        except (ValueError, TypeError, KeyError, AttributeError):
            return request.make_response("", status=400)
        return request.make_response("", status=202)
