# Part of Payobook. See LICENSE file for full copyright and licensing details.
"""Two add-only seams so other work can reuse the late handling (WF2 P4a).

1. `biz.approval.engine._escalate_extra(now)` runs at the end of the hourly
   "remind and pass up what is late" job, inside its own savepoint. A fault in
   it is logged once and never stops approval reminders (they have already
   been queued by then). The default does nothing.

2. `biz.approval.outbox._deliver` can deliver a row that has no approval
   request: when its payload names a record (`res_model`, `res_id`) and the
   words (`summary`, `body`), the note is posted on that record to that one
   person, exactly the way an approval reminder is posted (same subtype, same
   per-person delivery preference). Rows with a request are delivered as
   before, untouched.

Method-only file: a restart loads it, no upgrade needed (ledger G29).
"""
import logging

from markupsafe import Markup, escape

from odoo import api, fields, models

_logger = logging.getLogger(__name__)


class BizApprovalEngineLateExtra(models.AbstractModel):
    _inherit = 'biz.approval.engine'

    @api.model
    def escalate_cron(self):
        result = super().escalate_cron()
        try:
            with self.env.cr.savepoint():
                self._escalate_extra(fields.Datetime.now())
        except Exception:  # noqa: BLE001 — another area's fault never stops approvals
            _logger.exception('biz_approval_workflow: extra late handling failed')
        return result

    @api.model
    def _escalate_extra(self, now):
        """Hook: other areas remind and pass up their own late work here,
        through the same outbox. Default: nothing."""
        return None


class BizApprovalOutboxRecordNote(models.Model):
    _inherit = 'biz.approval.outbox'

    def _record_target(self):
        """The record a request-less row is about, or None."""
        payload = self.payload or {}
        model, ident = payload.get('res_model'), payload.get('res_id')
        if self.request_id or not model or model not in self.env or type(ident) is not int:
            return None
        record = self.env[model].sudo().browse(ident).exists()
        return record if record and hasattr(record, 'message_post') else None

    def _deliver(self):
        self.ensure_one()
        record = self._record_target()
        if record is None:
            return super()._deliver()
        payload = self.payload or {}
        lines = [escape(line) for line in str(payload.get('body') or '').split('\n') if line.strip()]
        body = Markup('<br/>').join(lines) if lines else escape(payload.get('summary') or '')
        record.message_post(
            body=body, subject=str(payload.get('summary') or '')[:200],
            partner_ids=self.user_id.partner_id.ids,
            message_type='notification', subtype_xmlid='mail.mt_note')
        return True
