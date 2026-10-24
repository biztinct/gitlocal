"""Contract and permission tests; provider calls are mocked, no live adverts."""

import hashlib
import hmac
import io
import json
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock, patch

from odoo.http import Response
from odoo.exceptions import AccessError, UserError
from odoo.tests import tagged
from .test_channels_p7 import ChannelCase
from ..services import job_boards as contracts
from ..services.connection_crypto import encrypt
from ..controllers.job_boards import HiringBoardWebhooks


@tagged("post_install", "-at_install", "recruit_boards")
class TestJobBoards(ChannelCase):
    def setUp(self):
        super().setUp()
        self.env["ir.config_parameter"].sudo().set_param(
            "web.base.url", "https://payobook.example.com"
        )
        self.req.job_id.sudo().write({"is_published": True})
        rows = self._rows(self.req)
        self.rc = (
            self.env["pb.hiring.role.channel"].sudo().browse(rows["linkedin"]["id"])
        )
        self.conn = (
            self.env["pb.hiring.connection"]
            .sudo()
            .create(
                {
                    "provider": "linkedin",
                    "company_id": self.company.id,
                    "enabled": True,
                    "check_ok": True,
                    "settings": {
                        "environment": "test",
                        "organization_id": "urn:li:organization:123",
                        "application_id": "123",
                        "client_id": "client",
                        "approval_reference": "TEST resource",
                    },
                    "credentials": encrypt(
                        self.env, json.dumps({"client_secret": "unit-test-secret"})
                    ),
                }
            )
        )
        self.platform_patch = patch(
            "odoo.addons.pb_hiring.models.job_board_platform.read_platform",
            return_value={
                "client_id": "partner-test",
                "client_secret": "partner-secret",
                "tenant": {
                    "enabled": True,
                    "organization_id": "urn:li:organization:123",
                    "hirer_id": "hirer",
                    "webhook_secret": "test-secret",
                    "domain": "https://payobook.example.com",
                },
            },
        )
        self.platform_patch.start()
        self.addCleanup(self.platform_patch.stop)
        self.values = dict(
            title="DEMO board role",
            description="<p>Test only</p>",
            location="Hanoi, Vietnam",
            summary="Test role",
            native_apply=True,
            location_id="loc",
            category_id="cat",
            product_id="prod",
            currency="AUD",
            salary_min=50000,
            salary_max=60000,
            pay_interval="Year",
            work_type="FullTime",
            arrangement="Hybrid",
        )

    def _queue(self):
        self.rc._board_send(self.values, "CREATE")
        self.assertEqual(self.rc.board_state, "queued")
        self.assertNotEqual(self.rc.state, "posted")
        self.rc.write({"board_state": "pending"})

    def _event(self, external="application-1", **extra):
        self.rc.write({"board_reference": "job-1", "board_connection_id": self.conn.id})
        data = dict(
            external_id=external,
            job_id="job-1",
            name="DEMO Board Applicant",
            email="board.applicant@example.com",
            phone="",
            resume_url="",
        )
        data.update(extra)
        return self.env["pb.hiring.board.event"]._enqueue(
            self.conn, external, data, self.rc
        )

    def _webhook(self, data, provider="linkedin", valid=True, method="POST", **params):
        raw = json.dumps(data).encode()
        secret = self.conn._secret(
            "client_secret" if provider == "linkedin" else "webhook_secret"
        )
        signature = ("hmacsha256=" if provider == "linkedin" else "") + hmac.new(
            secret.encode(),
            raw,
            hashlib.sha256 if provider == "linkedin" else hashlib.sha512,
        ).hexdigest()
        req = Mock(
            env=self.env,
            httprequest=Mock(
                method=method,
                stream=io.BytesIO(raw),
                headers={
                    "X-LI-Signature"
                    if provider == "linkedin"
                    else "Seek-Signature": signature if valid else "invalid"
                },
            ),
        )
        req.make_response.side_effect = lambda body="", status=200: Response(
            body, status=status
        )
        req.make_json_response.side_effect = lambda body: Response(
            json.dumps(body), content_type="application/json"
        )
        with patch("odoo.addons.pb_hiring.controllers.job_boards.request", req):
            response = HiringBoardWebhooks().webhook(
                provider, self.conn.webhook_key, **params
            )
            return (
                json.loads(response.get_data())
                if response.content_type == "application/json"
                else response.status_code
            )

    def test_payload_contracts_and_signatures(self):
        v = dict(self.values, listed_at=123, apply_url="https://example.com/apply")
        payload = contracts.linkedin_job(
            v, self.conn._config(), "job", "https://example.com/hook"
        )["elements"][0]
        self.assertEqual(
            payload["onsiteApplyConfiguration"]["questions"]["resumeQuestions"][
                "resumeQuestionRequirement"
            ],
            "REQUIRED",
        )
        cfg = dict(
            hirer_id="hirer", contact_name="Test", contact_email="test@example.com"
        )
        profile = contracts.seek_profile(v, cfg, "ref", "idem")["positionProfile"]
        self.assertEqual(profile["offeredRemunerationPackage"]["basisCode"], "Salaried")
        self.assertNotIn("applicationMethods", profile["postingInstructions"][0])
        self.assertEqual(
            contracts.seek_profile(dict(v, pay_interval="Hour"), cfg, "ref", "idem")[
                "positionProfile"
            ]["offeredRemunerationPackage"]["basisCode"],
            "Hourly",
        )
        for provider, algorithm, prefix in [
            ("linkedin", hashlib.sha256, "hmacsha256="),
            ("seek", hashlib.sha512, ""),
        ]:
            sig = prefix + hmac.new(b"secret", b"{}", algorithm).hexdigest()
            self.assertTrue(contracts.signed(provider, "secret", b"{}", sig))
            self.assertFalse(contracts.signed(provider, "secret", b"{ }", sig))
            self.assertFalse(contracts.signed(provider, "", b"{}", sig))

    def test_media_host_and_redirect_boundaries(self):
        for url in (
            "http://www.linkedin.com/ambry/a",
            "https://www.linkedin.com.evil.test/ambry/a",
            "https://user@www.linkedin.com/ambry/a",
            "https://www.linkedin.com:444/ambry/a",
            "https://www.linkedin.com/other",
        ):
            with self.assertRaises(ValueError):
                contracts.media_url("linkedin", url)
        self.assertTrue(
            contracts.media_url("linkedin", "https://www.linkedin.com/ambry/?token=x")
        )
        response = Mock(status_code=302)
        response.__enter__ = Mock(return_value=response)
        response.__exit__ = Mock(return_value=False)
        with (
            patch.object(type(self.conn), "_board_token_value", return_value="test"),
            patch(
                "odoo.addons.pb_hiring.models.job_boards.requests.get",
                return_value=response,
            ),
        ):
            with self.assertRaises(UserError):
                self.conn._board_media("https://www.linkedin.com/ambry/?x=1")

    def test_setup_role_secret_and_identity_guards(self):
        facade = self.env["pb.hiring"].with_user(self.lead)
        card = facade.connection_save("linkedin", {"client_secret": "rotated-test"})
        self.assertNotIn("rotated-test", str(card))
        self.assertIn("/hiring/boards/linkedin/", card["callback"])
        with self.assertRaises(AccessError):
            self.facade.connection_save("linkedin", {})
        self.conn.write({"enabled": True, "check_ok": True})
        self._queue()
        with self.assertRaises(UserError):
            facade.connection_save(
                "linkedin", {"organization_id": "urn:li:organization:999"}
            )
        with self.assertRaises(AccessError):
            self.conn.with_user(self.lead).read(["board_token"])

    def test_delivery_evidence_cannot_be_forged(self):
        with self.assertRaises(AccessError):
            self.rc.with_user(self.recruiter).write({"board_state": "live"})
        with self.assertRaises(AccessError):
            self.env["pb.hiring.role.channel"].with_user(self.recruiter).create(
                {
                    "requisition_id": self.req.id,
                    "channel_id": self.rc.channel_id.id,
                    "board_state": "live",
                }
            )
        self._queue()
        with self.assertRaises(UserError):
            self.facade.act("p7_mark_posted", {"role_channel_id": self.rc.id})
        with self.assertRaises(AccessError):
            self.rc.with_user(self.recruiter).write({"state": "posted"})

    def test_queue_acknowledgement_is_not_live_and_no_duplicate_create(self):
        self._queue()
        with patch.object(
            type(self.conn),
            "_li",
            return_value={
                "elements": [{"status": 202, "id": "urn:li:simpleJobPostingTask:1"}]
            },
        ):
            self.rc._board_deliver()
        self.assertEqual(self.rc.board_state, "pending")
        self.assertNotEqual(self.rc.state, "posted")
        with self.assertRaises(UserError):
            self.rc._board_send(self.values, "CREATE")
        self.rc.write({"board_state": "attention"})
        with self.assertRaises(UserError):
            self.rc._board_send(self.values, "CREATE")

    def test_provider_confirmation_updates_and_closes(self):
        self._queue()
        self.rc.write({"board_task_id": "task"})
        confirmed = {
            "results": {
                self.rc.board_reference: {
                    "listingStatus": "LISTED",
                    "linkedInApplyStatus": "ENABLED",
                    "promotionStatus": "NOT_PROMOTED",
                    "jobPostingUrl": "https://www.linkedin.com/jobs/view/123",
                }
            }
        }
        with patch.object(
            type(self.conn),
            "_li",
            side_effect=[{"results": {"task": {"status": "SUCCEEDED"}}}, confirmed],
        ):
            self.rc._board_refresh()
        self.assertEqual(self.rc.board_state, "live")
        self.assertEqual(self.rc.state, "posted")
        self.rc._board_send(self.values, "UPDATE")
        self.assertEqual(self.rc.board_operation, "UPDATE")
        self.rc.write({"board_state": "live"})
        self.rc._board_send(self.values, "CLOSE")
        self.rc.write({"board_state": "pending"})
        with patch.object(
            type(self.conn),
            "_li",
            side_effect=[
                {"results": {"task": {"status": "SUCCEEDED"}}},
                {"results": {self.rc.board_reference: {"listingStatus": "NOT_LISTED"}}},
            ],
        ):
            self.rc._board_refresh()
        self.assertEqual(self.rc.state, "closed")

    def test_network_ambiguity_never_marks_posted(self):
        self._queue()
        with patch.object(type(self.conn), "_li", side_effect=TimeoutError()):
            self.rc._board_deliver()
        self.assertEqual(self.rc.board_state, "attention")
        self.assertNotEqual(self.rc.state, "posted")

    def test_confidential_unpublished_and_playground_gates(self):
        self.req.sudo().write({"is_confidential": True})
        with self.assertRaises(UserError):
            self.rc._board_send(self.values, "CREATE")
        self.req.sudo().write({"is_confidential": False})
        self.req.job_id.is_published = False
        with self.assertRaises(UserError):
            self.rc._board_send(self.values, "CREATE")
        self.req.job_id.is_published = True
        self.conn.settings = dict(self.conn.settings, environment="playground")
        with self.assertRaises(UserError):
            self.rc._board_send(self.values, "CREATE")

    def test_review_roundtrip_and_company_scope(self):
        action = self.facade.board_open(self.rc.id)
        wizard = (
            self.env["pb.hiring.board.review"]
            .with_user(self.recruiter)
            .browse(action["res_id"])
        )
        wizard.write(self.values)
        wizard.action_save()
        self.assertEqual(self.rc.board_values["title"], self.values["title"])
        with self.assertRaises(UserError):
            wizard.action_submit()
        wizard.confirmed = True
        wizard.action_submit()
        self.assertEqual(self.rc.board_state, "queued")
        other = self.env["res.company"].create({"name": "Board isolation"})
        self.req.sudo().write({"company_id": other.id})
        with self.assertRaises(AccessError):
            self.facade.board_open(self.rc.id)

    def test_intake_deduplicates_preserves_existing_and_erases_payload(self):
        event = self._event()
        event._import_one()
        app = event.applicant_id
        self.assertTrue(app)
        self.assertFalse(event.payload)
        self.assertEqual(event.state, "done")
        self.assertEqual(app.pb_channel_id, self.rc.channel_id)
        self.assertEqual(self._event(), event)
        again = self._event("application-2", name="Changed name")
        again._import_one()
        self.assertEqual(again.applicant_id, app)
        self.assertEqual(app.partner_name, "DEMO Board Applicant")
        app._pb_anonymise()
        self.assertEqual(event.state, "removed")
        self.assertFalse(again.payload)

    def test_imported_cv_uses_existing_parser_queue(self):
        cv = self.env["pb.hiring.connection"]._for_company("cv", self.company)
        if not cv:
            cv = self.env["pb.hiring.connection"].create(
                {"provider": "cv", "company_id": self.company.id}
            )
        cv.write({"enabled": True, "check_ok": True})
        event = self._event(resume_url="https://www.linkedin.com/ambry/?x=test")
        with patch.object(
            type(self.conn),
            "_board_media",
            return_value=(b"%PDF-1.4\nTest", "pdf", "application/pdf"),
        ):
            event._import_one()
        self.assertTrue(event.applicant_id._current_cv())
        self.assertEqual(event.applicant_id.pb_cv_state, "queued")

    def test_webhook_challenge_invalid_signature_and_duplicate(self):
        self._event()
        data = {
            "type": "EXPORT_JOB_APPLICATION",
            "externalJobId": "job-1",
            "jobApplicationId": "app-hook",
            "questionResponses": {
                "contactInformationQuestionResponses": {
                    "firstNameAnswer": {"value": "DEMO"},
                    "lastNameAnswer": {"value": "Board"},
                    "emailAnswer": {"value": "hook@example.com"},
                }
            },
        }
        self.assertEqual(self._webhook(data, valid=False), 403)
        self.assertEqual(self._webhook(data), 202)
        self.assertEqual(self._webhook(data), 202)
        self.assertEqual(
            self.env["pb.hiring.board.event"].search_count(
                [("connection_id", "=", self.conn.id), ("external_id", "=", "app-hook")]
            ),
            1,
        )
        challenge = self._webhook(
            {}, method="GET", challengeCode="challenge", applicationId="123"
        )
        self.assertEqual(
            challenge["challengeResponse"],
            hmac.new(b"unit-test-secret", b"challenge", hashlib.sha256).hexdigest(),
        )
        self.assertEqual(
            self._webhook(
                {}, method="GET", challengeCode="challenge", applicationId="other"
            ),
            403,
        )
        data["externalJobId"] = "someone-elses-role"
        self.assertEqual(self._webhook(data), 400)

    def test_seek_signed_batch_expiry_and_tenant_validation(self):
        self.conn.write(
            {
                "provider": "seek",
                "settings": {"hirer_id": "hirer"},
                "credentials": encrypt(
                    self.env, json.dumps({"webhook_secret": "test-secret"})
                ),
            }
        )
        data = {
            "expireDateTime": (
                datetime.now(timezone.utc) + timedelta(minutes=5)
            ).isoformat(),
            "events": [
                {
                    "id": "event",
                    "type": "CandidateApplicationCreated",
                    "hirerId": "hirer",
                    "candidateApplicationProfileId": "profile",
                }
            ],
        }
        self.assertEqual(self._webhook(data, provider="seek"), 202)
        data["events"][0]["hirerId"] = "other"
        self.assertEqual(self._webhook(data, provider="seek"), 400)
        data["expireDateTime"] = (
            datetime.now(timezone.utc) - timedelta(seconds=1)
        ).isoformat()
        self.assertEqual(self._webhook(data, provider="seek"), 400)

    def test_seek_post_update_close_and_confirm(self):
        self.conn.write(
            {
                "provider": "seek",
                "settings": {
                    "environment": "test",
                    "hirer_id": "hirer",
                    "contact_name": "Test",
                    "contact_email": "test@example.com",
                },
            }
        )
        ch = self._channel("jobstreet")
        ch.write({"every_country": True})
        self.rc = (
            self.env["pb.hiring.role.channel"]
            .sudo()
            .create({"requisition_id": self.req.id, "channel_id": ch.id})
        )
        self._queue()
        with patch.object(
            type(self.conn),
            "_seek",
            return_value={
                "postPosition": {
                    "__typename": "PostPositionPayload_Success",
                    "positionProfile": {"profileId": {"value": "profile"}},
                }
            },
        ):
            self.rc._board_deliver()
        self.assertEqual(self.rc.board_remote_id, "profile")
        with patch.object(
            type(self.conn),
            "_seek",
            return_value={
                "positionProfile": {
                    "seekStatusCode": "Active",
                    "positionOrganizations": [{"id": {"value": "hirer"}}],
                }
            },
        ):
            self.rc._board_refresh()
        self.assertEqual(self.rc.board_state, "live")
        self.rc._board_send(self.values, "UPDATE")
        self.rc.write({"board_state": "pending"})
        with patch.object(
            type(self.conn), "_seek", return_value={"updatePostedPositionProfile": {}}
        ) as call:
            self.rc._board_deliver()
        self.assertNotIn(
            "idempotencyId",
            call.call_args.args[1]["input"]["positionProfile"]["postingInstructions"][
                0
            ],
        )
        self.rc.write({"board_state": "live"})
        self.rc._board_send(self.values, "CLOSE")
        self.rc.write({"board_state": "pending"})
        with patch.object(
            type(self.conn), "_seek", return_value={"closePostedPositionProfile": {}}
        ):
            self.rc._board_deliver()
        with patch.object(
            type(self.conn),
            "_seek",
            return_value={
                "positionProfile": {
                    "seekStatusCode": "Expired",
                    "positionOrganizations": [{"id": {"value": "hirer"}}],
                }
            },
        ):
            self.rc._board_refresh()
        self.assertEqual(self.rc.board_state, "closed")

    def test_oauth_cache_and_failed_task(self):
        with patch.object(
            type(self.conn),
            "_board_json",
            return_value={"access_token": "test-access", "expires_in": 3600},
        ) as call:
            self.assertEqual(self.conn._board_token_value(), "test-access")
            self.assertEqual(self.conn._board_token_value(), "test-access")
            self.assertEqual(call.call_count, 1)
        self.assertNotIn("test-access", self.conn.board_token)
        self._queue()
        self.rc.write({"board_task_id": "task"})
        with patch.object(
            type(self.conn),
            "_li",
            return_value={"results": {"task": {"status": "FAILED"}}},
        ):
            self.rc._board_refresh()
        self.assertEqual(self.rc.board_state, "attention")

    def test_shared_partner_account_cannot_be_rebound_by_tenant(self):
        self.conn.write(
            {
                "provider": "seek",
                "settings": {"environment": "test", "hirer_id": "another-tenant"},
            }
        )
        with self.assertRaises(UserError):
            self.conn._partner_config()
        with self.assertRaises(UserError):
            self.conn._board_token_value()
        self.assertFalse(self.env["pb.hiring"].connection_check("seek")["check_ok"])

    def test_partner_secret_stays_server_side(self):
        self.conn.write(
            {
                "provider": "seek",
                "settings": {"environment": "test", "hirer_id": "hirer"},
            }
        )
        card = self.conn._card()
        self.assertNotIn("partner-secret", str(card))
        self.assertNotIn("client_secret", [f["key"] for f in card["fields"]])
        self.assertEqual(
            card["tenant_reference"], self.env.cr.dbname + ":" + str(self.company.id)
        )
        with patch.object(
            type(self.conn),
            "_board_json",
            return_value={"access_token": "partner-access", "expires_in": 3600},
        ) as call:
            self.conn._board_token_value()
        self.assertEqual(call.call_args.kwargs["json"]["client_id"], "partner-test")

    def test_linkedin_child_provisioning_and_duplicate_guard(self):
        self.conn.settings = dict(self.conn.settings, application_id="", client_id="")
        facade = self.env["pb.hiring"].with_user(self.lead)
        facade.board_provision_customer()
        self.assertEqual(self.conn.board_provision_state, "queued")
        with self.assertRaises(UserError):
            facade.board_provision_customer()
        self.conn.board_provision_state = "pending"
        with patch.object(
            type(self.conn),
            "_board_json",
            side_effect=[
                {"access_token": "parent-access"},
                {
                    "key": "urn:li:developerApplication:777",
                    "credentials": {
                        "client_id": "child-id",
                        "client_secret": "child-secret",
                    },
                },
            ],
        ) as call:
            self.conn._provision_child()
        self.assertEqual(self.conn._config()["application_id"], "777")
        self.assertEqual(self.conn._secret("client_secret"), "child-secret")
        self.assertNotIn("child-secret", str(self.conn._card()))
        self.assertFalse(self.conn.enabled)
        self.assertTrue(
            call.call_args.kwargs["json"]["uniqueForeignId"].startswith("payobook-")
        )
        with self.assertRaises(UserError):
            facade.board_provision_customer()

    def test_platform_file_scope_and_permissions(self):
        import tempfile, os
        from ..services.board_platform import read_platform

        with tempfile.NamedTemporaryFile(mode="w+", suffix=".json") as f:
            json.dump(
                {
                    "seek": {
                        "test": {
                            "client_id": "partner",
                            "client_secret": "secret",
                            "tenants": {
                                "database-one:1": {"enabled": True, "hirer_id": "one"}
                            },
                        }
                    }
                },
                f,
            )
            f.flush()
            with patch(
                "odoo.addons.pb_hiring.services.board_platform.CONFIG_FILE", f.name
            ):
                self.assertEqual(
                    read_platform("seek", "test", "database-one:1")["tenant"][
                        "hirer_id"
                    ],
                    "one",
                )
                with self.assertRaises(ValueError):
                    read_platform("seek", "test", "database-two:1")
                os.chmod(f.name, 0o644)
                with self.assertRaises(ValueError):
                    read_platform("seek", "test", "database-one:1")

    def test_unpublish_queues_provider_closure_without_false_confirmation(self):
        self._queue()
        self.rc.write({"board_state": "live", "state": "posted"})
        self.req._close_job()
        self.assertEqual(self.rc.board_operation, "CLOSE")
        self.assertEqual(self.rc.board_state, "queued")
        self.assertEqual(self.rc.state, "posted")
        self.assertTrue(self.rc.board_close_requested)

    def test_unpublish_cancels_unsent_creation(self):
        self.rc._board_send(self.values, "CREATE")
        self.req._close_job()
        self.assertFalse(self.rc.board_reference)
        self.assertEqual(self.rc.board_state, "draft")

    def test_closure_waits_for_pending_create_confirmation(self):
        self._queue()
        self.req._close_job()
        self.assertTrue(self.rc.board_close_requested)
        self.assertEqual(self.rc.board_operation, "CREATE")
        with patch.object(
            type(self.conn),
            "_li",
            return_value={
                "results": {self.rc.board_reference: {"listingStatus": "LISTED"}}
            },
        ):
            self.rc._board_refresh()
        self.assertEqual(self.rc.board_operation, "CLOSE")
        self.assertEqual(self.rc.board_state, "queued")

    def test_uncertified_shared_app_cannot_activate_production(self):
        self.conn.settings = dict(self.conn.settings, environment="production")
        with self.assertRaises(UserError):
            self.conn._ready()
        card = self.env["pb.hiring"].connection_check("linkedin")
        self.assertFalse(card["check_ok"])
        self.assertFalse(card["enabled"])
