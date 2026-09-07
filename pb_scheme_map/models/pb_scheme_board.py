# -*- coding: utf-8 -*-
"""`pb.scheme.board` — the only server surface the "Who is paid by what" screen talks to.

The shape is the one `pb_assets`, `pb.decision.room` and `pb.group.room`
established: an `AbstractModel` facade, `@api.model` reads, every independent
figure inside its own `_safe()` so one failing number answers zero instead of
taking the board down, a row cap on anything a caller controls, and a
SERVER-SIDE gate that is the boundary. A reader with no permission gets an
empty, EXPLAINED board rather than an access dialog.

ONE COMPANY AT A TIME, AND THAT IS THE POINT (ledger gotcha GR3)
----------------------------------------------------------------
The canvas this replaces searched departments and schemes with no company
domain at all. On a single-company database nobody could tell; on a group it
offers you Vietnam's departments beside Singapore's schemes and lets you wire
one to the other, which produces a payslip in the wrong legal entity. So the
board is scoped to ONE company — the active one by default — and says which,
with a switcher when the reader is allowed more than one.

WHY THE COUNTS RUN UNDER `sudo()` (WFPLAN WF10, restated)
---------------------------------------------------------
Drawing the map is a payroll administrator's job. The counts are AGGREGATES —
how many people a scheme covers, how many nobody covers — and the exceptions
list is names and teams, nothing else: no wage, no payslip, no personal data
beyond what a department list already shows. The gate above decides who may
look; the queries below then read the roster without needing every payroll
administrator to also hold an HR permission.
"""

import logging
import time

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError

from .formula_scheme_assignment import CYCLE_SELECTION, CYCLE_WORDS

_logger = logging.getLogger(__name__)

READ_GROUPS = (
    'pb_hr_payroll_formula.group_formula_user',
    'om_hr_payroll.group_hr_payroll_user',
    'hr.group_hr_user',
)
WRITE_GROUPS = (
    'pb_hr_payroll_formula.group_formula_manager',
    'om_hr_payroll.group_hr_payroll_manager',
)

MAX_COMPANIES = 60
MAX_SEGMENTS = 400
MAX_SCHEMES = 120
MAX_NAMED = 200


class PbSchemeBoard(models.AbstractModel):
    _name = 'pb.scheme.board'
    _description = 'Who is paid by what — screen data'

    # ================================================================== gates
    @api.model
    def _safe(self, fn, default=0):
        try:
            return fn()
        except Exception as e:      # noqa: BLE001
            _logger.debug('Scheme map figure failed: %s', e)
            return default

    @api.model
    def _can_read(self):
        user = self.env.user
        if user._is_admin():
            return True
        for name in READ_GROUPS:
            if self._safe(lambda n=name: user.has_group(n), default=False):
                return True
        return False

    @api.model
    def _can_write(self):
        user = self.env.user
        if user._is_admin():
            return True
        for name in WRITE_GROUPS:
            if self._safe(lambda n=name: user.has_group(n), default=False):
                return True
        return False

    @api.model
    def _require_write(self):
        if not self._can_write():
            raise AccessError(_(
                "You can look at the map, but changing which scheme pays whom "
                "is for a payroll manager. Ask one of them to make the "
                "change."))
        return True

    # ================================================================ scoping
    @api.model
    def _pick_company(self, company_id=None):
        """The company this board is about — always exactly one."""
        allowed = self.env.companies.ids or [self.env.company.id]
        wanted = int(company_id or 0)
        if wanted and wanted in allowed:
            return wanted
        return self.env.company.id if self.env.company.id in allowed \
            else allowed[0]

    @api.model
    def _companies(self):
        rows = self.env['res.company'].sudo().browse(
            (self.env.companies.ids or [self.env.company.id])[:MAX_COMPANIES])
        return [{'id': c.id, 'name': c.name} for c in rows.exists()]

    # ================================================================== read
    @api.model
    def get_board(self, company_id=None, cycle_type='any'):
        started = time.time()
        if not self._can_read():
            return {
                'allowed': False, 'can_edit': False, 'company_id': 0,
                'company': '', 'companies': [], 'cycles': self._cycles(),
                'cycle_type': 'any', 'segments': [], 'schemes': [],
                'wires': [], 'exceptions': {'total': 0, 'people': []},
                'covered': 0, 'people': 0, 'stale': 0, 'ms': 0,
            }
        company_id = self._pick_company(company_id)
        cycle_type = cycle_type if cycle_type in dict(CYCLE_SELECTION) \
            else 'any'
        Map = self.env['pb.scheme.map'].sudo()

        schemes = self._schemes(company_id)
        rows = self._safe(
            lambda: Map._map_rows([company_id]).filtered(
                lambda r: r.company_id.id in (False, company_id)
                or not r.company_id),
            default=self.env['hr.formula.scheme.assignment'])
        blank = {'covered': 0, 'people': 0, 'not_covered_total': 0,
                 'not_covered': [], 'by_config': {}, 'by_department': {}}
        cover = self._safe(
            lambda: Map.coverage(company_id, cycle_type, MAX_NAMED),
            default=blank)

        # A SCHEME'S OWN KIND OF RUN DECIDES ITS COUNT. Asked "who pays this
        # person", the answer is the main run, so every mid-month advance
        # scheme would read "nobody yet" over a map that covers all of them.
        # One resolution per kind of run the company actually has — two on the
        # demo company, and it is the difference between a truthful board and a
        # board that says the advances are unmapped.
        kinds = {s['cycle_type'] for s in schemes if s['cycle_type']}
        per_kind = {}
        for kind in kinds:
            answer = self._safe(
                lambda k=kind: Map.coverage(company_id, k, 0), default=blank)
            per_kind[kind] = {int(k): v
                              for k, v in (answer.get('by_config') or {}).items()}
        fallback = {int(k): v for k, v in (cover.get('by_config') or {}).items()}
        for scheme in schemes:
            scheme['covered'] = per_kind.get(
                scheme['cycle_type'], fallback).get(scheme['id'], 0)

        missing = {int(k): v
                   for k, v in (cover.get('by_department') or {}).items()}
        segments = self._safe(lambda: self._segments(company_id, missing),
                              default=[])

        stale = self._safe(
            lambda: self.env['hr.employee'].sudo().search_count(
                [('company_id', '=', company_id),
                 ('pb_paid_by_stale', '=', True)]), default=0)

        return {
            'allowed': True,
            'can_edit': self._can_write(),
            'company_id': company_id,
            'company': self.env['res.company'].sudo().browse(company_id).name,
            'companies': self._companies(),
            'cycles': self._cycles(),
            'cycle_type': cycle_type,
            'segments': segments,
            'schemes': schemes,
            'wires': self._wires(rows, company_id),
            'exceptions': {
                'total': cover.get('not_covered_total', 0),
                'people': cover.get('not_covered', []),
            },
            'covered': cover.get('covered', 0),
            'people': cover.get('people', 0),
            'stale': stale,
            'studio_action': 'pb_formula_studio.action_pb_formula_studio',
            'ms': int((time.time() - started) * 1000),
        }

    @api.model
    def _cycles(self):
        return [{'value': value, 'label': label,
                 'words': _(CYCLE_WORDS.get(value, ''))}
                for value, label in CYCLE_SELECTION]

    @api.model
    def _schemes(self, company_id):
        """The company's live schemes, grouped in the caller by kind of run.

        Every ACTIVE scheme, mid-month advances included — the canvas this
        replaces filtered them out (`cycle_type != 'mid_cycle'`), which is why
        a division's advance scheme could never be attached to anything and
        every advance run resolved down the old ladder to whatever it found.
        """
        Config = self.env['hr.formula.config'].sudo()
        configs = Config.search(
            ['|', ('company_id', '=', False), ('company_id', '=', company_id),
             ('state', '=', 'active')], order='cycle_type, name',
            limit=MAX_SCHEMES)
        last = self._last_runs(configs.ids)
        return [{
            'id': c.id,
            'name': c.name or '',
            'code': c.code or '',
            'cycle_type': c.cycle_type or 'regular',
            'cycle_label': _(CYCLE_WORDS.get(c.cycle_type or 'regular', '')),
            'shared': not c.company_id,
            'covered': 0,
            'last_run': last.get(c.id) or {},
        } for c in configs]

    @api.model
    def _last_runs(self, config_ids):
        """The most recent run each scheme actually produced payslips in."""
        if not config_ids:
            return {}
        self.env.cr.execute("""
            SELECT DISTINCT ON (s.formula_config_id)
                   s.formula_config_id, r.id, r.name, r.date_end,
                   (SELECT COUNT(*) FROM hr_payslip x
                     WHERE x.payslip_run_id = r.id
                       AND x.formula_config_id = s.formula_config_id)
              FROM hr_payslip s
              JOIN hr_payslip_run r ON r.id = s.payslip_run_id
             WHERE s.formula_config_id = ANY(%s)
             ORDER BY s.formula_config_id, r.date_end DESC NULLS LAST, r.id DESC
        """, ([int(c) for c in config_ids],))
        out = {}
        for config_id, _run_id, name, date_end, people in self.env.cr.fetchall():
            out[config_id] = {
                'name': name or '',
                'date_end': fields.Date.to_string(date_end) if date_end else '',
                'people': people or 0,
            }
        return out

    @api.model
    def _segments(self, company_id, missing=None):
        """The left column: divisions first, then this company's top teams.

        A division is offered whenever it has a department in this company —
        attaching a scheme to it is how one line covers the same business in
        every company at once. Teams are the top of each branch, with their
        children reachable behind them, because an attachment at the top
        covers the branch and a board of forty rows teaches nobody anything.
        """
        Map = self.env['pb.scheme.map'].sudo()
        Department = self.env['hr.department'].sudo()
        heads = self._safe(
            lambda: self.env['pb.division'].sudo()._heads_by_department(
                [company_id]), default={})
        chains, meta = Map._chains([company_id])
        rolled = {}
        for dept_id, count in heads.items():
            for candidate in (chains.get(dept_id) or [dept_id]):
                rolled[candidate] = rolled.get(candidate, 0) + count
        # The same roll-up for the people nobody pays, so each row can say
        # "all covered" or "12 not covered" instead of a bare "No scheme" over
        # a team whose people ARE covered from the team above them.
        missing = missing or {}
        unmapped = {}
        for dept_id, count in missing.items():
            for candidate in (chains.get(dept_id) or [dept_id]):
                unmapped[candidate] = unmapped.get(candidate, 0) + count

        out = []
        if 'pb.division' in self.env:
            links = self.env['pb.division.link'].sudo().search(
                [('company_id', '=', company_id), ('active', '=', True)])
            for division in links.mapped('division_id'):
                mine = [link.department_id.id for link in links
                        if link.division_id == division]
                out.append({
                    'key': 'division-%s' % division.id,
                    'kind': 'division',
                    'id': division.id,
                    'label': division.name or '',
                    'sublabel': _("Division"),
                    'people': sum(rolled.get(d, 0) for d in mine),
                    'missing': sum(unmapped.get(d, 0) for d in mine),
                    'children': [],
                })

        tops = Department.search(
            [('company_id', '=', company_id), ('parent_id', '=', False)],
            limit=MAX_SEGMENTS)
        for dept in tops:
            children = Department.search(
                [('id', 'child_of', dept.id), ('id', '!=', dept.id)],
                limit=MAX_SEGMENTS)
            out.append({
                'key': 'department-%s' % dept.id,
                'kind': 'department',
                'id': dept.id,
                'label': dept.name or '',
                'sublabel': _("Team"),
                'people': rolled.get(dept.id, 0),
                'missing': unmapped.get(dept.id, 0),
                'children': [{
                    'key': 'department-%s' % child.id,
                    'kind': 'department',
                    'id': child.id,
                    'label': child.complete_name or child.name or '',
                    'people': rolled.get(child.id, 0),
                    'missing': unmapped.get(child.id, 0),
                } for child in children],
            })
        out.sort(key=lambda s: (s['kind'] != 'division', -s['people'],
                                s['label']))
        return out[:MAX_SEGMENTS]

    @api.model
    def _wires(self, rows, company_id):
        out = []
        for row in rows:
            if row.department_id:
                key, label = ('department-%s' % row.department_id.id,
                              row.department_id.complete_name
                              or row.department_id.name or '')
                if row.department_id.company_id.id != company_id:
                    continue
            elif row.division_id:
                key, label = ('division-%s' % row.division_id.id,
                              row.division_id.name or '')
            else:
                continue
            out.append({
                'id': row.id,
                'segment': key,
                'segment_label': label,
                'config_id': row.config_id.id,
                'config': row.config_id.name or '',
                'cycle_type': row.cycle_type or 'any',
                'cycle_label': _(CYCLE_WORDS.get(row.cycle_type or 'any', '')),
                'source': row.source or 'manual',
                'confidence': row.confidence or 0.0,
                'note': row.note or '',
            })
        return out

    # ================================================================= writes
    @api.model
    def _split(self, segment):
        kind, _sep, raw = (segment or '').partition('-')
        return kind, int(raw or 0)

    @api.model
    def attach(self, segment, config_id, cycle_type='any', company_id=None):
        """Wire a team or a division to a scheme, for one kind of run."""
        self._require_write()
        kind, segment_id = self._split(segment)
        config = self.env['hr.formula.config'].sudo().browse(
            int(config_id or 0)).exists()
        if not config or kind not in ('department', 'division') \
                or not segment_id:
            raise UserError(_(
                "That attachment did not name a team and a scheme this screen "
                "can see. Reload the screen and try again."))
        company_id = self._pick_company(company_id or config.company_id.id)
        if config.company_id and config.company_id.id != company_id:
            raise UserError(_(
                "%(scheme)s belongs to another company, so it cannot pay "
                "people here.", scheme=config.name or ''))
        if kind == 'department':
            department = self.env['hr.department'].sudo().browse(
                segment_id).exists()
            if not department or department.company_id.id != company_id:
                raise UserError(_(
                    "That team is not in this company, so a scheme here "
                    "cannot pay it."))
        values = {
            'config_id': config.id,
            'cycle_type': cycle_type if cycle_type in dict(CYCLE_SELECTION)
                          else 'any',
            'source': 'manual',
        }
        values['department_id' if kind == 'department' else 'division_id'] = \
            segment_id
        self.env['hr.formula.scheme.assignment'].sudo().create(values)
        return self.get_board(company_id, 'any')

    @api.model
    def detach(self, assignment_id, company_id=None):
        """Take one line off the map. Nothing else is touched."""
        self._require_write()
        row = self.env['hr.formula.scheme.assignment'].sudo().browse(
            int(assignment_id or 0)).exists()
        company = company_id or (row.company_id.id if row else None)
        if row:
            row.unlink()
        return self.get_board(company, 'any')

    @api.model
    def draft(self, company_id=None):
        """Propose the map from what was actually paid. Writes nothing."""
        if not self._can_read():
            raise AccessError(_("You cannot read this company's pay runs."))
        return self.env['pb.scheme.map'].sudo().draft(
            self._pick_company(company_id))

    @api.model
    def accept_draft(self, rows, company_id=None):
        self._require_write()
        result = self.env['pb.scheme.map'].sudo().accept_draft(rows)
        result['board'] = self.get_board(company_id, 'any')
        return result

    @api.model
    def recompute(self, company_id=None):
        """Work "Paid by" out again for this company, now."""
        self._require_write()
        company_id = self._pick_company(company_id)
        changed = self.env['hr.employee'].sudo()._pb_recompute_paid_by(
            company_ids=[company_id])
        return {'changed': changed, 'board': self.get_board(company_id, 'any')}

    @api.model
    def exceptions(self, company_id=None, cycle_type='any'):
        if not self._can_read():
            raise AccessError(_("You cannot read this company's roster."))
        return self.env['pb.scheme.map'].sudo().get_exceptions(
            self._pick_company(company_id), cycle_type, MAX_NAMED)

    # ============================================ the chip on a person's card
    @api.model
    def paid_by(self, employee_id):
        """"Paid by" for one person, for the Employee 360 drawer.

        Read from the stored field when it is current and resolved live when
        it is not, so the chip is never a stale answer presented as a fresh
        one — and never a blank where the map has a perfectly good answer.
        """
        if not self._can_read():
            return {'allowed': False}
        employee = self.env['hr.employee'].sudo().browse(
            int(employee_id or 0)).exists()
        if not employee:
            return {'allowed': True, 'found': False}
        Map = self.env['pb.scheme.map'].sudo()
        if employee.pb_paid_by_stale:
            cycle = self.env['hr.employee']._pb_main_cycle(
                employee.company_id.id)
            main = Map.resolve(employee.id, cycle)
            advance = Map.resolve(employee.id, 'mid_cycle')
            advance_id = (advance.get('config_id') or 0
                          if advance.get('rung') in ('department', 'division',
                                                     'rule') else 0)
            name = main.get('config_name') or ''
            via = main.get('via') or ''
        else:
            advance_id = employee.pb_paid_by_advance_id.id
            main = {'config_id': employee.pb_paid_by_id.id}
            name = employee.pb_paid_by_id.name or ''
            via = employee.pb_paid_by_rung or ''
        advance = self.env['hr.formula.config'].sudo().browse(
            advance_id).exists() if advance_id else None
        return {
            'allowed': True,
            'found': True,
            'config_id': main.get('config_id') or 0,
            'config': name,
            'advance': advance.name if advance else '',
            'via': via,
            'label': name or _("Not covered by any scheme"),
        }
