# Part of Payobook. See LICENSE file for full copyright and licensing details.
"""Step 3 "Who works what" (WFSETUP P2) — the people table and its bulk actions.

Extends the facade `pb.workforce.setup`. Same contract as P1: every method is
gated on the server (`_gate_read` for the table, `_gate_edit` for every
preview AND every write — previews read roster rows an officer may not see),
every domain is the CURRENT company.

Reads of people go through sudo BEHIND the gate and only the listed fields
leave the server (facts K3, K24). Writes:
  * working weeks  -> `pb.shift.pattern.member` / `.team` through the ORM as
    the caller (attendance manager CRUD), never `save_pattern` (it replaces
    members whole, facts B.2);
  * one-off shifts -> `hr.shift.planning` through the ORM as the caller, UTC
    windows from `Grid._pb_shift_window` (facts K25), checks from
    `Grid._pb_check` (facts C), batch savepoint with per-row fallback and
    tracking off (precedent `pattern_engine.apply`);
  * late rule     -> `hr.employee.pb_attendance_category` with sudo after the
    edit gate (the field is HR-officer-only, facts K24).

Every write records an undo row (`pb.workforce.setup.undo`); `undo()` puts it
back exactly or refuses whole.

Screen words: working week (pattern), team (department in the strip; a
rotation "start point" is a pattern team and is never named on screen except
as "week N"), one-off shift (a roster row without a working week), late rule
(attendance deduction group).
"""

from datetime import timedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError
from odoo.tools.misc import format_date

from odoo.addons.pb_shift_patterns.models.shift_pattern import MAX_TEAMS, TEAM_LETTERS

PEOPLE_CAP = 5000
ONEOFF_MAX_DAYS = 62
ONEOFF_MAX_ROWS = 5000
LIVE_STATES = ('draft', 'published', 'completed')
GROUPS = ('worker', 'manager')
# roster fields kept when a draft is replaced, so undo can put it back
# (calculated fields are refused on create by pb_attendance_policy)
DRAFT_FIELDS = ('employee_id', 'shift_template_id', 'date', 'start_datetime', 'end_datetime',
                'state', 'company_id', 'note', 'pb_pattern_id', 'pb_pattern_sig', 'pb_policy_id',
                'pb_day_kind', 'pb_category', 'pb_inferred', 'pb_evidence')


class WorkforceSetupPeople(models.AbstractModel):
    _inherit = 'pb.workforce.setup'

    # ------------------------------------------------------------ helpers
    @api.model
    def _changed_sentence(self):
        return _("Someone changed these people after you. Nothing was undone.")

    @api.model
    def _date(self, value):
        try:
            day = fields.Date.to_date(value)
        except (TypeError, ValueError):
            day = None
        if not day:
            raise UserError(_("Pick a date."))
        return day

    @api.model
    def _day_text(self, day):
        return format_date(self.env, day, date_format='EEE d MMM')

    @api.model
    def _ticked(self, employee_ids):
        """The ticked people that are still active in this company (sudo read,
        behind the caller's gate)."""
        ids = []
        for value in (employee_ids or []):
            n = self._int(value, 0)
            if n > 0:
                ids.append(n)
        if not ids:
            raise UserError(_("Tick at least one person."))
        emps = self.env['hr.employee'].sudo().search(
            [('id', 'in', ids), ('active', '=', True)] + self._company_domain(), order='name, id')
        if not emps:
            raise UserError(_("The people you ticked are no longer here. Refresh the list."))
        return emps

    @api.model
    def _gone_problem(self, employee_ids, emps):
        asked = {self._int(v, 0) for v in (employee_ids or [])} - {0}
        gone = len(asked - set(emps.ids))
        if not gone:
            return []
        return [_("1 of the people you ticked is no longer here and is left out.") if gone == 1
                else _("%s of the people you ticked are no longer here and are left out.", gone)]

    @api.model
    def _initials(self, name):
        words = [w for w in (name or '').replace(',', ' ').split() if w and w[0].isalpha()]
        if not words:
            return '?'
        if len(words) == 1:
            return words[0][:2].upper()
        return (words[0][0] + words[-1][0]).upper()

    @api.model
    def _admin_employee_ids(self):
        """The administrator / system account's employee rows: never the
        default person of the right panel (owner note on P2)."""
        users = self.env['res.users']
        for xmlid in ('base.user_admin', 'base.user_root'):
            user = self.env.ref(xmlid, raise_if_not_found=False)
            if user:
                users |= user
        if not users:
            return set()
        return set(self.env['hr.employee'].sudo().with_context(active_test=False).search(
            [('user_id', 'in', users.ids)]).ids)

    @api.model
    def _default_person(self):
        """First employee by name who has a working week today and is not the
        administrator; else the first non-administrator; else anyone."""
        Employee = self.env['hr.employee'].sudo()
        admins = list(self._admin_employee_ids())
        base = [('active', '=', True)] + self._company_domain()
        covering = self._covering(self._today())
        if covering:
            emp = Employee.search(base + [('id', 'in', covering.mapped('employee_id').ids),
                                          ('id', 'not in', admins)], order='name, id', limit=1)
            if emp:
                return emp
        return (Employee.search(base + [('id', 'not in', admins)], order='name, id', limit=1)
                or Employee.search(base, order='name, id', limit=1))

    @api.model
    def person_week(self, employee_id=False):
        if not employee_id:
            self._gate_read()
            emp = self._default_person()
            return super().person_week(emp.id) if emp else False
        return super().person_week(employee_id)

    # ============================================================ the table
    @api.model
    def people(self):
        """Every active person of the company, in one call (the client filters,
        searches and sorts in memory). Hard cap PEOPLE_CAP, reported."""
        self._gate_read()
        today = self._today()
        Employee = self.env['hr.employee'].sudo()
        emps = Employee.search([('active', '=', True)] + self._company_domain(),
                               order='name, id', limit=PEOPLE_CAP + 1)
        capped = len(emps) > PEOPLE_CAP
        emps = emps[:PEOPLE_CAP]
        values = emps.read(['name', 'department_id', 'work_location_id', 'pb_clock_code',
                            'barcode', 'pb_attendance_category'])

        # working weeks from today on, one search (+ prefetch)
        members = self.env['pb.shift.pattern.member'].sudo().search([
            ('employee_id', 'in', emps.ids),
            ('company_id', '=', self.env.company.id),
            ('pattern_id.active', '=', True),
            '|', ('date_to', '=', False), ('date_to', '>=', today)])
        by_emp = {}
        for m in members:
            by_emp.setdefault(m.employee_id.id, []).append(m)
        slot_maps = {}

        def slots(pattern):
            if pattern.id not in slot_maps:
                slot_maps[pattern.id] = pattern._pb_slot_map()
            return slot_maps[pattern.id]

        # one-off shifts (roster rows not made by a working week) from today on
        oneoff = {emp.id: count for emp, count in self.env['hr.shift.planning'].sudo()._read_group(
            [('employee_id', 'in', emps.ids), ('date', '>=', today),
             ('state', 'in', ('draft', 'published')), ('pb_pattern_id', '=', False),
             ('company_id', '=', self.env.company.id)],
            ['employee_id'], ['__count'])}

        rows, teams, sites = [], {}, set()
        without = 0
        for v in values:
            mine = by_emp.get(v['id'], [])
            covering = sorted((m for m in mine if m._pb_covers(today)),
                              key=lambda m: (m.pattern_id.name or '', m.id))
            current = covering[0] if covering else False
            chosen = current or (min(mine, key=lambda m: (m.date_from, m.id)) if mine else False)
            week_days, week_no, also = [False] * 7, False, []
            if chosen:
                pattern = chosen.pattern_id
                ref = today if current else chosen.date_from
                monday = ref - timedelta(days=ref.weekday())
                smap = slots(pattern)
                offset = chosen.team_id.offset_days
                for i in range(7):
                    shift = smap.get(pattern._pb_cycle_index(monday + timedelta(days=i), offset))
                    week_days[i] = shift.id if shift else False
                cycle = pattern.cycle_days or 7
                if cycle % 7 == 0 and cycle > 7:
                    week_no = pattern._pb_cycle_index(monday, offset) // 7 + 1
                lo = max(today, chosen.date_from or today)
                hi = chosen.date_to
                for m in mine:
                    if m.pattern_id == pattern:
                        continue
                    if (m.date_from or lo) <= (hi or m.date_from or lo) and lo <= (m.date_to or lo) \
                            and m.pattern_id.name not in also:
                        also.append(m.pattern_id.name)
            if not current:
                without += 1
            dept_id = v['department_id'][0] if v['department_id'] else 0
            dept = v['department_id'][1] if v['department_id'] else ''
            site = v['work_location_id'][1] if v['work_location_id'] else ''
            if site:
                sites.add(site)
            team = teams.setdefault(dept_id, {'id': dept_id, 'name': dept or _("No team"),
                                              'total': 0, 'with_week': 0})
            team['total'] += 1
            team['with_week'] += 1 if current else 0
            rows.append({
                'id': v['id'],
                'name': v['name'] or '',
                'number': (v.get('pb_clock_code') or v.get('barcode') or '').strip(),
                'initials': self._initials(v['name']),
                'department_id': dept_id,
                'department': dept,
                'site': site,
                'group': v.get('pb_attendance_category') or False,
                'week_id': chosen.pattern_id.id if chosen else False,
                'week_name': chosen.pattern_id.name if chosen else False,
                'team_name': chosen.team_id.name if chosen else False,
                'week_no': week_no,
                'week_from': fields.Date.to_string(chosen.date_from) if chosen and chosen.date_from else False,
                'week_now': bool(current),
                'week_days': week_days,
                'also_on': also,
                'oneoff': oneoff.get(v['id'], 0),
            })
        ordered = sorted(teams.values(), key=lambda t: (t['id'] == 0, (t['name'] or '').lower()))
        return {
            'rows': rows,
            'teams': ordered,
            'sites': sorted(sites),
            'total': len(rows),
            'without_week': without,
            'capped': capped,
            'cap': PEOPLE_CAP,
            'today': fields.Date.to_string(today),
        }

    # ============================================================ give a working week
    @api.model
    def _assign_plan(self, employee_ids, week_id, date_from, start_week=0, mode='replace'):
        if mode not in ('replace', 'keep'):
            mode = 'replace'
        emps = self._ticked(employee_ids)
        week = self._own_week(week_id).sudo()
        day = self._date(date_from)
        today = self._today()
        if day < today:
            raise UserError(_("Pick today or a later date. Past weeks stay as they were."))
        cycle = max(1, week.cycle_days or 1)
        n_weeks = cycle // 7 if (cycle % 7 == 0 and cycle > 7) else 1
        start_week = self._int(start_week, 0)
        if not 0 <= start_week < n_weeks:
            raise UserError(_("Pick one of the weeks of this rotation."))
        if not week.start_date:
            raise UserError(_("This working week has no first day. Open it in step 2 and save it again."))
        monday = self._monday(day)
        # the team whose cycle puts `monday` on day 7*start_week (facts B.1):
        # _pb_cycle_index(monday, offset) == 7*start_week  <=>  offset below
        offset = ((monday - week.start_date).days - 7 * start_week) % cycle
        team = week.team_ids.filtered(lambda t: (t.offset_days or 0) % cycle == offset)[:1]
        team_name = team.name if team else False
        if not team:
            if len(week.team_ids) >= MAX_TEAMS:
                raise UserError(_("This working week already has 8 different start points. Pick another start week."))
            used = set(week.team_ids.mapped('name'))
            team_name = next((_("Team %s", letter) for letter in TEAM_LETTERS
                              if _("Team %s", letter) not in used),
                             _("Team %s", len(week.team_ids) + 1))

        members = self.env['pb.shift.pattern.member'].sudo().search([
            ('employee_id', 'in', emps.ids),
            ('company_id', '=', self.env.company.id),
            ('pattern_id.active', '=', True),
            '|', ('date_to', '=', False), ('date_to', '>=', day)])
        by_emp = {}
        for m in members:
            by_emp.setdefault(m.employee_id.id, []).append(m)

        moved, kept, already = [], [], []
        to_end, to_delete = [], []
        have_other = 0
        ends = {}
        for emp in emps:
            mine = [m for m in by_emp.get(emp.id, []) if m.pattern_id == week]
            others = [m for m in by_emp.get(emp.id, []) if m.pattern_id != week]
            if team and any(m.team_id == team and m._pb_covers(day) for m in mine):
                already.append(emp)
                continue
            if others:
                have_other += 1
                if mode == 'keep':
                    kept.append(emp)
                    continue
            moved.append(emp)
            for m in mine + (others if mode == 'replace' else []):
                if m.date_from and m.date_from >= day:
                    to_delete.append(m)
                else:
                    to_end.append(m)
                if m.pattern_id != week:
                    ends.setdefault(m.pattern_id.id, {'week_name': m.pattern_id.name, 'people': set()})
                    ends[m.pattern_id.id]['people'].add(emp.id)
        return {
            'emps': emps, 'week': week, 'day': day, 'start_week': start_week, 'mode': mode,
            'offset': offset, 'team': team, 'team_name': team_name, 'new_team': not team,
            'moved': moved, 'kept': kept, 'already': already, 'have_other': have_other,
            'to_end': to_end, 'to_delete': to_delete,
            'ends': [{'week_name': e['week_name'], 'people': len(e['people'])} for e in ends.values()],
            'n_weeks': n_weeks,
        }

    @api.model
    def assign_week_preview(self, employee_ids, week_id, date_from, start_week=0, mode='replace'):
        """What `assign_week` would do, as numbers. Writes nothing."""
        self._gate_edit()
        try:
            plan = self._assign_plan(employee_ids, week_id, date_from, start_week, mode)
        except UserError as e:
            return {'will_move': 0, 'keep_theirs': 0, 'already': 0, 'ends': [], 'team_name': False,
                    'new_team': False, 'problems': [e.args[0] if e.args else str(e)]}
        return {
            'will_move': len(plan['moved']),
            'keep_theirs': plan['have_other'],
            'kept': len(plan['kept']),
            'already': len(plan['already']),
            'ends': plan['ends'],
            'team_name': plan['team_name'],
            'new_team': plan['new_team'],
            'week_name': plan['week'].name,
            'date_from': fields.Date.to_string(plan['day']),
            'date_text': self._day_text(plan['day']),
            'ends_text': self._day_text(plan['day'] - timedelta(days=1)),
            'start_week': plan['start_week'],
            'rotation_weeks': plan['n_weeks'],
            'problems': self._gone_problem(employee_ids, plan['emps']),
        }

    @api.model
    def assign_week(self, employee_ids, week_id, date_from, start_week=0, mode='replace'):
        """Put the ticked people on a working week from `date_from`, in one
        transaction, and record exactly what changed for undo."""
        self._gate_edit()
        plan = self._assign_plan(employee_ids, week_id, date_from, start_week, mode)
        week, day = plan['week'], plan['day']
        Member = self.env['pb.shift.pattern.member']          # as the caller
        Team = self.env['pb.shift.pattern.team']
        if not plan['moved']:
            return {'moved': 0, 'kept': len(plan['kept']), 'already': len(plan['already']),
                    'undo_id': False, 'summary': _("Nothing changed.")}
        teams_created = []
        team = plan['team']
        if not team:
            seq = max(week.team_ids.mapped('sequence') or [0]) + 10
            team = Team.create({'pattern_id': week.id, 'name': plan['team_name'],
                                'sequence': seq, 'offset_days': plan['offset']})
            teams_created.append(team.id)
        ended, deleted = [], []
        before = day - timedelta(days=1)
        for m in plan['to_end']:
            ended.append({'id': m.id, 'prev': fields.Date.to_string(m.date_to) if m.date_to else False,
                          'new': fields.Date.to_string(before)})
        for m in plan['to_delete']:
            deleted.append({'pattern_id': m.pattern_id.id, 'team_id': m.team_id.id,
                            'employee_id': m.employee_id.id,
                            'date_from': fields.Date.to_string(m.date_from) if m.date_from else False,
                            'date_to': fields.Date.to_string(m.date_to) if m.date_to else False})
        if plan['to_end']:
            Member.browse([m.id for m in plan['to_end']]).write({'date_to': before})
        if plan['to_delete']:
            Member.browse([m.id for m in plan['to_delete']]).unlink()
        created = Member.create([{'pattern_id': week.id, 'team_id': team.id, 'employee_id': emp.id,
                                  'date_from': day, 'date_to': False} for emp in plan['moved']])
        n = len(plan['moved'])
        summary = (_("1 person now works “%s”.", week.name) if n == 1
                   else _("%(n)s people now work “%(week)s”.", n=n, week=week.name))
        undo = self.env['pb.workforce.setup.undo'].create({
            'kind': 'assign', 'summary': summary,
            'payload': {
                'created': [{'id': m.id, 'employee_id': m.employee_id.id, 'team_id': team.id,
                             'date_from': fields.Date.to_string(day)} for m in created],
                'ended': ended, 'deleted': deleted, 'teams': teams_created,
            },
        })
        return {'moved': n, 'kept': len(plan['kept']), 'already': len(plan['already']),
                'undo_id': undo.id, 'summary': summary}

    @api.model
    def _undo_assign(self, payload):
        Member = self.env['pb.shift.pattern.member']
        created = Member.browse([c['id'] for c in payload.get('created', [])]).exists()
        if len(created) != len(payload.get('created', [])):
            raise UserError(self._changed_sentence())
        by_id = {c['id']: c for c in payload['created']}
        for m in created:
            want = by_id[m.id]
            if (m.employee_id.id != want['employee_id'] or m.team_id.id != want['team_id']
                    or fields.Date.to_string(m.date_from) != want['date_from'] or m.date_to):
                raise UserError(self._changed_sentence())
        ended = Member.browse([e['id'] for e in payload.get('ended', [])]).exists()
        if len(ended) != len(payload.get('ended', [])):
            raise UserError(self._changed_sentence())
        ended_by_id = {e['id']: e for e in payload['ended']}
        for m in ended:
            if fields.Date.to_string(m.date_to) != ended_by_id[m.id]['new']:
                raise UserError(self._changed_sentence())
        teams = self.env['pb.shift.pattern.team'].browse(payload.get('teams', [])).exists()
        if teams and (teams.member_ids - created):
            raise UserError(self._changed_sentence())
        try:
            with self.env.cr.savepoint():
                created.unlink()
                for m in ended:
                    m.write({'date_to': ended_by_id[m.id]['prev'] or False})
                if payload.get('deleted'):
                    Member.create([{
                        'pattern_id': d['pattern_id'], 'team_id': d['team_id'],
                        'employee_id': d['employee_id'], 'date_from': d['date_from'] or False,
                        'date_to': d['date_to'] or False} for d in payload['deleted']])
                teams.unlink()
                self.env.flush_all()
        except (UserError, ValidationError):
            raise UserError(self._changed_sentence())

    # ============================================================ one-off shift
    @api.model
    def _oneoff_labels(self):
        return {
            'past': _("in the past"),
            'published': _("already published"),
            'locked': _("already has clock-ins"),
            'leave_approved': _("on approved leave"),
            'overlap': _("overlaps another shift"),
            'young_worker_night': _("night work is not allowed for this person"),
            'refused': _("could not be added"),
        }

    @api.model
    def _oneoff_plan(self, employee_ids, shift_id, date_from, date_to, weekdays):
        emps = self._ticked(employee_ids)
        shift = self._own_shift(shift_id, allow_shared=True)
        first, last = self._date(date_from), self._date(date_to)
        if last < first:
            raise UserError(_("The last day is before the first day."))
        if (last - first).days + 1 > ONEOFF_MAX_DAYS:
            raise UserError(_("Pick %s days or fewer at a time. Split a longer stretch into two.", ONEOFF_MAX_DAYS))
        wanted = set()
        for value in (weekdays or []):
            n = self._int(value, -1)
            if 0 <= n <= 6:
                wanted.add(n)
        if not wanted:
            raise UserError(_("Pick at least one day of the week."))
        days = [first + timedelta(days=i) for i in range((last - first).days + 1)
                if (first + timedelta(days=i)).weekday() in wanted]
        if len(days) * len(emps) > ONEOFF_MAX_ROWS:
            raise UserError(_("That is more than %s shifts at once. Tick fewer people or pick fewer days.", '5,000'))

        Grid = self.env['hr.shift.planning.grid']
        Shift = self.env['hr.shift.planning']                 # as the caller
        today = self._today()
        future = [d for d in days if d >= today]
        existing = {}
        if future:
            for row in Shift.search([('employee_id', 'in', emps.ids), ('date', 'in', future),
                                     ('state', 'in', LIVE_STATES)]):
                existing.setdefault((row.employee_id.id, row.date), Shift.browse())
                existing[(row.employee_id.id, row.date)] |= row
        windows = Grid._pb_shift_windows(emps.ids, first, last) if future else {}
        leaves = Grid._pb_leave_map(emps.ids, first, last) if future else {}
        has_calc = 'pb_attendance_id' in Shift._fields
        has_policy = 'pb_policy_id' in Shift._fields
        policies = {}
        if has_policy:
            policies = {e.id: e.pb_attendance_policy_id.id for e in emps}   # sudo read (emps are sudo)

        creates, replace = [], Shift.browse()
        skipped, examples = {}, []
        labels = self._oneoff_labels()

        def skip(emp, day, code):
            skipped[code] = skipped.get(code, 0) + 1
            if len(examples) < 5:
                examples.append(_("%(name)s, %(day)s: %(why)s.", name=emp.name,
                                  day=self._day_text(day), why=labels.get(code, code)))

        for emp in emps:
            win = list(windows.get(emp.id, []))
            for day in days:
                if day < today:
                    skip(emp, day, 'past')
                    continue
                rows = existing.get((emp.id, day), Shift.browse())
                if rows.filtered(lambda r: r.state != 'draft'):
                    skip(emp, day, 'published')
                    continue
                if has_calc and rows.filtered('pb_attendance_id'):
                    skip(emp, day, 'locked')
                    continue
                gone = set(rows.ids)
                trial = [w for w in win if w[2] not in gone]
                warns = Grid._pb_check(emp, day, shift, {emp.id: trial}, leaves, {})
                code = next((w['code'] for w in warns if w['severity'] == 'block'), None) \
                    or next((w['code'] for w in warns
                             if w['severity'] == 'warn' and w['code'] in ('leave_approved', 'overlap')), None)
                if code:
                    skip(emp, day, code)
                    continue
                tz = Grid._pb_shift_tzname(emp)
                start, end = Grid._pb_shift_window(shift, day, tz)
                vals = {'employee_id': emp.id, 'shift_template_id': shift.id, 'date': day,
                        'start_datetime': start, 'end_datetime': end, 'state': 'draft',
                        'company_id': self.env.company.id}
                if has_policy:
                    # set it here (from the sudo read) so the roster hook does
                    # not read an HR-only field as the caller
                    vals['pb_policy_id'] = policies.get(emp.id) or False
                if 'pb_pattern_id' in Shift._fields:
                    vals['pb_pattern_id'] = False
                creates.append(vals)
                replace |= rows
                win = trial + [(start, end, 0)]
        return {'emps': emps, 'shift': shift, 'first': first, 'last': last, 'days': days,
                'creates': creates, 'replace': replace, 'skipped': skipped, 'examples': examples,
                'labels': labels}

    @api.model
    def _oneoff_out(self, plan):
        labels = plan['labels']
        return {
            'days': len(plan['days']),
            'people': len(plan['emps']),
            'will_add': len(plan['creates']),
            'replace_drafts': len(plan['replace']),
            'skipped': dict(plan['skipped']),
            'skipped_list': [{'code': k, 'label': labels.get(k, k), 'count': v}
                             for k, v in sorted(plan['skipped'].items(), key=lambda kv: -kv[1])],
            'examples': plan['examples'],
        }

    @api.model
    def oneoff_preview(self, employee_ids, shift_id, date_from, date_to, weekdays):
        """What `oneoff_apply` would do. Writes nothing."""
        self._gate_edit()
        try:
            plan = self._oneoff_plan(employee_ids, shift_id, date_from, date_to, weekdays)
        except UserError as e:
            return {'days': 0, 'people': 0, 'will_add': 0, 'replace_drafts': 0, 'skipped': {},
                    'skipped_list': [], 'examples': [], 'problems': [e.args[0] if e.args else str(e)]}
        out = self._oneoff_out(plan)
        out['problems'] = self._gone_problem(employee_ids, plan['emps'])
        return out

    @api.model
    def oneoff_apply(self, employee_ids, shift_id, date_from, date_to, weekdays):
        self._gate_edit()
        plan = self._oneoff_plan(employee_ids, shift_id, date_from, date_to, weekdays)
        Shift = self.env['hr.shift.planning'].with_context(
            tracking_disable=True, mail_create_nolog=True, mail_notrack=True)
        removed = []
        fields_kept = [f for f in DRAFT_FIELDS if f in Shift._fields]
        for row in plan['replace']:
            vals = {}
            for name in fields_kept:
                value = row[name]
                field = Shift._fields[name]
                if field.type == 'many2one':
                    value = value.id or False
                elif field.type == 'date':
                    value = fields.Date.to_string(value) if value else False
                elif field.type == 'datetime':
                    value = fields.Datetime.to_string(value) if value else False
                vals[name] = value
            removed.append(vals)
        if plan['replace']:
            plan['replace'].unlink()
        created = Shift.browse()
        refused = 0
        if plan['creates']:
            try:
                with self.env.cr.savepoint():
                    created = Shift.create(plan['creates'])
            except (UserError, ValidationError):
                for vals in plan['creates']:
                    try:
                        with self.env.cr.savepoint():
                            created |= Shift.create(vals)
                    except (UserError, ValidationError):
                        refused += 1
        skipped = dict(plan['skipped'])
        if refused:
            skipped['refused'] = refused
        n, people = len(created), len(set(created.mapped('employee_id').ids))
        if n == 1:
            summary = _("1 one-off shift added.")
        elif people == 1:
            summary = _("%s one-off shifts added for 1 person.", n)
        else:
            summary = _("%(n)s one-off shifts added for %(p)s people.", n=n, p=people)
        undo_id = False
        if created or removed:
            undo_id = self.env['pb.workforce.setup.undo'].create({
                'kind': 'oneoff', 'summary': summary,
                'payload': {
                    'created': [{'id': r.id, 'employee_id': r.employee_id.id,
                                 'template_id': r.shift_template_id.id,
                                 'start': fields.Datetime.to_string(r.start_datetime),
                                 'end': fields.Datetime.to_string(r.end_datetime)} for r in created],
                    'removed': removed,
                },
            }).id
        return {'added': n, 'replaced': len(removed), 'skipped': skipped,
                'skipped_total': sum(skipped.values()), 'undo_id': undo_id, 'summary': summary}

    @api.model
    def _undo_oneoff(self, payload):
        Shift = self.env['hr.shift.planning'].with_context(
            tracking_disable=True, mail_create_nolog=True, mail_notrack=True)
        want = {c['id']: c for c in payload.get('created', [])}
        created = Shift.browse(list(want)).exists()
        if len(created) != len(want):
            raise UserError(self._changed_sentence())
        for r in created:
            w = want[r.id]
            if (r.state != 'draft' or r.employee_id.id != w['employee_id']
                    or r.shift_template_id.id != w['template_id']
                    or fields.Datetime.to_string(r.start_datetime) != w['start']
                    or fields.Datetime.to_string(r.end_datetime) != w['end']
                    or ('pb_attendance_id' in Shift._fields and r.pb_attendance_id)):
                raise UserError(self._changed_sentence())
        try:
            with self.env.cr.savepoint():
                created.unlink()
                if payload.get('removed'):
                    Shift.create([{k: v for k, v in vals.items() if k in Shift._fields}
                                  for vals in payload['removed']])
                self.env.flush_all()
        except (UserError, ValidationError):
            raise UserError(self._changed_sentence())

    # ============================================================ late rule
    @api.model
    def _single_policy(self):
        """The company's one non-retired late-rule set, or nothing when there
        is none or more than one (then nobody is pointed at one here)."""
        if 'pb.attendance.policy' not in self.env:
            return self.env['res.company'].browse()
        policies = self.env['pb.attendance.policy'].sudo().search(
            [('company_id', '=', self.env.company.id), ('state', '!=', 'retired')])
        return policies if len(policies) == 1 else policies.browse()

    @api.model
    def _band_lines(self, policy):
        out = {g: [] for g in GROUPS}
        if not policy:
            return out
        for band in policy.band_ids.sorted(lambda b: (b.category, b.minimum)):
            if band.category not in out:
                continue
            lo = int(band.minimum or 0)
            if band.open_ended or not band.maximum:
                span = _("%s min or more", lo)
            elif lo == 0:
                span = _("under %s min", int(band.maximum))
            else:
                hi = int(band.maximum)
                span = _("%(a)s to %(b)s min", a=lo, b=hi - 1) if hi - 1 > lo else _("%s min", lo)
            off = (_("nothing off") if not band.hours
                   else _("%s h off", ('%g' % band.hours)))
            out[band.category].append('%s: %s' % (span, off))
        return out

    @api.model
    def _late_plan(self, employee_ids, group):
        if group not in GROUPS:
            raise UserError(_("Pick Worker or Manager."))
        emps = self._ticked(employee_ids)
        changed = emps.filtered(lambda e: e.pb_attendance_category != group)
        policy = self._single_policy()
        fill = emps.filtered(lambda e: not e.pb_attendance_policy_id) if policy else emps.browse()
        return {'emps': emps, 'group': group, 'changed': changed, 'fill': fill, 'policy': policy}

    @api.model
    def set_late_rule_preview(self, employee_ids, group):
        self._gate_edit()
        lines = self._band_lines(self._single_policy())
        try:
            plan = self._late_plan(employee_ids, group)
        except UserError as e:
            return {'changed': 0, 'unchanged': 0, 'policy_set': 0, 'lines': lines,
                    'problems': [e.args[0] if e.args else str(e)]}
        return {'changed': len(plan['changed']), 'unchanged': len(plan['emps']) - len(plan['changed']),
                'policy_set': len(plan['fill']), 'lines': lines,
                'problems': self._gone_problem(employee_ids, plan['emps'])}

    @api.model
    def set_late_rule(self, employee_ids, group):
        self._gate_edit()
        plan = self._late_plan(employee_ids, group)
        touched = plan['changed'] | plan['fill']
        label = _("Manager") if group == 'manager' else _("Worker")
        n = len(plan['changed'])
        if not touched:
            return {'changed': 0, 'unchanged': len(plan['emps']), 'policy_set': 0,
                    'undo_id': False, 'summary': _("Nothing changed.")}
        rows = [{'id': e.id, 'cat': e.pb_attendance_category or False,
                 'pol': e.pb_attendance_policy_id.id or False} for e in touched]
        ctx = {'tracking_disable': True, 'mail_notrack': True}
        # sudo: the field is HR-officer-only (facts K24); the edit gate ran above
        if plan['changed']:
            plan['changed'].sudo().with_context(**ctx).write({'pb_attendance_category': group})
        if plan['fill']:
            plan['fill'].sudo().with_context(**ctx).write({'pb_attendance_policy_id': plan['policy'].id})
        for row, emp in zip(rows, touched):
            row['new_cat'] = emp.pb_attendance_category or False
            row['new_pol'] = emp.pb_attendance_policy_id.id or False
        summary = (_("1 person set to the %s late rule.", label) if n == 1
                   else _("%(n)s people set to the %(rule)s late rule.", n=n, rule=label)) if n \
            else _("The late rules are now linked for %s people.", len(plan['fill']))
        undo = self.env['pb.workforce.setup.undo'].create({
            'kind': 'late', 'summary': summary, 'payload': {'rows': rows}})
        return {'changed': n, 'unchanged': len(plan['emps']) - n, 'policy_set': len(plan['fill']),
                'undo_id': undo.id, 'summary': summary}

    @api.model
    def _undo_late(self, payload):
        rows = payload.get('rows', [])
        emps = self.env['hr.employee'].sudo().with_context(active_test=False).browse(
            [r['id'] for r in rows]).exists()
        if len(emps) != len(rows):
            raise UserError(self._changed_sentence())
        by_id = {e.id: e for e in emps}
        for r in rows:
            e = by_id[r['id']]
            if (e.pb_attendance_category or False) != r['new_cat'] \
                    or (e.pb_attendance_policy_id.id or False) != r['new_pol']:
                raise UserError(self._changed_sentence())
        groups = {}
        for r in rows:
            groups.setdefault((r['cat'], r['pol']), []).append(r['id'])
        ctx = {'tracking_disable': True, 'mail_notrack': True}
        for (cat, pol), ids in groups.items():
            self.env['hr.employee'].sudo().with_context(**ctx).browse(ids).write(
                {'pb_attendance_category': cat or False, 'pb_attendance_policy_id': pol or False})

    # ============================================================ undo
    @api.model
    def undo(self, undo_id):
        """Put back exactly what one bulk action changed, or refuse whole."""
        self._gate_edit()
        row = self.env['pb.workforce.setup.undo'].sudo().search([
            ('id', '=', self._int(undo_id, 0)), ('user_id', '=', self.env.uid),
            ('company_id', '=', self.env.company.id)], limit=1)
        if not row:
            raise UserError(_("This change can no longer be undone."))
        payload = row.payload or {}
        handler = {'assign': self._undo_assign, 'oneoff': self._undo_oneoff,
                   'late': self._undo_late}[row.kind]
        handler(payload)
        kind = row.kind
        row.unlink()
        return {'undone': True, 'summary': {
            'assign': _("Undone. Their working weeks are back as they were."),
            'oneoff': _("Undone. The one-off shifts are gone and the planned ones are back."),
            'late': _("Undone. Their late rules are back as they were."),
        }[kind]}
