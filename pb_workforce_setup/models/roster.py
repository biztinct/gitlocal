# Part of Payobook. See LICENSE file for full copyright and licensing details.
"""Roster rows (`hr.shift.planning`): the ONE create override of this module.

1. Policy fill (WFSETUP P2). `pb_attendance_policy` copies the employee's
   late-rule set onto every new roster row (`policy.py` create hook) by
   reading `hr.employee.pb_attendance_policy_id` AS THE CALLER. That field is
   HR-officer-only (facts K24), so an attendance manager WITHOUT HR rights got
   an AccessError on every roster create — the working-week draft engine
   (`pb.shift.pattern.engine.apply`) included (ledger WS9). The same value is
   filled here, read with sudo, before that hook runs (this module loads after
   it, so this override is the outer one). No change when the caller passes
   `pb_policy_id` themselves.

2. Automatic day type (WFSETUP P3, owner ruling R7). When a row is made
   without `pb_day_kind`, it is worked out here, per BATCH (one holiday-map
   call, one membership search — the pattern engine makes thousands at once):
     * `holiday` when the shift's local start day is a public holiday or a
       company day off for that person (`pb.shift.pattern.engine._pb_holiday_map`,
       facts B.3 — not re-implemented);
     * `weekend` ("rest day") when the person's working week has that day OFF
       (`_pb_cycle_index` with the team offset and the member dates), or, for
       a person with no working week on that day, when their working calendar
       has no hours on that weekday;
     * `weekday` otherwise.
   A value given by a person (form, import, any write carrying the key
   without this module's context token) sets `pb_day_kind_manual` and is
   never worked out again. The token is a Python object, so no RPC caller
   can forge it.
"""

from odoo import api, fields, models

_AUTO = object()
AUTO_KEY = '_pb_day_kind_auto'


class ShiftPlanningPolicyFill(models.Model):
    _inherit = 'hr.shift.planning'

    pb_day_kind_manual = fields.Boolean(
        string='Day type set by hand', default=False,
        help='Set when someone chose normal day, rest day or public holiday for this shift '
             'themselves. Such a shift is never re-marked automatically.')

    @api.model
    def _pb_auto_ctx(self):
        return {AUTO_KEY: _AUTO}

    @api.model_create_multi
    def create(self, vals_list):
        if 'pb_policy_id' in self._fields:
            need = [v for v in vals_list if 'pb_policy_id' not in v and v.get('employee_id')]
            if need:
                emps = self.env['hr.employee'].sudo().browse({v['employee_id'] for v in need})
                policy = {e.id: e.pb_attendance_policy_id.id for e in emps}
                for v in need:
                    v['pb_policy_id'] = policy.get(v['employee_id']) or False
        if 'pb_day_kind' in self._fields:
            ours = self.env.context.get(AUTO_KEY) is _AUTO
            todo = []
            for v in vals_list:
                if v.get('pb_day_kind_manual'):
                    continue                                    # chosen by hand, kept
                if 'pb_day_kind_manual' in v or 'pb_day_kind' not in v:
                    todo.append(v)                              # new, or copied from an automatic row
                elif not ours:
                    v['pb_day_kind_manual'] = True              # a person chose it
            todo = [v for v in todo if v.get('employee_id') and v.get('date')]
            if todo:
                kinds = self._pb_day_kinds([(v['employee_id'], fields.Date.to_date(v['date'])) for v in todo])
                for v in todo:
                    v['pb_day_kind'] = kinds[(v['employee_id'], fields.Date.to_date(v['date']))]
                    v['pb_day_kind_manual'] = False
        return super().create(vals_list)

    def write(self, vals):
        if ('pb_day_kind' in vals and 'pb_day_kind_manual' not in vals
                and 'pb_day_kind_manual' in self._fields
                and self.env.context.get(AUTO_KEY) is not _AUTO):
            vals = dict(vals, pb_day_kind_manual=True)
        # A shift moved to another day or person (WFSETUP P4 carry-over, P3
        # report §2 item 14): an automatic day type is worked out again in the
        # same write, for rows nobody set by hand and that are not calculated
        # or turned into attendance yet. An explicit day type wins.
        moved = self.browse()
        if (('date' in vals or 'employee_id' in vals) and 'pb_day_kind' not in vals
                and 'pb_day_kind_manual' in self._fields):
            moved = self.filtered(lambda r: not r.pb_day_kind_manual
                                  and not r.pb_attendance_id and not r.pb_calculation_status)
        res = super().write(vals)
        if moved:
            moved._pb_remark_moved()
        return res

    def _pb_remark_moved(self):
        """Day type of moved automatic rows, worked out again (one batch)."""
        kinds = self._pb_day_kinds([(r.employee_id.id, r.date) for r in self])
        groups = {}
        for row in self:
            want = kinds.get((row.employee_id.id, row.date), 'weekday')
            if row.pb_day_kind != want:
                groups.setdefault(want, []).append(row.id)
        ctx = dict(self._pb_auto_ctx(), tracking_disable=True, mail_notrack=True)
        for kind, ids in groups.items():
            self.browse(ids).with_context(**ctx).write({'pb_day_kind': kind})

    # ------------------------------------------------------------ the day type
    @api.model
    def _pb_day_kinds(self, pairs):
        """{(employee_id, date): 'holiday' | 'weekend' | 'weekday'} for many
        (employee, local start day) pairs at once. Pure read (sudo: callers
        are the ORM create of a permitted writer or a gated facade)."""
        out = {}
        pairs = [(int(e), d) for e, d in pairs if e and d]
        if not pairs:
            return out
        Employee = self.env['hr.employee'].sudo().with_context(active_test=False)
        emps = Employee.browse(sorted({e for e, _d in pairs}))
        first = min(d for _e, d in pairs)
        last = max(d for _e, d in pairs)
        holidays = self.env['pb.shift.pattern.engine'].sudo()._pb_holiday_map(emps, first, last)
        members = self.env['pb.shift.pattern.member'].sudo().search([
            ('employee_id', 'in', emps.ids),
            ('pattern_id.active', '=', True),
            '|', ('date_from', '=', False), ('date_from', '<=', last),
            '|', ('date_to', '=', False), ('date_to', '>=', first)])
        by_emp = {}
        for m in members.sorted(lambda m: (m.pattern_id.name or '', m.id)):
            by_emp.setdefault(m.employee_id.id, []).append(m)
        emp_by_id = {e.id: e for e in emps}
        slot_maps, calendars = {}, {}
        for emp_id, day in pairs:
            key = (emp_id, day)
            if key in out:
                continue
            if (emp_id, day.isoformat()) in holidays:
                out[key] = 'holiday'
                continue
            member = next((m for m in by_emp.get(emp_id, ()) if m._pb_covers(day)), None)
            if member:
                pattern = member.pattern_id
                if pattern.id not in slot_maps:
                    slot_maps[pattern.id] = pattern._pb_slot_map()
                works = pattern._pb_cycle_index(day, member.team_id.offset_days) in slot_maps[pattern.id]
            else:
                emp = emp_by_id.get(emp_id)
                cal = emp and (emp.resource_calendar_id or emp.company_id.resource_calendar_id)
                works = self._pb_calendar_works(cal, day, calendars) if cal else True
            out[key] = 'weekday' if works else 'weekend'
        return out

    @api.model
    def _pb_calendar_works(self, calendar, day, cache):
        """Does this working calendar have hours on `day`'s weekday (week A/B
        honoured)? A calendar without any hours counts as every day worked."""
        if calendar.id not in cache:
            keys = {(a.week_type or False, int(a.dayofweek))
                    for a in calendar.attendance_ids if not a.display_type}
            cache[calendar.id] = (bool(calendar.two_weeks_calendar), keys)
        two_weeks, keys = cache[calendar.id]
        if not keys:
            return True
        if two_weeks:
            week = str(self.env['resource.calendar.attendance'].get_week_type(day))
            return (week, day.weekday()) in keys
        return any(d == day.weekday() for _w, d in keys)
