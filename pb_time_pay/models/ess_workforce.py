# Part of Payobook. See LICENSE file for full copyright and licensing details.
"""My Overtime on My Payobook says which hours became time off.

Extends `get_my_overtime` (contract C-4: the method name and its keys stay
exactly as they are; this ADDS a ``time_off`` key per row and a
``total_time_off`` total). Read-only, as the page has always been.
"""

from odoo import api, models


class PbEssWorkforceTimePay(models.AbstractModel):
    _inherit = 'pb.ess.workforce'

    @api.model
    def get_my_overtime(self):
        data = super().get_my_overtime()
        rows = data.get('rows') or []
        ids = [r['id'] for r in rows if r.get('id')]
        if not ids:
            data.setdefault('total_time_off', 0.0)
            return data
        reqs = {r.id: r for r in self.env['hr.overtime.request'].sudo().browse(
            ids).exists()}
        total = 0.0
        for row in rows:
            rec = reqs.get(row.get('id'))
            off = bool(rec) and rec.pb_comp_choice == 'time_off'
            row['time_off'] = off
            if off and rec.state == 'approved':
                total += rec._pb_toil_hours()
        data['total_time_off'] = round(total, 2)
        return data
