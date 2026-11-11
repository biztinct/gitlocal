# -*- coding: utf-8 -*-
"""UPDATES P2d — what the history screens say.

1. "Could not be made" (the P2c report's "needs a decision" item 3). When an
   approved change could not be written, the approval engine keeps the
   request "approved" with its reason (`block_reason`) and the change stays
   "Waiting for approval" — on the Updates home and on the Records screen's
   History alike. Both now say "Could not be made" and give the reason in
   plain words. DISPLAY ONLY: the approval engine, the change's own state and
   every button stay exactly as they were ("See the request" still opens the
   request, where it can be tried again).

2. A named update of one-off pay items is listed on the Records screen's
   History too (its approval proposal is a records change). It reads its own
   words there, and its Undo takes back what no pay run has taken yet.
"""
from odoo import _, api, models


class PbRecordsApplyHistory(models.Model):
    _inherit = 'pb.records.apply'

    def _blocked_reason(self):
        """The engine's reason when this change was approved but could not be
        written; '' otherwise."""
        self.ensure_one()
        if self.applied or self.state != 'pending':
            return ''
        request = self.sudo().approval_request_id
        if request and request.state == 'approved' and (request.block_reason or '').strip():
            return request.block_reason.strip()
        return ''


class PbRecordsDeskHistory(models.AbstractModel):
    _inherit = 'pb.records.desk'

    @api.model
    def get_history(self, limit=20):
        answer = super().get_history(limit)
        rows = answer.get('applies') or []
        if not rows:
            return answer
        Apply = self.env['pb.records.apply'].sudo()
        recs = {r.id: r for r in Apply.browse([h['id'] for h in rows]).exists()}
        Desk = self.env['pb.updates.desk']
        for h in rows:
            rec = recs.get(h['id'])
            if not rec:
                continue
            reason = rec._blocked_reason()
            if reason:
                h.update(state='blocked', state_label=_("Could not be made"),
                         block_note=_("Approved, but it could not be made: %s") % reason,
                         with_whom='')
            if rec.updates_oneoff:
                state, label, note = Desk._oneoff_state(rec.oneoff_ids)
                h['oneoff'] = True
                if not reason:
                    h['block_note'] = ' · '.join(
                        x for x in (rec._headline(), label, note) if x)
                if rec.applied and state in ('cancelled', 'cleared'):
                    # Nothing left that an Undo could take back.
                    h['undone'] = True
        return answer

    @api.model
    def undo_apply(self, apply_id):
        source = self.env['pb.records.apply'].sudo().browse(int(apply_id or 0)).exists()
        if source and source.updates_oneoff and source.applied:
            # A one-off is not a record value to put back: "undo" takes back
            # what is still waiting for a pay run — with the same right to
            # change employee records that Updates' own Cancel asks for.
            Updates = self.env['pb.updates.desk']
            if not Updates._can_write():
                return {'ok': False, 'msg': _(
                    "Cancelling an update needs permission to change employee "
                    "records. Ask an administrator for the HR or Payroll Officer "
                    "role.")}
            return Updates._oneoff_cancel_rows(source.oneoff_ids, source)
        return super().undo_apply(apply_id)
