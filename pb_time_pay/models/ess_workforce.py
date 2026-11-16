# Part of Payobook. See LICENSE file for full copyright and licensing details.
"""My Overtime on My Payobook says which hours became time off — and, since
WDGAP S5-F (owner ruling TP3, 2026-11-16), the person's own DECIDED late and
early minutes.

Extends `get_my_overtime` (contract C-4: the method name and its keys stay
exactly as they are; this ADDS a ``time_off`` key per row, a
``total_time_off`` total and a ``late`` summary for the link card). Read-only,
as the page has always been.

`get_my_late_minutes` is the facade of the page `/my/work/late`: the
signed-in person's own `pb.time.late` rows (resolved from the session through
`_require_own_employee`, never from a parameter), grouped by month. Only
confirmed minutes count; an excused row is shown as "Excused" and never as a
charge. Minutes nobody has decided are never stored, so they are never shown.
The manager's note is not shown (it is written for the team, not the person).
"""

from dateutil.relativedelta import relativedelta

from odoo import _, api, fields, models
from odoo.tools.misc import format_date

#: How far back the page reads (months, this one included).
LATE_MONTHS = 12
#: Most rows the page lists.
LATE_CAP = 400


class PbEssWorkforceTimePay(models.AbstractModel):
    _inherit = 'pb.ess.workforce'

    @api.model
    def get_my_overtime(self):
        data = super().get_my_overtime()
        data['late'] = self._pb_my_late_summary()
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

    # ------------------------------------------------------------ late minutes
    @api.model
    def _pb_my_late_rows(self, emp):
        today = fields.Date.context_today(self)
        start = today.replace(day=1) - relativedelta(months=LATE_MONTHS - 1)
        return self.env['pb.time.late'].sudo().search(
            [('employee_id', '=', emp.id), ('date', '>=', start),
             ('state', 'in', ('confirmed', 'excused'))],
            order='date desc, kind, id', limit=LATE_CAP)

    @api.model
    def _pb_my_late_summary(self):
        """For the link card on My Overtime: shown only when the person has
        decided minutes (nothing changes for anybody else)."""
        emp = self._own_employee()
        if not emp:
            return {'count': 0, 'month_minutes': 0}
        rows = self._pb_my_late_rows(emp)
        first = fields.Date.context_today(self).replace(day=1)
        month = sum(r.minutes for r in rows if r.state == 'confirmed' and r.date >= first)
        return {'count': len(rows), 'month_minutes': month}

    @api.model
    def get_my_late_minutes(self):
        """The page: one block per month, newest first.

        ``{'months': [{'key', 'label', 'counted', 'rows': [{'date', 'kind',
        'kind_label', 'minutes', 'state', 'state_label'}]}], 'total_counted'}``
        """
        emp = self._require_own_employee()
        kinds = {'late': _('Late arrival'), 'early': _('Early leave')}
        states = {'confirmed': _('Counted'), 'excused': _('Excused')}
        months = []
        by_key = {}
        total = 0
        for row in self._pb_my_late_rows(emp):
            key = row.date.strftime('%Y-%m')
            block = by_key.get(key)
            if block is None:
                block = {'key': key,
                         'label': format_date(self.env, row.date, date_format='MMMM y'),
                         'counted': 0, 'rows': []}
                by_key[key] = block
                months.append(block)
            counted = row.state == 'confirmed'
            if counted:
                block['counted'] += row.minutes
                total += row.minutes
            block['rows'].append({
                'date': format_date(self.env, row.date, date_format='EEE d MMM'),
                'kind': row.kind,
                'kind_label': kinds.get(row.kind, ''),
                'minutes': row.minutes,
                'state': row.state,
                'state_label': states.get(row.state, ''),
            })
        return {'months': months, 'total_counted': total}
