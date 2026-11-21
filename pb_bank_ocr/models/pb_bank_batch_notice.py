# -*- coding: utf-8 -*-
"""WDGAP W3-C follow-up: ONE notice per approver per batch of bank changes.

WHAT WAS TRUE BEFORE. Bank changes held as a batch — a pay data file or the
old Vietnam employee import (BK2), a connected system's records refresh, or a
batch made on purpose (BG1: "Bank details already on record — copy to the
bank file") — are one approval EACH. The approvals engine queues "Your
approval is needed" per approval and per approver, and its delivery job turns
every row into a message (an email for people who read by email) and a to-do.
A 615-person batch gave each approver 615 to-dos and 1,230 emails, and the
engine never closes a to-do after the decision (W3-C rehearsal, ledger W3C-4).

WHAT IS TRUE NOW. For a change in a batch (`pb_origin == 'import'` with a
`pb_import_key`):
  * "Your approval is needed", "Still waiting" and "Overdue" are queued ONCE
    per approver per batch (the outbox's own dedupe key, made per batch). The
    one to-do names the count and points to Compliance › Bank ("Approve all
    in this file"); the one message is the only email. A later reminder or
    escalation for somebody who already has the batch's to-do updates that
    to-do and sends nothing.
  * The to-do's count follows the batch: after each decision it says how many
    are still waiting, and when none is waiting (all approved, turned down,
    sent back or withdrawn) every batch to-do is marked done. A notice still
    queued when the batch is already decided is never delivered.
  * The person who sent the batch hears "approved" once, when the last change
    of the batch is approved — not once per person.
Single bank changes (My Payobook, HR's bank screen, the Updates sheet) are
untouched: no key, so everything runs exactly as before. Who may decide (the
second-person rule, never the proposer) is not touched either.
"""

import logging

from markupsafe import Markup

from odoo import _, api, fields, models

from .pb_bank_import_hold import NEWHIRE_KEY_PREFIX

_logger = logging.getLogger(__name__)

BANK_MODEL = 'pb.bank.change.request'
WAITING_STATES = ('hr_review', 'finance_review')
#: kinds sent to approvers once per batch (a to-do each)
BATCH_TODO_KINDS = ('your_turn', 'reminder', 'escalation')
#: kinds sent to the proposer once per batch (a message, no to-do)
BATCH_ONCE_KINDS = ('approved',)
BANK_SCREEN_URL = '/web#action=pb_bank_ocr.action_pb_bank_ocr'


def _batch_of(request):
    """(key, label) when this approval belongs to a batch of bank changes."""
    if not request or request.res_model != BANK_MODEL or not request.res_id:
        return None
    rec = request.env[BANK_MODEL].sudo().browse(request.res_id).exists()
    if not rec or rec.pb_origin != 'import' or not rec.pb_import_key:
        return None
    if rec.pb_import_key.startswith(NEWHIRE_KEY_PREFIX):
        return None                        # FS-16: one person, one notice

    return rec.pb_import_key, rec.pb_import_label or ''


class BizApprovalOutboxBankBatch(models.Model):
    _inherit = 'biz.approval.outbox'

    pb_bank_batch_key = fields.Char(index=True, readonly=True, copy=False)
    pb_bank_activity_id = fields.Many2one('mail.activity', readonly=True,
                                          copy=False, ondelete='set null')

    @api.model
    def _queue(self, kind, user, request=None, payload=None, dedupe=None):
        batch = None
        if kind in BATCH_TODO_KINDS + BATCH_ONCE_KINDS:
            try:
                batch = _batch_of(request)
            except Exception:              # noqa: BLE001 — never block a decision
                _logger.warning('pb_bank_ocr: batch lookup failed for %s',
                                request, exc_info=True)
        if not batch or not user:
            return super()._queue(kind, user, request=request,
                                  payload=payload, dedupe=dedupe)
        key, label = batch
        Req = self.env[BANK_MODEL].sudo()
        if kind in BATCH_ONCE_KINDS and Req._pb_batch_waiting(key):
            return self.browse()           # said once, when the last is approved
        row = super()._queue(
            kind, user, request=request,
            payload=dict(payload or {}, pb_bank_batch_label=label),
            dedupe='bankbatch-%s-%s-%s' % (kind, key, user.id))
        if row and not row.pb_bank_batch_key:
            row.sudo().write({'pb_bank_batch_key': key})
        return row

    def _deliver(self):
        self.ensure_one()
        key = self.pb_bank_batch_key
        if not key or not self.request_id:
            return super()._deliver()
        Req = self.env[BANK_MODEL].sudo()
        label = (self.payload or {}).get('pb_bank_batch_label') or ''
        request = self.request_id.sudo()
        partner = self.user_id.partner_id
        if self.kind in BATCH_ONCE_KINDS:
            request.message_post(
                body=_("All bank changes from \"%s\" that were waiting are "
                       "decided. Compliance › Bank shows each one.", label),
                subject=_("Bank changes decided: %s", label),
                partner_ids=partner.ids, message_type='notification',
                subtype_xmlid='mail.mt_note')
            return True
        waiting = Req._pb_batch_waiting(key)
        if not waiting:
            return True                    # decided before the job ran
        mine = self.sudo().search([
            ('pb_bank_batch_key', '=', key), ('user_id', '=', self.user_id.id),
            ('pb_bank_activity_id', '!=', False)]).pb_bank_activity_id.exists()
        if mine:
            # a reminder or an escalation for somebody who already has the
            # batch's to-do: bring it up to date, send nothing more
            Req._pb_batch_refresh(key)
            return True
        summary = Req._pb_batch_summary(label, waiting)
        body = Req._pb_batch_body(label, waiting)
        request.message_post(
            body=body, subject=summary, partner_ids=partner.ids,
            message_type='notification', subtype_xmlid='mail.mt_note')
        # the message above is the one email; the to-do itself sends none
        activity = request.with_context(
            mail_activity_quick_update=True).activity_schedule(
            act_type_xmlid='mail.mail_activity_data_todo',
            summary=summary, note=body, user_id=self.user_id.id,
            date_deadline=(request.due_at or fields.Datetime.now()).date())
        self.sudo().write({'pb_bank_activity_id': activity.id})
        return True


class PbBankChangeRequestBatchNotice(models.Model):
    _inherit = BANK_MODEL

    @api.model
    def _pb_batch_waiting(self, key):
        return self.sudo().search_count([('pb_import_key', '=', key),
                                         ('state', 'in', WAITING_STATES)])

    @api.model
    def _pb_batch_summary(self, label, waiting):
        return _("%(n)s bank changes waiting for your approval: %(what)s",
                 n=waiting, what=label)

    @api.model
    def _pb_batch_body(self, label, waiting):
        return Markup('%s<br/><a href="%s">%s</a>') % (
            _("%(n)s bank changes from \"%(what)s\" are waiting for you. Open "
              "Compliance › Bank and press \"Approve all in this file\". To "
              "send one back, open it in Approvals.", n=waiting, what=label),
            BANK_SCREEN_URL, _("Open Compliance › Bank"))

    @api.model
    def _pb_batch_refresh(self, key):
        """Bring the batch's to-dos up to date: the count still waiting, or
        marked done when nothing is waiting any more."""
        Outbox = self.env['biz.approval.outbox'].sudo()
        rows = Outbox.search([('pb_bank_batch_key', '=', key),
                              ('pb_bank_activity_id', '!=', False)])
        activities = rows.pb_bank_activity_id.exists()
        if not activities:
            return 0
        waiting = self._pb_batch_waiting(key)
        if not waiting:
            activities.sudo()._action_done(
                feedback=_("Every bank change in this batch is decided."))
            return 0
        label = (rows[:1].payload or {}).get('pb_bank_batch_label') or ''
        activities.sudo().with_context(mail_activity_quick_update=True).write({
            'summary': self._pb_batch_summary(label, waiting),
            'note': self._pb_batch_body(label, waiting),
        })
        return waiting

    def write(self, vals):
        if 'state' not in vals:
            return super().write(vals)
        keys = {r.pb_import_key for r in self.sudo()
                if r.pb_origin == 'import' and r.pb_import_key}
        res = super().write(vals)
        for key in keys:
            try:
                with self.env.cr.savepoint():
                    self._pb_batch_refresh(key)
            except Exception:              # noqa: BLE001 — never block a decision
                _logger.warning('pb_bank_ocr: could not refresh the to-dos of '
                                'batch %s', key, exc_info=True)
        return res
