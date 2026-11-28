# Part of Payobook. See LICENSE file for full copyright and licensing details.
"""Make N weeks of draft shifts from patterns — plan first, then apply.

The engine is `copy_week_checked` (pb_schedule/models/schedule_grid.py) in
shape, on purpose:

  * the caches are built ONCE per run (`_pb_shift_windows`, `_pb_leave_map`,
    `_pb_ceilings` per month) and the SAME worker `_pb_check` judges every
    shift, so a pattern refuses exactly what Copy Week refuses — an overlap,
    approved leave, the young-worker night ban, the overtime ceiling — and a
    pending leave request (info) does not stop a shift;
  * `block` and `warn` are skipped and reported, never raised: "why did
    nothing happen" is the question a silent refusal leaves;
  * each shift planned in this pass is appended to the windows, so the next
    row sees it.

Added on top of Copy Week:

  * PUBLIC HOLIDAYS. Company closures in `resource.calendar.leaves` (no
    resource, time type "leave") — the rows `pb.holidays` writes — are skipped
    and reported unless the pattern says "Work on public holidays".
  * NO DUPLICATES. The pattern's own shifts in the range are matched first:
      - an UNTOUCHED draft that is still what the pattern wants is kept;
      - an untouched draft the pattern no longer wants (changed slot, changed
        team, person left the pattern, shift hours changed) is removed — and
        its window is taken out of the overlap cache before anything is
        judged, so its replacement is not refused by its own ghost;
      - a draft changed by hand, and every published/completed shift, is left
        alone and the day is not filled again.
  * PAST DAYS are never filled (today counts as not past).

`plan()` writes nothing — the preview is the plan. `apply()` re-plans (data
may have moved since the preview), removes, then creates in one batch inside
a savepoint; should the batch be refused by a rule the checks did not foresee,
it falls back to one savepoint per shift and reports each refusal.
"""

import logging
from collections import OrderedDict
from datetime import datetime, time, timedelta

import pytz

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError

from .shift_planning import pattern_signature

_logger = logging.getLogger(__name__)

MAX_WEEKS = 12
REPORT_CAP = 300       # skip rows returned to the screen; the counts are exact
_LIVE_STATES = ('draft', 'published', 'completed')


class ShiftPatternEngine(models.AbstractModel):
    _name = 'pb.shift.pattern.engine'
    _description = 'Rotating shift pattern engine'

    # ------------------------------------------------------------ gates
    @api.model
    def _pb_can_make(self):
        u = self.env.user
        return bool(u.has_group('hr_attendance.group_hr_attendance_manager')
                    or u.has_group('base.group_system'))

    @api.model
    def _require_maker(self):
        if not self._pb_can_make():
            raise AccessError(_(
                "Making shifts from a pattern is for attendance managers."))

    # ------------------------------------------------------------ range
    @api.model
    def _pb_range(self, start, weeks):
        """(first, last) dates. `start` snaps back to its Monday."""
        day = fields.Date.to_date(start) if start else fields.Date.context_today(self)
        if not day:
            raise UserError(_("Choose the first week to fill."))
        day = day - timedelta(days=day.weekday())
        try:
            weeks = int(weeks or 0)
        except (TypeError, ValueError):
            weeks = 0
        if not 1 <= weeks <= MAX_WEEKS:
            raise UserError(_("Choose 1 to %s weeks.", MAX_WEEKS))
        return day, day + timedelta(days=7 * weeks - 1)

    # ------------------------------------------------------------ holidays
    @api.model
    def _pb_holiday_map(self, employees, first, last):
        """{(employee_id, iso day): holiday name} — company closures.

        The holiday board's own reading (`pb.holidays._column`): rows with no
        resource, time type "leave", of the person's company. A closure tied
        to a working schedule counts for the people on that schedule (or on
        the company's), one with no schedule for everybody in the company.
        Days are the person's LOCAL days (the shift's own clock).
        """
        out = {}
        if not employees:
            return out
        Grid = self.env['hr.shift.planning.grid']
        lo = datetime.combine(first - timedelta(days=1), time.min)
        hi = datetime.combine(last + timedelta(days=1), time.max)
        rows = self.env['resource.calendar.leaves'].sudo().search([
            ('resource_id', '=', False),
            ('company_id', 'in', employees.company_id.ids),
            ('time_type', '=', 'leave'),
            ('date_from', '<=', hi),
            ('date_to', '>=', lo),
        ])
        if not rows:
            return out
        for emp in employees:
            tz = pytz.timezone(Grid._pb_shift_tzname(emp))
            cals = {emp.resource_calendar_id.id, emp.company_id.resource_calendar_id.id}
            for row in rows:
                if row.company_id != emp.company_id:
                    continue
                if row.calendar_id and row.calendar_id.id not in cals:
                    continue
                d_from = pytz.UTC.localize(row.date_from).astimezone(tz).date()
                # an end at 23:59:59 local is that day; an end exactly at
                # midnight belongs to the day before
                end_local = pytz.UTC.localize(row.date_to).astimezone(tz)
                d_to = end_local.date()
                if end_local.time() == time.min and d_to > d_from:
                    d_to -= timedelta(days=1)
                cur = max(d_from, first)
                while cur <= min(d_to, last):
                    out.setdefault((emp.id, cur.isoformat()), row.name or _('Public holiday'))
                    cur += timedelta(days=1)
        return out

    # ------------------------------------------------------------ the plan
    @api.model
    def _pb_wanted(self, pattern, first, last, today):
        """{(employee_id, iso): (employee, template, day)} the pattern asks for.

        Plus the count of cycle days that are off, and of days skipped
        because they are in the past.
        """
        slots = pattern._pb_slot_map()
        wanted = OrderedDict()
        off = past = 0
        members = pattern.member_ids.filtered(
            lambda m: m.employee_id.active
            and (not m.date_from or m.date_from <= last)
            and (not m.date_to or m.date_to >= first))
        for member in members.sorted(lambda m: (m.employee_id.name or '', m.id)):
            emp = member.employee_id
            cur = max(first, member.date_from or first)
            stop = min(last, member.date_to or last)
            while cur <= stop:
                template = slots.get(pattern._pb_cycle_index(cur, member.team_id.offset_days))
                if not template:
                    off += 1
                elif cur < today:
                    past += 1
                else:
                    wanted[(emp.id, cur.isoformat())] = (emp, template, cur)
                cur += timedelta(days=1)
        return wanted, off, past

    @api.model
    def plan(self, patterns, first, last):
        """Everything `apply` would do, as data. Writes nothing.

        Several patterns are planned in ONE pass so a person on two patterns
        is checked against both (the windows cache is shared).
        """
        Grid = self.env['hr.shift.planning.grid']
        Shift = self.env['hr.shift.planning']
        today = fields.Date.context_today(self)

        per_pattern = OrderedDict()
        all_emp_ids = set()
        for pattern in patterns:
            # sudo for the READ of people and slots only (an attendance
            # manager need not hold HR rights on employees); every shift is
            # searched, judged and created as the caller
            wanted, off, past = self._pb_wanted(pattern.sudo(), first, last, today)
            per_pattern[pattern.id] = {'pattern': pattern, 'wanted': wanted,
                                       'off': off, 'past': past}
            all_emp_ids.update(k[0] for k in wanted)

        # the patterns' own shifts in the range, whoever they belong to now
        own = Shift.search([
            ('pb_pattern_id', 'in', patterns.ids),
            ('date', '>=', first), ('date', '<=', last),
            ('state', 'in', _LIVE_STATES),
        ], order='date, id')

        remove = Shift.browse()
        kept_same = kept_published = 0
        kept_edited = []
        claimed = set()                    # (pattern, emp, iso) already there
        for s in own:
            slot = per_pattern.get(s.pb_pattern_id.id)
            key = (s.employee_id.id, s.date.isoformat())
            want = slot['wanted'].get(key) if slot else None
            ckey = (s.pb_pattern_id.id,) + key
            if s.state != 'draft':
                if want and ckey not in claimed:
                    kept_published += 1
                    claimed.add(ckey)
                continue
            if not s._pb_pattern_untouched():
                if want and ckey not in claimed:
                    claimed.add(ckey)
                    kept_edited.append(self._pb_row(s.employee_id, s.date, s.shift_template_id,
                                                    [_("Changed by hand, so it is left as it is.")],
                                                    'edited', 'info', slot['pattern']))
                continue
            if want and ckey not in claimed and want[1] == s.shift_template_id:
                tz = Grid._pb_shift_tzname(s.employee_id)
                start, end = Grid._pb_shift_window(s.shift_template_id, s.date, tz)
                if (start, end) == (s.start_datetime, s.end_datetime):
                    kept_same += 1
                    claimed.add(ckey)
                    continue
            remove |= s

        emp_ids = sorted(all_emp_ids)
        employees = self.env['hr.employee'].browse(emp_ids)
        windows = Grid._pb_shift_windows(emp_ids, first, last)
        gone = set(remove.ids)
        if gone:
            windows = {e: [w for w in ws if w[2] not in gone] for e, ws in windows.items()}
        leaves = Grid._pb_leave_map(emp_ids, first, last)
        ceilings_by_month = {}
        holidays = self._pb_holiday_map(employees, first, last)

        creates, skipped = [], []
        counts = {}
        for pid, slot in per_pattern.items():
            pattern = slot['pattern']
            for (emp_id, iso), (emp, template, day) in slot['wanted'].items():
                if (pid, emp_id, iso) in claimed:
                    continue
                if not pattern.work_on_holidays and (emp_id, iso) in holidays:
                    skipped.append(self._pb_row(
                        emp, day, template,
                        [_("%s is a public holiday.", holidays[(emp_id, iso)])],
                        'holiday', 'warn', pattern))
                    counts['holiday'] = counts.get('holiday', 0) + 1
                    continue
                month = (day.year, day.month)
                if month not in ceilings_by_month:
                    month_end = (day.replace(day=28) + timedelta(days=4))
                    month_end -= timedelta(days=month_end.day)
                    ceilings_by_month[month] = Grid._pb_ceilings(emp_ids, month_end)
                warns = Grid._pb_check(emp, day, template, windows, leaves,
                                       ceilings_by_month[month])
                hard = [w for w in warns if w['severity'] in ('block', 'warn')]
                if hard:
                    code = hard[0]['code']
                    skipped.append(self._pb_row(
                        emp, day, template, [w['text'] for w in hard], code,
                        'block' if any(w['severity'] == 'block' for w in hard) else 'warn',
                        pattern))
                    counts[code] = counts.get(code, 0) + 1
                    continue
                tz = Grid._pb_shift_tzname(emp)
                start, end = Grid._pb_shift_window(template, day, tz)
                creates.append({
                    'employee_id': emp.id,
                    'shift_template_id': template.id,
                    'date': day,
                    'start_datetime': start,
                    'end_datetime': end,
                    'state': 'draft',
                    'company_id': emp.company_id.id,
                    'pb_pattern_id': pattern.id,
                    'pb_pattern_sig': pattern_signature(emp.id, template.id, day, start, end),
                })
                windows.setdefault(emp.id, []).append((start, end, 0))

        return {
            'first': first, 'last': last,
            'creates': creates,
            'remove': remove,
            'skipped': skipped,
            'counts': counts,
            'kept_same': kept_same,
            'kept_published': kept_published,
            'kept_edited': kept_edited,
            'off': sum(p['off'] for p in per_pattern.values()),
            'past': sum(p['past'] for p in per_pattern.values()),
            'per_pattern': {pid: len(p['wanted']) for pid, p in per_pattern.items()},
        }

    @api.model
    def _pb_row(self, employee, day, template, reasons, code, severity, pattern):
        return {
            'employee_id': employee.id,
            'employee_name': employee.name or '',
            'date': day.isoformat(),
            'template': template.name or template.code or '',
            'pattern': pattern.name or '',
            'reasons': reasons,
            'code': code,
            'severity': severity,
        }

    # ------------------------------------------------------------ apply
    @api.model
    def apply(self, patterns, first, last):
        """Make the drafts. Returns the same report a preview shows, done."""
        self._require_maker()
        plan = self.plan(patterns, first, last)
        removed = len(plan['remove'])
        if plan['remove']:
            plan['remove'].unlink()

        Shift = self.env['hr.shift.planning'].with_context(
            tracking_disable=True, mail_create_nolog=True, mail_notrack=True)
        created = 0
        failed = []
        vals_list = plan['creates']
        if vals_list:
            try:
                with self.env.cr.savepoint():
                    Shift.create(vals_list)
                created = len(vals_list)
            except (UserError, ValidationError) as batch_error:
                _logger.info('pattern batch refused, one by one: %s', batch_error)
                for vals in vals_list:
                    try:
                        with self.env.cr.savepoint():
                            Shift.create(vals)
                        created += 1
                    except (UserError, ValidationError) as e:
                        emp = self.env['hr.employee'].browse(vals['employee_id'])
                        tmpl = self.env['hr.shift.template'].browse(vals['shift_template_id'])
                        pattern = self.env['pb.shift.pattern'].browse(vals['pb_pattern_id'])
                        failed.append(self._pb_row(emp, vals['date'], tmpl,
                                                   [str(e.args[0] if e.args else e)],
                                                   'refused', 'block', pattern))
        if failed:
            plan['skipped'].extend(failed)
            plan['counts']['refused'] = len(failed)

        now = fields.Datetime.now()
        for pattern in patterns:
            to = max(pattern.last_made_to, last) if pattern.last_made_to else last
            pattern.sudo().write({'last_made_on': now, 'last_made_by': self.env.uid,
                                  'last_made_to': to})
        report = self._pb_report(plan)
        report.update({'created': created, 'removed': removed, 'done': True})
        return report

    @api.model
    def _pb_report(self, plan):
        """The plan as the screen reads it (JSON-safe)."""
        skipped = plan['skipped']
        return {
            'done': False,
            'first': plan['first'].isoformat(),
            'last': plan['last'].isoformat(),
            'created': len(plan['creates']),
            'removed': len(plan['remove']),
            'skipped_total': len(skipped),
            'skipped': skipped[:REPORT_CAP],
            'counts': plan['counts'],
            'kept_same': plan['kept_same'],
            'kept_published': plan['kept_published'],
            'kept_edited_total': len(plan['kept_edited']),
            'kept_edited': plan['kept_edited'][:REPORT_CAP],
            'off': plan['off'],
            'past': plan['past'],
            'people': len({c['employee_id'] for c in plan['creates']}),
        }

    # ------------------------------------------------------------ clean up
    @api.model
    def clear_drafts(self, patterns):
        """Remove the untouched drafts these patterns made, from today on."""
        self._require_maker()
        today = fields.Date.context_today(self)
        drafts = self.env['hr.shift.planning'].search([
            ('pb_pattern_id', 'in', patterns.ids),
            ('state', '=', 'draft'),
            ('date', '>=', today),
        ])
        untouched = drafts.filtered(lambda s: s._pb_pattern_untouched())
        n = len(untouched)
        untouched.unlink()
        return {'removed': n, 'kept_edited': len(drafts) - n}
