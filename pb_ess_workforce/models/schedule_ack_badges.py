# Part of Payobook. See LICENSE file for full copyright and licensing details.
"""The manager's half of the read receipt: an ack badge per person on the roster.

WHEN-I-WORK'S PATTERN, AND WHY IT IS ONE NUMBER PER PERSON
----------------------------------------------------------
A scheduling manager does not want to know which of Thursday's four shifts an
employee confirmed. They want to know whether the roster LANDED — so the badge
is per PERSON for the visible window: a green check when everything published to
them is confirmed, a muted "n/m" when it is not, and nothing at all when they
have no published shift in the window (an empty badge on an empty row is noise,
and W64's rule is that a cell renders outcomes, not configuration).

STRICTLY ADDITIVE
-----------------
`get_schedule_data` is `pb_schedule`'s read model, and this override does one
thing to it: adds an `ack` key to each employee row and an `ack` block to
`counts`. Every existing key keeps its shape and its meaning, so the cockpit
renders identically on a database where this module is absent — the templates
guard on the key's presence, which is the same soft-hook shape the rest of the
program uses.

DRAFT SHIFTS ARE NOT COUNTED
----------------------------
An unpublished shift is not a promise anybody has been asked to confirm, so
counting it would make every freshly-drafted week look like a delivery failure.
Only `published` counts; `completed` is excluded too, because a shift that has
already been worked is past the point where an acknowledgment means anything and
leaving it in the denominator would make history permanently red.
"""

from datetime import timedelta

from odoo import api, fields, models


class ShiftPlanningGridAck(models.TransientModel):
    _inherit = 'hr.shift.planning.grid'

    @api.model
    def get_schedule_data(self, week_start_str, department_id=False,
                          num_days=7, search=''):
        data = super().get_schedule_data(
            week_start_str, department_id=department_id,
            num_days=num_days, search=search)
        try:
            self._ess_decorate_ack(data, week_start_str, num_days)
        except Exception:                                     # pragma: no cover
            # A badge is an instrument, not the roster. If it cannot be
            # computed the manager still gets their week — and the absent key
            # is exactly what the template already guards for.
            data.setdefault('ack', {'shown': False})
        return data

    @api.model
    def _ess_decorate_ack(self, data, week_start_str, num_days):
        week_start = fields.Date.from_string(week_start_str)
        num_days = 14 if int(num_days or 7) == 14 else 7
        week_end = week_start + timedelta(days=num_days - 1)
        emp_ids = [r['id'] for r in data.get('employees', [])]
        if not emp_ids:
            data['ack'] = {'shown': False, 'acked': 0, 'total': 0, 'people': 0,
                           'people_done': 0}
            return

        # One grouped read, not one per row: the roster is capped at 200 people
        # and this must not become 200 queries a render.
        groups = self.env['hr.shift.planning'].sudo().read_group(
            [('employee_id', 'in', emp_ids),
             ('date', '>=', week_start), ('date', '<=', week_end),
             ('state', '=', 'published')],
            ['id:count'], ['employee_id', 'ack_state'], lazy=False)
        by_emp = {}
        for g in groups:
            emp = g.get('employee_id')
            if not emp:
                continue
            slot = by_emp.setdefault(emp[0], {'acked': 0, 'total': 0})
            n = g.get('__count') or g.get('id_count') or 0
            slot['total'] += n
            if g.get('ack_state') == 'acked':
                slot['acked'] += n

        total = acked = people = people_done = 0
        for row in data['employees']:
            slot = by_emp.get(row['id'])
            if not slot or not slot['total']:
                row['ack'] = None       # nothing published: no badge (W64)
                continue
            done = slot['acked'] >= slot['total']
            row['ack'] = {'acked': slot['acked'], 'total': slot['total'],
                          'all': done}
            total += slot['total']
            acked += slot['acked']
            people += 1
            people_done += 1 if done else 0

        data['ack'] = {
            'shown': bool(people),
            'acked': acked, 'total': total,
            'people': people, 'people_done': people_done,
        }
