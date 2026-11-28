# Part of Payobook. See LICENSE file for full copyright and licensing details.
"""Automatic holiday / rest-day marking of roster shifts — the screen twin
(WFSETUP P3, owner ruling R7; owner rule: whatever the backend does must be
doable on screen).

New roster rows are marked as they are made (`models/roster.py`). This method
re-checks the ones already there, from today on — after the rules are
confirmed, after a holiday is added or removed (wired in P4), and from the
quiet "Re-check holiday and rest-day shifts" link on step 4.
"""

from odoo import _, api, fields, models

from .roster import AUTO_KEY, _AUTO

KIND_KEYS = {'holiday': 'holiday', 'weekend': 'rest_day', 'weekday': 'normal'}


class WorkforceSetupDays(models.AbstractModel):
    _inherit = 'pb.workforce.setup'

    @api.model
    def remark_days(self, date_from=None):
        """Work out the day type again for every roster row of this company
        from today (or `date_from`, never earlier) that nobody set by hand and
        that is not calculated yet. Returns {checked, changed:{holiday,
        rest_day, normal}, summary}."""
        self._gate_edit()
        day = self._today()
        if date_from:
            asked = fields.Date.to_date(date_from)
            if asked and asked > day:
                day = asked
        Shift = self.env['hr.shift.planning']                 # as the caller (manager)
        changed = {'holiday': 0, 'rest_day': 0, 'normal': 0}
        if 'pb_day_kind' not in Shift._fields:
            return {'checked': 0, 'changed': changed, 'summary': _("Nothing to check.")}
        rows = Shift.search(self._future_rows_domain(day) + [('pb_day_kind_manual', '=', False)])
        kinds = Shift._pb_day_kinds([(r.employee_id.id, r.date) for r in rows])
        groups = {}
        for row in rows:
            want = kinds.get((row.employee_id.id, row.date), 'weekday')
            if row.pb_day_kind != want:
                groups.setdefault(want, []).append(row.id)
        ctx = dict(Shift._pb_auto_ctx(), tracking_disable=True, mail_notrack=True)
        for kind, ids in groups.items():
            Shift.browse(ids).with_context(**ctx).write({'pb_day_kind': kind})
            changed[KIND_KEYS[kind]] += len(ids)
        total = sum(changed.values())
        if not rows:
            summary = _("There are no shifts from today on to check.")
        elif not total:
            summary = _("Checked %s shifts. All of them were already right.", self._num(len(rows)))
        else:
            parts = []
            if changed['holiday']:
                parts.append(_("%s now public holiday", self._num(changed['holiday'])))
            if changed['rest_day']:
                parts.append(_("%s now rest day", self._num(changed['rest_day'])))
            if changed['normal']:
                parts.append(_("%s now normal day", self._num(changed['normal'])))
            summary = _("Checked %(n)s shifts: %(parts)s.", n=self._num(len(rows)), parts=', '.join(parts))
        return {'checked': len(rows), 'changed': changed, 'summary': summary}
