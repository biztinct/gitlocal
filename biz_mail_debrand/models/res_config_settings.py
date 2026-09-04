# Part of biz_mail_debrand — portable outgoing-email white-label layer.
# License LGPL-3.
import logging

from odoo import api, models

from .debrand import debrand_html, debrand_text

_logger = logging.getLogger(__name__)


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    # ------------------------------------------------------------------
    # Idempotent data scrub — runs on install AND every upgrade via the
    # data/apply.xml <function> record (same pattern as biz_debrand).
    # ------------------------------------------------------------------
    @api.model
    def _biz_mail_debrand_apply(self):
        env = self.env
        icp = env["ir.config_parameter"].sudo()
        lang_codes = env["res.lang"].search([]).mapped("code") or ["en_US"]

        # --- stored mail.template records (all languages) -------------
        templates = env["mail.template"].sudo().with_context(active_test=False).search([])
        touched = 0
        for lang in lang_codes:
            for template in templates.with_context(lang=lang):
                vals = {}
                for field in ("name", "subject"):
                    value = template[field]
                    scrubbed = debrand_text(env, value)
                    if scrubbed != value:
                        vals[field] = scrubbed
                body = template.body_html
                scrubbed_body = debrand_html(env, body)
                if str(scrubbed_body or "") != str(body or ""):
                    vals["body_html"] = scrubbed_body
                if vals:
                    template.write(vals)
                    touched += 1
        # email_from is not translated — scrub once (fixes stock templates
        # hardcoding noreply@odoo.com)
        for template in templates:
            if template.email_from:
                scrubbed = debrand_text(env, template.email_from)
                if scrubbed != template.email_from:
                    template.email_from = scrubbed
                    touched += 1

        # --- digest: rename + disable (opt out via config parameter) --
        if not icp.get_param("biz_mail_debrand.disable_digest"):
            icp.set_param("biz_mail_debrand.disable_digest", "1")
        disable_digest = icp.get_param("biz_mail_debrand.disable_digest") not in (
            "0", "False", "off",
        )
        digests = env["digest.digest"].sudo().with_context(active_test=False).search([])
        for lang in lang_codes:
            for digest in digests.with_context(lang=lang):
                scrubbed = debrand_text(env, digest.name)
                if scrubbed != digest.name:
                    digest.name = scrubbed
        if disable_digest:
            digests.filtered(lambda d: d.state == "activated").write(
                {"state": "deactivated"}
            )
            icp.set_param("digest.default_digest_emails", False)
            cron = env.ref(
                "digest.ir_cron_digest_scheduler_action", raise_if_not_found=False
            )
            if cron:
                cron.sudo().active = False

        _logger.info(
            "biz_mail_debrand: scrubbed %s mail.template values across %s langs; "
            "digest disabled=%s (%s digest record(s))",
            touched, len(lang_codes), disable_digest, len(digests),
        )
        return True
