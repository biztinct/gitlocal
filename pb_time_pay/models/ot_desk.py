# Part of Payobook. See LICENSE file for full copyright and licensing details.
"""The Overtime desk: "Approve as time off" beside "Approve" (owner ruling L3).

Each card says whether the overtime will be paid or given as time off, and the
desk's own `act` learns one more verb, ``approve_time_off``: set the choice,
then approve — row by row, as the real user, inside the desk's own per-row
savepoint, so a refusal of either half leaves that row exactly as it was.
"""

from odoo import _, api, models


class PbOtDeskTimePay(models.AbstractModel):
    _inherit = 'pb.ot.desk'

    def _queue_cards(self, reqs):
        cards = super()._queue_cards(reqs)
        if not cards:
            return cards
        by_id = {r.id: r for r in reqs.sudo()}
        for card in cards:
            rec = by_id.get(card.get('id'))
            if rec is None:
                continue
            card['time_off'] = rec.pb_comp_choice == 'time_off'
            card['time_off_label'] = rec.pb_comp_label
            card['from_punches'] = bool(rec.pb_from_punches)
        return cards

    @api.model
    def act(self, request_ids, action, note=False):
        if action != 'approve_time_off':
            return super().act(request_ids, action, note=note)
        self._require_manager()
        results = []
        Req = self.env['hr.overtime.request']
        for rid in [int(x) for x in (request_ids or [])]:
            rec = Req.browse(rid).exists()
            if not rec:
                results.append({'id': rid, 'ok': False,
                                'error': _("No longer exists.")})
                continue
            name = rec.sudo().employee_id.name
            try:
                with self.env.cr.savepoint():
                    rec._pb_set_choice('time_off')
                    rec.action_approve()
                results.append({'id': rid, 'ok': True, 'name': name})
            except Exception as exc:    # noqa: BLE001 — per-row chip
                results.append({'id': rid, 'ok': False, 'name': name,
                                'error': self._msg(exc)})
        return {'results': results}
