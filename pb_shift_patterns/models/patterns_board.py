# Part of Payobook. See LICENSE file for full copyright and licensing details.
"""`pb.shift.patterns` — the facade of the Patterns lens (Mission Control).

Cockpit pattern: one AbstractModel, every method gated on the server
(`_require_reader` = the Schedule's officer gate, `_require_maker` = the
attendance managers who may create shifts at all). The JS `groups` on the
lens are a hint only.

Reads of people, templates and departments go through sudo BEHIND the gate
(C18.73): an attendance officer need not hold HR rights on employees to see
who is on a rota, exactly as the roster reads names today.
"""

import logging
from datetime import timedelta

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError
from odoo.fields import Domain
from odoo.tools.misc import format_date

from .shift_pattern import MAX_CYCLE_DAYS, MAX_TEAMS, TEAM_LETTERS
from .pattern_engine import MAX_WEEKS

_logger = logging.getLogger(__name__)

PAGE_SIZE = 40

USE_DOMAINS = {
    'people': [('member_ids', '!=', False)],
    'nobody': [('member_ids', '=', False)],
}


class ShiftPatternsBoard(models.AbstractModel):
    _name = 'pb.shift.patterns'
    _inherit = ['pb.filter.mixin']
    _description = 'Rotating shift patterns board'

    # ------------------------------------------------------------ gates
    @api.model
    def _can_read(self):
        u = self.env.user
        return bool(u.has_group('hr_attendance.group_hr_attendance_officer')
                    or u.has_group('base.group_system'))

    @api.model
    def _refusal(self):
        return _("Shift patterns are for the people who plan the schedule. Ask "
                 "your administrator for the attendance officer role.")

    @api.model
    def _require_reader(self):
        if not self._can_read():
            raise AccessError(self._refusal())

    @api.model
    def _engine(self):
        return self.env['pb.shift.pattern.engine']

    @api.model
    def _require_maker(self):
        self._require_reader()
        self._engine()._require_maker()

    @api.model
    def _scope(self):
        return [('company_id', 'in', self.env.companies.ids)]

    @api.model
    def _pattern(self, pattern_id, active_test=True):
        """A search, not a browse: another company's pattern reads 'not there'."""
        try:
            pid = int(pattern_id or 0)
        except (TypeError, ValueError):
            pid = 0
        rec = self.env['pb.shift.pattern'].with_context(active_test=active_test).search(
            self._scope() + [('id', '=', pid)], limit=1)
        if not rec:
            raise UserError(_("This pattern is no longer there."))
        return rec

    @api.model
    def _patterns(self, pattern_ids):
        ids = []
        for pid in pattern_ids or []:
            try:
                ids.append(int(pid))
            except (TypeError, ValueError):
                continue
        recs = self.env['pb.shift.pattern'].search(self._scope() + [('id', 'in', ids)])
        if not recs:
            raise UserError(_("Choose at least one pattern."))
        return recs

    # ------------------------------------------------------------ words
    @api.model
    def _d(self, day, fmt='EEE d MMM'):
        return format_date(self.env, day, date_format=fmt) if day else ''

    @api.model
    def _cycle_label(self, days):
        days = int(days or 0)
        if days and days % 7 == 0:
            weeks = days // 7
            return _("Repeats every week") if weeks == 1 else \
                _("Repeats every %s weeks", weeks)
        return _("Repeats every day") if days == 1 else _("Repeats every %s days", days)

    @api.model
    def _templates(self):
        Grid = self.env['hr.shift.planning.grid']
        rows = self.env['hr.shift.template'].sudo().search([
            '|', ('company_id', '=', False), ('company_id', 'in', self.env.companies.ids)])
        return [{
            'id': t.id, 'name': t.name or '', 'code': t.code or '',
            'color': t.color or 0, 'shift_type': t.shift_type or '',
            'start': Grid._pb_float_hhmm(t.start_hour),
            'end': Grid._pb_float_hhmm(t.end_hour),
            'hours': round(t.duration or 0.0, 2),
            'is_overnight': bool(t.is_overnight),
            'company_id': t.company_id.id or False,
        } for t in rows]

    # ============================================================ the board
    @api.model
    def get_board(self):
        if not self._can_read():
            return {'allowed': False, 'why': self._refusal()}
        P = self.env['pb.shift.pattern']
        scope = self._scope()
        today = fields.Date.context_today(self)
        this_monday = today - timedelta(days=today.weekday())
        patterns = P.search(scope)
        people = len(patterns.sudo().member_ids.mapped('employee_id'))
        drafts = self.env['hr.shift.planning'].sudo().search_count([
            ('pb_pattern_id', 'in', patterns.ids), ('state', '=', 'draft'),
            ('date', '>=', today)])
        nobody = len(patterns.filtered(lambda p: not p.member_ids))
        no_cycle = len(patterns.filtered(lambda p: not p.slot_ids.filtered('template_id')))
        archived = P.with_context(active_test=False).search(scope + [('active', '=', False)])
        depts = self.env['hr.department'].sudo().search(
            [('company_id', 'in', self.env.companies.ids + [False])], order='name')
        return {
            'allowed': True, 'why': '',
            'can_edit': self._engine()._pb_can_make(),
            'kpis': {'patterns': len(patterns), 'people': people, 'drafts': drafts,
                     'nobody': nobody, 'no_cycle': no_cycle},
            'total': len(patterns),
            'templates': self._templates(),
            'departments': [{'id': d.id, 'name': d.display_name or d.name or ''} for d in depts],
            'company_id': self.env.company.id,
            'today': today.isoformat(),
            'this_monday': this_monday.isoformat(),
            'max_weeks': MAX_WEEKS, 'max_cycle': MAX_CYCLE_DAYS, 'max_teams': MAX_TEAMS,
            'archived': [{'id': a.id, 'name': a.name or ''} for a in archived],
        }

    # ------------------------------------------------------------ filter panel
    def _pbf_model(self):
        return 'pb.shift.pattern'

    def _pbf_screen(self):
        return 'shift_patterns'

    def _pbf_base_domain(self):
        return list(self._scope())

    def _pbf_search_domain(self, search):
        q = (search or '').strip()
        if not q:
            return None
        return Domain.OR([Domain('name', 'ilike', q),
                          Domain('department_id.name', 'ilike', q),
                          Domain('member_ids.employee_id.name', 'ilike', q)])

    def _pbf_sorts(self):
        return [
            {'key': 'name', 'label': _('Name, A to Z'), 'order': 'name, id'},
            {'key': 'new', 'label': _('Newest first'), 'order': 'create_date desc, id desc'},
            {'key': 'fill', 'label': _('Filled least far ahead'),
             'order': 'last_made_to asc nulls first, id'},
        ]

    def _pbf_spec(self):
        return [
            {'key': 'use', 'label': _('People'), 'icon': 'users', 'group': 'other',
             'type': 'choice', 'pinned': True, 'requires': ['member_ids'],
             'options': [
                 {'value': 'people', 'label': _('Has people'), 'tone': 'green',
                  'domain': USE_DOMAINS['people']},
                 {'value': 'nobody', 'label': _('Nobody yet'), 'tone': 'amber',
                  'domain': USE_DOMAINS['nobody']},
             ]},
            {'key': 'department', 'label': _('Department'), 'icon': 'building',
             'group': 'other', 'type': 'many2one', 'path': 'department_id',
             'pinned': True, 'label_sudo': True},
            {'key': 'who', 'label': _('Made by'), 'icon': 'user', 'group': 'other',
             'type': 'many2one', 'path': 'create_uid', 'label_sudo': True},
        ]

    def _pbf_builtin_views(self):
        return [
            {'key': 'all', 'label': _('All patterns'), 'icon': 'repeat', 'filters': {}},
            {'key': 'people', 'label': _('In use'), 'filters': {'use': ['people']}},
            {'key': 'nobody', 'label': _('Nobody yet'), 'filters': {'use': ['nobody']}},
        ]

    @api.model
    def pbf_layout(self, **kw):
        if not self._can_read():
            return {'refused': self._refusal()}
        return super().pbf_layout(**kw)

    @api.model
    def get_page(self, filters=None, search=None, sort=None, offset=0, limit=PAGE_SIZE):
        if not self._can_read():
            return {'rows': [], 'total': 0, 'offset': 0}
        P = self.env['pb.shift.pattern']
        try:
            offset = max(0, int(offset or 0))
            limit = max(1, min(int(limit or PAGE_SIZE), 200))
        except (TypeError, ValueError):
            offset, limit = 0, PAGE_SIZE
        filters = filters if isinstance(filters, dict) else {}
        domain = self.pbf_domain(filters, search)
        order = self.pbf_order(sort) or 'name, id'
        rows = []
        tmap = {t['id']: t for t in self._templates()}
        for rec in P.search(domain, order=order, offset=offset, limit=limit):
            try:
                rows.append(self._row(rec, tmap))
            except Exception as e:      # noqa: BLE001 — one bad row never blanks it
                _logger.info('pattern row %s failed: %s', rec.id, e)
        return {'rows': rows, 'total': P.search_count(domain), 'offset': offset}

    @api.model
    def _strip(self, rec, tmap):
        """Team A's cycle as cells — the row's picture of the rota."""
        slots = {s.day_index: s.template_id.id for s in rec.sudo().slot_ids if s.template_id}
        out = []
        for i in range(min(rec.cycle_days or 0, MAX_CYCLE_DAYS)):
            t = tmap.get(slots.get(i))
            out.append({'i': i, 'off': not t, 'code': (t or {}).get('code', ''),
                        'color': (t or {}).get('color', 0),
                        'name': (t or {}).get('name', '')})
        return out

    @api.model
    def _row(self, rec, tmap):
        today = fields.Date.context_today(self)
        sudo = rec.sudo()
        drafts = self.env['hr.shift.planning'].sudo().search_count([
            ('pb_pattern_id', '=', rec.id), ('state', '=', 'draft'), ('date', '>=', today)])
        people = len(sudo.member_ids.mapped('employee_id'))
        working = len(sudo.slot_ids.filtered('template_id'))
        need = ''
        if not working:
            need = 'cycle'
        elif not people:
            need = 'people'
        return {
            'id': rec.id, 'name': rec.name or '',
            'department': sudo.department_id.name or '',
            'cycle_days': rec.cycle_days,
            'cycle_label': self._cycle_label(rec.cycle_days),
            'teams': len(sudo.team_ids),
            'people': people,
            'working_days': working,
            'drafts': drafts,
            'made_to': rec.last_made_to.isoformat() if rec.last_made_to else '',
            'made_to_label': self._d(rec.last_made_to),
            'start_label': self._d(rec.start_date, 'd MMM y'),
            'strip': self._strip(rec, tmap),
            'need': need,
        }

    # ============================================================ one pattern
    @api.model
    def get_pattern(self, pattern_id):
        self._require_reader()
        rec = self._pattern(pattern_id)
        sudo = rec.sudo()
        others = self._other_patterns(sudo.member_ids.mapped('employee_id').ids, rec.id)
        today = fields.Date.context_today(self)
        Shift = self.env['hr.shift.planning'].sudo()
        return {
            'id': rec.id,
            'name': rec.name or '',
            'department_id': sudo.department_id.id or False,
            'company_id': rec.company_id.id,
            'start_date': rec.start_date.isoformat() if rec.start_date else '',
            'cycle_days': rec.cycle_days,
            'work_on_holidays': rec.work_on_holidays,
            'note': rec.note or '',
            'slots': [{'day': s.day_index, 'template_id': s.template_id.id or False}
                      for s in sudo.slot_ids],
            'teams': [{'key': 't%s' % t.id, 'name': t.name or '',
                       'offset': t.offset_days or 0} for t in sudo.team_ids],
            'members': [self._member(m, others) for m in sudo.member_ids],
            'drafts': Shift.search_count([('pb_pattern_id', '=', rec.id),
                                          ('state', '=', 'draft'), ('date', '>=', today)]),
            'published': Shift.search_count([('pb_pattern_id', '=', rec.id),
                                             ('state', '=', 'published'),
                                             ('date', '>=', today)]),
            'made_to': rec.last_made_to.isoformat() if rec.last_made_to else '',
            'made_to_label': self._d(rec.last_made_to),
            'made_by': sudo.last_made_by.name or '',
        }

    @api.model
    def _other_patterns(self, employee_ids, pattern_id=0):
        """{employee_id: [names of OTHER patterns they are on]}"""
        out = {}
        if not employee_ids:
            return out
        rows = self.env['pb.shift.pattern.member'].sudo().search([
            ('employee_id', 'in', list(employee_ids)),
            ('pattern_id', '!=', int(pattern_id or 0)),
            ('pattern_id.active', '=', True),
            ('company_id', 'in', self.env.companies.ids),
        ])
        for m in rows:
            names = out.setdefault(m.employee_id.id, [])
            if m.pattern_id.name not in names:
                names.append(m.pattern_id.name)
        return out

    @api.model
    def _person(self, emp):
        return {
            'employee_id': emp.id,
            'name': emp.name or '',
            'job': emp.job_title or emp.job_id.name or '',
            'department': emp.department_id.name or '',
            'avatar': '/web/image/hr.employee/%s/avatar_128' % emp.id,
        }

    @api.model
    def _member(self, m, others):
        row = self._person(m.employee_id)
        row.update({
            'team_key': 't%s' % m.team_id.id,
            'date_from': m.date_from.isoformat() if m.date_from else '',
            'date_to': m.date_to.isoformat() if m.date_to else '',
            'also_on': others.get(m.employee_id.id, []),
        })
        return row

    @api.model
    def find_people(self, query='', limit=20):
        """People to add, in the companies the reader works in."""
        self._require_reader()
        q = (query or '').strip()
        domain = [('active', '=', True), ('company_id', 'in', self.env.companies.ids)]
        if q:
            domain += ['|', ('name', 'ilike', q), ('job_title', 'ilike', q)]
        try:
            limit = max(1, min(int(limit or 20), 50))
        except (TypeError, ValueError):
            limit = 20
        emps = self.env['hr.employee'].sudo().search(domain, order='name', limit=limit)
        others = self._other_patterns(emps.ids)
        out = []
        for e in emps:
            row = self._person(e)
            row['also_on'] = others.get(e.id, [])
            out.append(row)
        return out

    # ============================================================ save
    @api.model
    def _int(self, value, default=0):
        try:
            return int(value)
        except (TypeError, ValueError):
            return default

    @api.model
    def _date(self, value):
        if not value:
            return False
        try:
            return fields.Date.to_date(value)
        except (TypeError, ValueError):
            raise UserError(_("%s is not a date.", value))

    @api.model
    def save_pattern(self, vals, pattern_id=False):
        """Create or replace one pattern with its cycle, teams and people.

        The cycle, teams and people are replaced whole: nothing outside the
        pattern points at a slot, a team or a member row (made shifts point at
        the PATTERN), so replacing them loses nothing.
        """
        self._require_maker()
        vals = vals if isinstance(vals, dict) else {}
        name = (vals.get('name') or '').strip()
        if not name:
            raise UserError(_("Give the pattern a name."))
        cycle = self._int(vals.get('cycle_days'), 0)
        if not 1 <= cycle <= MAX_CYCLE_DAYS:
            raise UserError(_("A pattern repeats every 1 to %s days.", MAX_CYCLE_DAYS))
        start = self._date(vals.get('start_date'))
        if not start:
            raise UserError(_("Choose day 1 of the cycle."))

        if pattern_id:
            rec = self._pattern(pattern_id)
            company = rec.company_id
        else:
            rec = self.env['pb.shift.pattern']
            company = self.env.company

        dept_id = self._int(vals.get('department_id'), 0) or False
        if dept_id:
            dept = self.env['hr.department'].sudo().browse(dept_id).exists()
            if not dept or (dept.company_id and dept.company_id != company):
                raise UserError(_("That department is not in this company."))

        # ---- the cycle
        allowed_tmpl = self.env['hr.shift.template'].sudo().search([
            '|', ('company_id', '=', False), ('company_id', '=', company.id)])
        slot_cmds = [(5, 0, 0)]
        seen_days = set()
        for s in vals.get('slots') or []:
            day = self._int(s.get('day'), -1)
            tid = self._int(s.get('template_id'), 0)
            if not tid or day in seen_days:
                continue
            if not 0 <= day < cycle:
                continue                    # a shrunk cycle drops its tail
            if tid not in allowed_tmpl.ids:
                raise UserError(_("A shift in the cycle is not available in this company."))
            seen_days.add(day)
            slot_cmds.append((0, 0, {'day_index': day, 'template_id': tid}))

        # ---- the teams
        teams = []
        keys = set()
        for i, t in enumerate(vals.get('teams') or []):
            key = str(t.get('key') or 'k%s' % i)
            if key in keys:
                continue
            keys.add(key)
            offset = self._int(t.get('offset'), 0)
            if not 0 <= offset < cycle:
                raise UserError(_("A team must start 0 to %s days after Team A.", cycle - 1))
            teams.append({'key': key, 'sequence': (i + 1) * 10, 'offset_days': offset,
                          'name': (t.get('name') or '').strip()
                          or _("Team %s", TEAM_LETTERS[i % len(TEAM_LETTERS)])})
        if not teams:
            raise UserError(_("A pattern needs at least one team."))
        if len(teams) > MAX_TEAMS:
            raise UserError(_("A pattern has at most %s teams.", MAX_TEAMS))

        # ---- the people
        members = []
        emp_ids = [self._int(m.get('employee_id'), 0) for m in vals.get('members') or []]
        emps = self.env['hr.employee'].sudo().browse([e for e in emp_ids if e]).exists()
        ok_emp = {e.id for e in emps if e.company_id == company}
        for m in vals.get('members') or []:
            eid = self._int(m.get('employee_id'), 0)
            if not eid:
                continue
            if eid not in ok_emp:
                raise UserError(_("Somebody on the list is not in this company."))
            key = str(m.get('team_key') or '')
            if key not in keys:
                key = teams[0]['key']
            members.append({'employee_id': eid, 'key': key,
                            'date_from': self._date(m.get('date_from')),
                            'date_to': self._date(m.get('date_to'))})

        basics = {
            'name': name, 'department_id': dept_id, 'start_date': start,
            'cycle_days': cycle, 'work_on_holidays': bool(vals.get('work_on_holidays')),
            'note': (vals.get('note') or '').strip() or False,
        }
        if rec:
            rec.team_ids.unlink()           # members go with their team
            rec.write(dict(basics, slot_ids=slot_cmds))
        else:
            rec = rec.create(dict(basics, company_id=company.id, slot_ids=slot_cmds[1:]))
        Team = self.env['pb.shift.pattern.team']
        by_key = {}
        for t in teams:
            by_key[t['key']] = Team.create({'pattern_id': rec.id, 'name': t['name'],
                                            'sequence': t['sequence'],
                                            'offset_days': t['offset_days']})
        if members:
            self.env['pb.shift.pattern.member'].create([{
                'pattern_id': rec.id, 'team_id': by_key[m['key']].id,
                'employee_id': m['employee_id'],
                'date_from': m['date_from'], 'date_to': m['date_to'],
            } for m in members])
        rec._check_cycle()
        return {'id': rec.id}

    @api.model
    def archive_pattern(self, pattern_id, archive=True):
        self._require_maker()
        rec = self._pattern(pattern_id, active_test=False)
        rec.active = not archive
        return True

    # ============================================================ make drafts
    @api.model
    def preview(self, pattern_ids, start, weeks):
        """What "Make drafts" would do. Writes nothing."""
        self._require_maker()
        Eng = self._engine()
        first, last = Eng._pb_range(start, weeks)
        report = Eng._pb_report(Eng.plan(self._patterns(pattern_ids), first, last))
        report.update(self._range_words(first, last))
        return report

    @api.model
    def make_drafts(self, pattern_ids, start, weeks):
        self._require_maker()
        Eng = self._engine()
        first, last = Eng._pb_range(start, weeks)
        report = Eng.apply(self._patterns(pattern_ids), first, last)
        report.update(self._range_words(first, last))
        return report

    @api.model
    def clear_drafts(self, pattern_id):
        self._require_maker()
        return self._engine().clear_drafts(self._pattern(pattern_id, active_test=False))

    @api.model
    def _range_words(self, first, last):
        return {'first_label': self._d(first, 'EEE d MMM y'),
                'last_label': self._d(last, 'EEE d MMM y')}
