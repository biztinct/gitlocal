# Part of Payobook. See LICENSE file for full copyright and licensing details.
"""`pb.workforce.setup` — the facade of the guided Workforce setup screen.

Cockpit pattern (clone of `pb.workforce.workspace` / `pb.shift.patterns`):
one AbstractModel, every method gated on the server. Attendance officers READ
(`_gate_read`), attendance managers WRITE (`_gate_edit`); the JS hides
controls as a courtesy only.

SCOPE: every domain is the CURRENT company (`self.env.company`) only. Shifts
and roster rows carry no company record rule (facts K2), so the domain is the
only fence. Shared shifts (`company_id = False`) are listed and usable, but
read-only here.

Reads of people and of pattern members go through sudo BEHIND the gate
(C18.73): an attendance officer need not hold HR rights to see who is on a
working week. Every WRITE goes through the ORM as the caller, so the models'
own ACLs and validations still apply (ledger rule 5: no parallel write path).

Screen words: a "working week" is a `pb.shift.pattern`; a "shift" is an
`hr.shift.template`; an off day is a cycle day without a template.
"""

import re
from datetime import timedelta

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tools.misc import format_date

# ONE colour table (handover §2). The stored value is the Schedule's palette
# index (`pb_schedule.scss` `$pbsc-accent`); the screen speaks in names. The JS
# receives this table in the `load()` payload and never keeps its own copy.
#   1 = --pbim-primary (#5A4BB0)              -> indigo
#   6 = mix(green 55 %, blue)  (~#2A7195)     -> teal (closest of the eleven)
#   4 = --pbim-amber (#D97706)                -> amber
#   3 = --pbim-cyan (#2563EB)                 -> blue
#   5 = --pbim-rose (#DC2668)                 -> rose
#   2 = --pbim-green (#2E7D4F)                -> green
COLOURS = (('indigo', 1), ('teal', 6), ('amber', 4), ('blue', 3), ('rose', 5), ('green', 2))
COLOUR_INDEX = dict(COLOURS)
COLOUR_NAME = {index: name for name, index in COLOURS}
DEFAULT_COLOUR = 'indigo'

MAX_WEEKS = 8                       # pb.shift.pattern MAX_CYCLE_DAYS = 56
STEP_KEYS = ('shifts', 'weeks', 'people', 'rules', 'holidays', 'clocks', 'live')
_TIME = re.compile(r'^\s*(\d{1,2}):(\d{2})\s*$')


class WorkforceSetup(models.AbstractModel):
    _name = 'pb.workforce.setup'
    _description = 'Workforce setup'

    # ------------------------------------------------------------ gates
    @api.model
    def _can_read(self):
        u = self.env.user
        return bool(u.has_group('hr_attendance.group_hr_attendance_officer')
                    or u.has_group('base.group_system'))

    @api.model
    def _can_edit(self):
        u = self.env.user
        return bool(u.has_group('hr_attendance.group_hr_attendance_manager')
                    or u.has_group('base.group_system'))

    @api.model
    def _gate_read(self):
        if not self._can_read():
            raise AccessError(_("Attendance access is required."))

    @api.model
    def _gate_edit(self):
        self._gate_read()
        if not self._can_edit():
            raise AccessError(_("Only an attendance manager can change the workforce setup."))

    # ------------------------------------------------------------ helpers
    @api.model
    def _today(self):
        return fields.Date.context_today(self)

    @api.model
    def _monday(self, day=None):
        day = day or self._today()
        return day - timedelta(days=day.weekday())

    @api.model
    def _int(self, value, default=0):
        try:
            return int(value)
        except (TypeError, ValueError):
            return default

    @api.model
    def _hhmm(self, value):
        """8.5 -> "08:30"; never "08:60" for a float a hair under the hour."""
        minutes = int(round((value or 0.0) * 60)) % 1440
        return '%02d:%02d' % (minutes // 60, minutes % 60)

    @api.model
    def _minutes(self, text):
        match = _TIME.match(str(text or ''))
        if not match:
            raise UserError(_("Use a time like 08:30."))
        hours, minutes = int(match.group(1)), int(match.group(2))
        if not (0 <= hours < 24 and 0 <= minutes < 60):
            raise UserError(_("Use a time like 08:30."))
        return hours * 60 + minutes

    @api.model
    def _company_domain(self):
        return [('company_id', '=', self.env.company.id)]

    @api.model
    def _shift_domain(self):
        return ['|', ('company_id', '=', False), ('company_id', '=', self.env.company.id)]

    @api.model
    def _covering(self, day, extra=None):
        """Member rows of this company's ACTIVE working weeks covering `day`."""
        domain = [
            ('company_id', '=', self.env.company.id),
            ('pattern_id.active', '=', True),
            '|', ('date_from', '=', False), ('date_from', '<=', day),
            '|', ('date_to', '=', False), ('date_to', '>=', day),
        ]
        return self.env['pb.shift.pattern.member'].sudo().search(domain + (extra or []))

    @api.model
    def _employees(self):
        return self.env['hr.employee'].sudo().search(
            [('active', '=', True)] + self._company_domain(), order='name, id')

    # ============================================================ load
    @api.model
    def load(self, employee_id=False):
        self._gate_read()
        shifts = self._shift_rows()
        weeks = self._week_rows()
        # sudo: biz_access refuses res.company reads to attendance-only users
        # (ledger WS2); the gate above already ran and only the name is read.
        company = self.env.company.sudo()
        return {
            'can_edit': self._can_edit(),
            'company': {'id': company.id, 'name': company.name or ''},
            'today': fields.Date.to_string(self._today()),
            'features': {'rules': 'pb.attendance.policy' in self.env},
            'colors': [{'name': name, 'index': index} for name, index in COLOURS],
            'max_weeks': MAX_WEEKS,
            'steps': self._steps(shifts, weeks),
            'shifts': shifts,
            'weeks': weeks,
            'person': self.person_week(employee_id),
            # the top bar's "..." menu: administrators only (the company
            # switch refuses anyone else), how the Workforce menu is arranged
            'menu': {
                'can_switch': self.env.user.has_group('base.group_system'),
                'grouped': bool(company.pb_workforce_workspace_enabled),
            },
        }

    @api.model
    def set_workforce_menu(self, grouped):
        """The top bar's "..." menu: how the Workforce menu is arranged for
        this company — the same company switch the old setup screen wrote
        (`pb_workforce_workspace_enabled`, which itself refuses anyone but an
        administrator). Through the facade rather than a client write on
        `res.company`, which reloads the whole web client."""
        self._gate_read()
        if not self.env.user.has_group('base.group_system'):
            raise AccessError(_("Only an administrator can change how the Workforce menu is arranged."))
        self.env.company.write({'pb_workforce_workspace_enabled': bool(grouped)})
        return bool(self.env.company.pb_workforce_workspace_enabled)

    @api.model
    def _steps(self, shifts, weeks):
        usable = len(shifts)
        n_weeks = len(weeks)
        employees = self._employees()
        covered = set(self._covering(self._today(), [('employee_id', 'in', employees.ids)])
                      .mapped('employee_id').ids)
        total = len(employees)
        missing = total - len(covered)
        steps = []
        if usable:
            steps.append({'key': 'shifts', 'state': 'done',
                          'text': _("1 shift ready") if usable == 1 else _("%s shifts ready", usable)})
        else:
            steps.append({'key': 'shifts', 'state': 'warn', 'text': _("Add your first shift")})
        if n_weeks:
            steps.append({'key': 'weeks', 'state': 'done',
                          'text': _("1 working week ready") if n_weeks == 1
                          else _("%s working weeks ready", n_weeks)})
        else:
            steps.append({'key': 'weeks', 'state': 'warn', 'text': _("Build a working week")})
        if not total:
            steps.append({'key': 'people', 'state': 'todo', 'text': _("No people yet")})
        elif missing:
            steps.append({'key': 'people', 'state': 'warn', 'missing': missing, 'total': total,
                          'text': _("1 person has no working week") if missing == 1
                          else _("%s people have no working week", missing)})
        else:
            steps.append({'key': 'people', 'state': 'done', 'missing': 0, 'total': total,
                          'text': _("The 1 person has a working week") if total == 1
                          else _("All %s people have a working week", total)})
        # steps 4-7 are filled in by rules.py and golive.py
        for key in STEP_KEYS[3:]:
            steps.append({'key': key, 'state': 'todo', 'text': ''})
        return steps

    # ============================================================ shifts
    @api.model
    def _shift_rows(self, ids=None):
        domain = self._shift_domain()
        if ids is not None:
            domain = domain + [('id', 'in', list(ids))]
        shifts = self.env['hr.shift.template'].search(domain, order='sequence, id')
        if not shifts:
            return []
        weeks_by_shift = {}
        slots = self.env['pb.shift.pattern.slot'].sudo().search([
            ('template_id', 'in', shifts.ids),
            ('company_id', '=', self.env.company.id),
            ('pattern_id.active', '=', True)])
        for slot in slots:
            weeks_by_shift.setdefault(slot.template_id.id, set()).add(slot.pattern_id.id)
        roster = {template.id for template, _count in self.env['hr.shift.planning'].sudo()._read_group(
            [('shift_template_id', 'in', shifts.ids)], ['shift_template_id'], ['__count'])}
        return [self._shift_row(s, len(weeks_by_shift.get(s.id, ())), s.id in roster) for s in shifts]

    @api.model
    def _shift_row(self, shift, used_weeks=0, used_roster=False):
        return {
            'id': shift.id,
            'name': shift.name or '',
            'code': shift.code or '',
            'start': self._hhmm(shift.start_hour),
            'end': self._hhmm(shift.end_hour),
            'break_minutes': int(round((shift.break_duration or 0.0) * 60)),
            'color': COLOUR_NAME.get(shift.color, DEFAULT_COLOUR),
            'overnight': bool(shift.is_overnight),
            'paid_minutes': int(round((shift.duration or 0.0) * 60)),
            'shared': not shift.company_id,
            'used_weeks': used_weeks,
            'used_roster': bool(used_roster),
        }

    @api.model
    def _one_shift_row(self, shift):
        rows = self._shift_rows([shift.id])
        return rows[0] if rows else self._shift_row(shift)

    @api.model
    def _own_shift(self, shift_id, allow_shared=False):
        """A search, not a browse: another company's shift reads 'not there'."""
        shift = self.env['hr.shift.template'].search(
            self._shift_domain() + [('id', '=', self._int(shift_id))], limit=1)
        if not shift:
            raise UserError(_("This shift is no longer there."))
        if not allow_shared and not shift.company_id:
            raise UserError(_("This shift is shared by every company, so it cannot be changed here. Copy it to make your own."))
        return shift

    @api.model
    def _new_code(self, name):
        words = re.findall(r'\w+', name or '', flags=re.UNICODE)
        base = ''.join(w[0] for w in words).upper()[:4] or 'S'
        taken = {(c or '').upper() for c in self.env['hr.shift.template'].sudo().with_context(
            active_test=False).search(self._shift_domain()).mapped('code')}
        code, n = base, 2
        while code.upper() in taken:
            code = '%s-%s' % (base, n)
            n += 1
        return code

    @api.model
    def _shift_type(self, start_minutes):
        if start_minutes < 12 * 60:
            return 'morning'
        if start_minutes < 18 * 60:
            return 'afternoon'
        return 'night'

    @api.model
    def _clean_shift(self, vals):
        vals = vals if isinstance(vals, dict) else {}
        name = (vals.get('name') or '').strip()
        if not name:
            raise UserError(_("Give the shift a name."))
        start = self._minutes(vals.get('start'))
        end = self._minutes(vals.get('end'))
        if start == end:
            raise UserError(_("A shift needs a start and an end that differ."))
        try:
            brk = int(vals.get('break_minutes') or 0)
        except (TypeError, ValueError):
            raise UserError(_("The break is a number of minutes."))
        if brk < 0:
            raise UserError(_("The break cannot be less than zero."))
        span = (end - start) % 1440
        if brk >= span:
            raise UserError(_("The break is longer than the shift."))
        out = {
            'name': name,
            'start_hour': start / 60.0,
            'end_hour': end / 60.0,
            'break_duration': brk / 60.0,
            'is_overnight': end <= start,
        }
        colour = vals.get('color')
        if colour:
            if colour not in COLOUR_INDEX:
                raise UserError(_("Pick one of the colours shown."))
            out['color'] = COLOUR_INDEX[colour]
        return out, start

    @api.model
    def save_shift(self, vals, shift_id=False):
        """Create or change one shift. An end at or before the start is an
        overnight shift: the tick is set here, never asked for."""
        self._gate_edit()
        clean, start = self._clean_shift(vals)
        if shift_id:
            shift = self._own_shift(shift_id)
            shift.write(clean)
        else:
            clean.setdefault('color', COLOUR_INDEX[DEFAULT_COLOUR])
            clean.update({
                'company_id': self.env.company.id,
                'code': self._new_code(clean['name']),
                'shift_type': self._shift_type(start),
            })
            shift = self.env['hr.shift.template'].create(clean)
        return self._one_shift_row(shift)

    @api.model
    def copy_shift(self, shift_id):
        self._gate_edit()
        source = self._own_shift(shift_id, allow_shared=True)
        name = _("%s (copy)", source.name)
        shift = source.copy({
            'name': name,
            'code': self._new_code(name),
            'company_id': self.env.company.id,
        })
        return self._one_shift_row(shift)

    @api.model
    def remove_shift(self, shift_id):
        """Delete when nothing points at the shift; hide (archive) it when only
        history does; refuse while a working week still uses it."""
        self._gate_edit()
        shift = self._own_shift(shift_id)
        n_weeks = len(self.env['pb.shift.pattern.slot'].search([
            ('template_id', '=', shift.id), ('pattern_id.active', '=', True)]).mapped('pattern_id'))
        if n_weeks:
            raise UserError(_("This shift is used in 1 working week. Take it out of it first.")
                            if n_weeks == 1 else
                            _("This shift is used in %s working weeks. Take it out of them first.", n_weeks))
        referenced = bool(
            self.env['pb.shift.pattern.slot'].sudo().search_count([('template_id', '=', shift.id)])
            or self.env['hr.shift.planning'].sudo().with_context(active_test=False).search_count(
                [('shift_template_id', '=', shift.id)]))
        if not referenced and 'pb.attendance.policy.shift' in self.env:
            referenced = bool(self.env['pb.attendance.policy.shift'].sudo().search_count(
                [('template_id', '=', shift.id)]))
        if not referenced:
            try:
                with self.env.cr.savepoint():
                    shift.unlink()
                return {'archived': False}
            except Exception:       # a reference this check does not know (FK restrict)
                referenced = True
        shift.active = False
        return {'archived': True}

    # ============================================================ working weeks
    @api.model
    def _week_rows(self, ids=None):
        domain = self._company_domain()
        if ids is not None:
            domain = domain + [('id', 'in', list(ids))]
        patterns = self.env['pb.shift.pattern'].sudo().search(domain, order='id')   # stable while renaming
        if not patterns:
            return []
        today = self._today()
        people = {}
        members = self.env['pb.shift.pattern.member'].sudo().search([
            ('pattern_id', 'in', patterns.ids),
            '|', ('date_to', '=', False), ('date_to', '>=', today)])
        for m in members:
            people.setdefault(m.pattern_id.id, set()).add(m.employee_id.id)
        return [self._week_row(p, len(people.get(p.id, ()))) for p in patterns]

    @api.model
    def _week_row(self, pattern, n_people=0):
        cycle = max(1, pattern.cycle_days or 1)
        slots = pattern._pb_slot_map()
        days = [slots[i].id if i in slots else False for i in range(cycle)]
        whole = cycle % 7 == 0
        monday = bool(pattern.start_date) and pattern.start_date.weekday() == 0
        weeks, minutes = [], []
        if whole:
            shift_by_day = {i: slots[i] for i in slots}
            lead = pattern.start_date.weekday() if pattern.start_date else 0
            for w in range(cycle // 7):
                row, paid = [], 0
                for d in range(7):
                    # column d is a weekday; on a non-Monday start the cycle
                    # day under it moves, so display still lines up.
                    k = 7 * w + ((d - lead) % 7)
                    shift = shift_by_day.get(k)
                    row.append(shift.id if shift else False)
                    paid += int(round((shift.duration or 0.0) * 60)) if shift else 0
                weeks.append(row)
                minutes.append(paid)
        editable = whole and monday
        return {
            'id': pattern.id,
            'name': pattern.name or '',
            'editable': editable,
            'weeks': weeks,
            'days': days,
            'people': n_people,
            'minutes_per_week': minutes,
            'cycle_days': cycle,
            'teams': len(pattern.team_ids),
            'reason': False if editable else _("This rotation does not follow whole weeks."),
        }

    @api.model
    def _one_week_row(self, pattern):
        rows = self._week_rows([pattern.id])
        return rows[0] if rows else self._week_row(pattern)

    @api.model
    def _own_week(self, week_id):
        pattern = self.env['pb.shift.pattern'].search(
            self._company_domain() + [('id', '=', self._int(week_id))], limit=1)
        if not pattern:
            raise UserError(_("This working week is no longer there."))
        return pattern

    @api.model
    def _clean_grid(self, weeks, company):
        if not isinstance(weeks, (list, tuple)) or not 1 <= len(weeks) <= MAX_WEEKS:
            raise UserError(_("A working week repeats over 1 to %s weeks.", MAX_WEEKS))
        allowed = set(self.env['hr.shift.template'].sudo().search([
            '|', ('company_id', '=', False), ('company_id', '=', company.id)]).ids)
        wanted = {}
        for w, row in enumerate(weeks):
            if not isinstance(row, (list, tuple)) or len(row) != 7:
                raise UserError(_("Each week has seven days."))
            for d, value in enumerate(row):
                tid = self._int(value, 0) if value else 0
                if not tid:
                    continue
                if tid not in allowed:
                    raise UserError(_("A shift in this working week is not available in this company."))
                wanted[7 * w + d] = tid
        return wanted, 7 * len(weeks)

    @api.model
    def save_week(self, vals, week_id=False):
        """Create or change one working week: its name and its days.

        Never `save_pattern` (it replaces teams and members whole). Slots are
        upserted by day index; teams and people are untouched, ids and all.
        """
        self._gate_edit()
        vals = vals if isinstance(vals, dict) else {}
        name = (vals.get('name') or '').strip()
        if not name:
            raise UserError(_("Give the working week a name."))
        if week_id:
            pattern = self._own_week(week_id)
            if not (pattern.cycle_days % 7 == 0 and pattern.start_date
                    and pattern.start_date.weekday() == 0):
                raise UserError(_("This rotation does not follow whole weeks. Change it in the rotation editor."))
            company = pattern.company_id
        else:
            pattern = self.env['pb.shift.pattern']
            company = self.env.company
        if 'weeks' in vals:
            wanted, cycle = self._clean_grid(vals.get('weeks'), company)
        elif pattern:
            wanted = {i: t.id for i, t in pattern._pb_slot_map().items()}
            cycle = pattern.cycle_days
        else:
            wanted, cycle = {}, 7

        if not pattern:
            pattern = pattern.create({
                'name': name,
                'company_id': company.id,
                'start_date': self._monday(),
                'cycle_days': cycle,
                'slot_ids': [(0, 0, {'day_index': k, 'template_id': t}) for k, t in sorted(wanted.items())],
            })
            self.env['pb.shift.pattern.team'].create({
                'pattern_id': pattern.id, 'name': _("Team %s", 'A'),
                'sequence': 10, 'offset_days': 0})
            return self._one_week_row(pattern)

        if any((t.offset_days or 0) >= cycle for t in pattern.team_ids):
            raise UserError(_("A team in this working week starts in a later week. Move that team first in the rotation editor."))
        commands = []
        seen = set()
        for slot in pattern.slot_ids:
            k = slot.day_index
            if k >= cycle or k in seen:
                commands.append((2, slot.id, 0))
                continue
            seen.add(k)
            want = wanted.get(k, False)
            if (slot.template_id.id or False) != want:
                commands.append((1, slot.id, {'template_id': want}))
        for k in sorted(wanted):
            if k not in seen:
                commands.append((0, 0, {'day_index': k, 'template_id': wanted[k]}))
        write = {}
        if name != pattern.name:
            write['name'] = name
        if cycle != pattern.cycle_days:
            write['cycle_days'] = cycle
        if commands:
            write['slot_ids'] = commands
        if write:
            try:
                with self.env.cr.savepoint():
                    pattern.write(write)
                    pattern._check_cycle()
            except ValidationError:
                raise UserError(_("A team in this working week starts in a later week. Move that team first in the rotation editor."))
        return self._one_week_row(pattern)

    @api.model
    def remove_week(self, week_id):
        self._gate_edit()
        pattern = self._own_week(week_id)
        today = self._today()
        people = set(self.env['pb.shift.pattern.member'].sudo().search([
            ('pattern_id', '=', pattern.id),
            '|', ('date_to', '=', False), ('date_to', '>=', today)]).mapped('employee_id').ids)
        if people:
            n = len(people)
            raise UserError(_("1 person works this week. Move them to another week first.") if n == 1
                            else _("%s people work this week. Move them to another week first.", n))
        self.env['pb.shift.patterns'].archive_pattern(pattern.id)
        return {'archived': True}

    # ============================================================ people panel
    @api.model
    def find_people(self, query='', limit=20):
        self._gate_read()
        q = (query or '').strip()
        domain = [('active', '=', True)] + self._company_domain()
        if q:
            domain += ['|', ('name', 'ilike', q), ('department_id.name', 'ilike', q)]
        limit = max(1, min(self._int(limit, 20) or 20, 50))
        emps = self.env['hr.employee'].sudo().search(domain, order='name, id', limit=limit)
        covered = set(self._covering(self._today(), [('employee_id', 'in', emps.ids)])
                      .mapped('employee_id').ids)
        return [{'id': e.id, 'name': e.name or '', 'department': e.department_id.name or '',
                 'has_week': e.id in covered} for e in emps]

    @api.model
    def person_week(self, employee_id=False):
        """One person's CURRENT week, Monday to Sunday, from their working
        week: the real cycle index (`_pb_cycle_index`), team offset and member
        dates honoured. False when the company has nobody."""
        self._gate_read()
        Employee = self.env['hr.employee'].sudo()
        emp = Employee
        if employee_id:
            emp = Employee.search([('id', '=', self._int(employee_id)), ('active', '=', True)]
                                  + self._company_domain(), limit=1)
        today = self._today()
        if not emp:
            covering = self._covering(today)
            if covering:
                emp = Employee.search([('id', 'in', covering.mapped('employee_id').ids)],
                                      order='name, id', limit=1)
        if not emp:
            emp = Employee.search([('active', '=', True)] + self._company_domain(),
                                  order='name, id', limit=1)
        if not emp:
            return False
        member = self._covering(today, [('employee_id', '=', emp.id)]).sorted(
            lambda m: (m.pattern_id.name or '', m.id))[:1]
        monday = self._monday(today)
        days = []
        week_no = False
        slots = member.pattern_id._pb_slot_map() if member else {}
        if member:
            pattern = member.pattern_id
            if pattern.cycle_days % 7 == 0 and pattern.cycle_days > 7:
                week_no = pattern._pb_cycle_index(monday, member.team_id.offset_days) // 7 + 1
        for i in range(7):
            day = monday + timedelta(days=i)
            shift = False
            if member and member._pb_covers(day):
                shift = slots.get(member.pattern_id._pb_cycle_index(day, member.team_id.offset_days)) or False
            days.append({
                'label': format_date(self.env, day, date_format='EEE'),
                'date': fields.Date.to_string(day),
                'today': day == today,
                'shift_id': shift.id if shift else False,
                'name': shift.name if shift else '',
                'color': COLOUR_NAME.get(shift.color, DEFAULT_COLOUR) if shift else False,
                'start': self._hhmm(shift.start_hour) if shift else '',
                'end': self._hhmm(shift.end_hour) if shift else '',
            })
        return {
            'id': emp.id,
            'name': emp.name or '',
            'department': emp.department_id.name or '',
            'week_name': member.pattern_id.name if member else False,
            'week_id': member.pattern_id.id if member else False,
            'week_no': week_no,
            'days': days,
        }
