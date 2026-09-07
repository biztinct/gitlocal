# -*- coding: utf-8 -*-
"""`pb.decision.room` — the Decision Room's only server surface.

The shape `pb_people` established and `pb_assets` repeated: an `AbstractModel`
facade, `@api.model` reads, every independent number inside its own `_safe()`
so one failing metric answers zero instead of taking the screen down,
`self.env.companies` scoping on every search, and one carefully argued
exception to "no sudo in a read" (the roster; see below).

The gate is SERVER-SIDE and it is the boundary. A reader with no Decision Room
group gets an EMPTY ROOM with `allowed: false` rather than an access dialog, so
the screen can say in words what it is and who to ask.

THE ROSTER SOURCE, verified on this build (2026-09-06) and not re-derived:

  * `hr.employee` has NO stored `department_id` / `job_id`; both are NON-STORED
    related fields through `version_id`, so neither can be searched or grouped.
    The stored truth is `hr.version`, reached by `hr.employee.current_version_id`.
  * `hr.contract` DOES carry `department_id`, `job_id` and `wage` — but on the
    Payobook demo company only `wage` is filled (department and job are NULL on
    all 4,510 open contracts), while on the AB Mauri tenant the contract's
    department IS filled on all 152.
  * So: team and role are read from the CONTRACT when it names them and from the
    employee's CURRENT VERSION otherwise, and pay is always the open contract's
    `wage`. Both databases then answer correctly with one code path.

Four queries build the whole baseline — employees, versions, contracts,
departments — and everything after that is dictionary work. Nothing loops a
recordset: the demo company has 4,533 people.

WHY THOSE FOUR QUERIES RUN UNDER SUDO, which is the one place this facade
departs from the house rule that a read never does:

  * the gate has ALREADY been passed. `_can_read()` is checked before anything
    is queried, and a reader without it never reaches this code — it gets an
    empty room with `allowed: false`;
  * what comes back is an AGGREGATE and never a person: a team's name, how many
    people are in it, and the average monthly pay of a role. No employee id, no
    name, no individual salary crosses the wire, and the client has no call that
    would let it ask for one;
  * the alternative is worse. Reading the roster as the user would mean the
    Decision Room could only be opened by somebody who also holds
    `hr.group_hr_user` — so the owner of the company, the person this screen was
    built for, would be locked out of a headcount chart by an HR permission. A
    gate that has to be widened for a screen to work is a gate that stops
    meaning anything.

Everything else — the saved plans, the assumptions row — is read as the user,
through the company rule, exactly as the house rule says.
"""

import calendar
import logging
import re
import time
from copy import deepcopy
from datetime import date

from odoo import api, fields, models, _
from odoo.exceptions import AccessError, UserError
from odoo.tools.misc import format_date

from .pb_decision_assumptions import EDIT_FORM, EDIT_GROUPS
from .pb_decision_ruleset import RULE_FIELDS
from .pb_decision_plan import MAX_PLANS, STATES as PLAN_STATES

_logger = logging.getLogger(__name__)

GROUP_USER = 'pb_decision_room.group_decision_user'
GROUP_MANAGER = 'pb_decision_room.group_decision_manager'

#: Beyond this many teams the picker stops being a picker.
MAX_TEAMS = 12
#: Roles kept per team before the rest are merged into one row.
MAX_ROLES = 12
#: How long a baseline is trusted before it is rebuilt, in seconds.
CACHE_TTL = 600

#: Seniority, read off the job title. Used to order the role picker and to make
#: "a senior hire eats the budget faster" true rather than decorative.
LEVELS = (
    (4, r'chief|director|head\b|vp\b|c\.?e\.?o|c\.?f\.?o|general manager'),
    (3, r'manager|lead\b|leader|senior|supervisor|principal'),
    (2, r'specialist|engineer|analyst|officer|executive|consultant|accountant'),
)

#: Pay fields a payslip might carry, most specific first. Only consulted when a
#: role has no contract wage at all.
PAYSLIP_WAGE_FIELDS = (
    'basic_wage', 'contract_wage', 'vietnam_basic_salary', 'net_wage', 'wage',
)

#: (database, company id, roster signature) -> (built at, baseline)
_BASELINE_CACHE = {}


def _clean_number(value):
    """"46,800,000" not "46800000.0" — a range in a refusal a person reads."""
    number = float(value or 0)
    if number == int(number):
        return '{:,}'.format(int(number))
    return '{:,.2f}'.format(number)


def _drop_company_cache(dbname, company_id):
    """Forget every cached baseline for one company.

    The key carries the roster signature, so there is no single entry to pop:
    the whole set for that company goes. Changing which teams earn revenue is
    a change to the BASELINE, and a ten-minute-old answer would quietly be the
    old one.
    """
    for key in [k for k in _BASELINE_CACHE
                if k[0] == dbname and k[1] == company_id]:
        _BASELINE_CACHE.pop(key, None)


def _level_of(name):
    low = (name or '').lower()
    for level, pattern in LEVELS:
        if re.search(pattern, low):
            return level
    return 1


class PbDecisionRoom(models.AbstractModel):
    _name = 'pb.decision.room'
    _description = 'Decision Room data'

    # ------------------------------------------------------------------ gates
    @api.model
    def _safe(self, fn, default=0):
        try:
            return fn()
        except Exception as e:      # noqa: BLE001
            _logger.debug('Decision Room metric failed: %s', e)
            return default

    @api.model
    def _can_read(self):
        user = self.env.user
        return (user.has_group(GROUP_USER) or user.has_group(GROUP_MANAGER)
                or user._is_admin())

    @api.model
    def _can_manage(self):
        user = self.env.user
        return user.has_group(GROUP_MANAGER) or user._is_admin()

    @api.model
    def _require_read(self):
        if not self._can_read():
            raise AccessError(_(
                "The Decision Room is opened by the people who plan the year. "
                "Ask your HR or finance lead to add you."))
        return True

    @api.model
    def _require_manage(self):
        if not self._can_manage():
            raise AccessError(_(
                "You can plan freely, but the assumptions behind the numbers "
                "are looked after by your HR or finance lead. Ask them to "
                "change them."))
        return True

    # ------------------------------------------------------------- the room
    @api.model
    def _empty_room(self):
        return {
            'allowed': False,
            'can_manage': False,
            'company': {},
            'assumptions': {},
            'assumptions_form': [],
            'assumptions_groups': [],
            'assumptions_scope': {},
            'awaiting': {'count': 0, 'plans': []},
            'scope': {'kind': 'company', 'ref': '', 'label': '',
                      'company_ids': [], 'currency': {}, 'mixed': False,
                      'currencies': []},
            'year': date.today().year,
            'rates': {'known': True, 'rows': {}, 'unknown': []},
            'actuals': {},
            'baseline': {'asof': str(date.today()),
                         'asof_at': fields.Datetime.to_string(
                             fields.Datetime.now()),
                         'headcount': 0,
                         'teams': [], 'blocks': [], 'source': ''},
            'plans': [],
            'limits': {'max_plans': MAX_PLANS},
        }

    @api.model
    def _company_for(self, company_id):
        allowed = self.env.companies.ids or [self.env.company.id]
        if company_id and company_id in allowed:
            return self.env['res.company'].browse(company_id)
        if self.env.company.id in allowed:
            return self.env.company
        return self.env['res.company'].browse(allowed[0])

    @api.model
    def get_room(self, company_id=None, refresh=False, scope=None, year=None):
        """Everything the room needs to draw itself, in one round trip.

        `scope` is `{kind, ref}` — the group, a country, a company, a division
        or a payroll scheme. Left out, it is the reader's own company and every
        number in the answer is the one Phases 1-3 produced, to the digit.
        """
        if not self._can_read():
            return self._empty_room()
        started = time.time()
        Scope = self.env['pb.decision.scope']
        scope = scope or {}
        if company_id and not scope.get('kind'):
            scope = {'kind': 'company', 'ref': str(company_id)}
        resolved = self._safe(
            lambda: Scope.describe(scope.get('kind'), scope.get('ref')),
            default=None)
        if not resolved:
            resolved = Scope.describe('company', str(self.env.company.id))
        companies = self.env['res.company'].sudo().browse(
            resolved['company_ids'])
        company = companies[:1] or self.env.company
        year = int(year or date.today().year)

        scoped = self._with_companies(resolved['company_ids'])
        Assumptions = scoped.env['pb.decision.assumptions']
        row = self._safe(lambda: Assumptions.get_for_scope(resolved),
                         default=Assumptions)
        baseline = self._safe(
            lambda: scoped._scope_baseline(resolved, row, refresh=refresh),
            default={'asof': str(date.today()),
                     'asof_at': fields.Datetime.to_string(
                         fields.Datetime.now()),
                     'headcount': 0, 'teams': [], 'blocks': [],
                     'source': 'none'})
        blocks = baseline.get('blocks') or []
        room = {
            'allowed': True,
            'can_manage': self._can_manage(),
            'scope': resolved,
            'year': year,
            'company': {
                'id': company.id,
                'name': company.display_name,
                'currency': self._currency_dict(
                    self.env['res.currency'].browse(
                        resolved['currency']['id'])
                    or company.currency_id),
            },
            # The scope's own currency, which for a group is the group's money
            # and for everything else is the company's. Every headline number
            # on the stage is said in this.
            'assumptions': (blocks[0]['rules'] if blocks
                            else self._safe(
                                lambda: Assumptions.effective(row, company),
                                default={})),
            # The editing surface is DESCRIBED here and drawn in the browser,
            # so the dialog cannot drift from the model behind it.
            'assumptions_form': self._safe(
                lambda: Assumptions.edit_form(), default=[]),
            'assumptions_groups': list(EDIT_GROUPS),
            'assumptions_scope': self._safe(
                lambda: self._assumptions_meta(row, resolved), default={}),
            'baseline': baseline,
            'rates': self._safe(
                lambda: self._rate_table(resolved, baseline, year),
                default={'known': True, 'rows': {}, 'unknown': []}),
            'actuals': self._safe(
                lambda: self.get_actuals(resolved, year), default={}),
            'plans': self._safe(lambda: scoped._plans(resolved), default=[]),
            'awaiting': self._safe(lambda: self.awaiting_approval(),
                                   default={'count': 0, 'plans': []}),
            'limits': {'max_plans': MAX_PLANS},
        }
        room['timing_ms'] = round((time.time() - started) * 1000)
        _logger.info('Decision Room: get_room(%s %s, %s companies) in %s ms',
                     resolved['kind'], resolved['ref'],
                     len(resolved['company_ids']), room['timing_ms'])
        return room

    @api.model
    def _currency_dict(self, currency):
        return {
            'id': currency.id if currency else 0,
            'code': (currency.name or '') if currency else '',
            'symbol': (currency.symbol or '') if currency else '',
            'position': (currency.position or 'before') if currency
                        else 'before',
            'decimals': (currency.decimal_places or 0) if currency else 0,
        }

    @api.model
    def get_scopes(self):
        """The picker's tree. Asked for only when the chip is opened."""
        if not self._can_read():
            return {'has_group': False, 'nodes': [], 'note': ''}
        started = time.time()
        out = self._safe(lambda: self.env['pb.decision.scope'].get_scopes(),
                         default={'has_group': False, 'nodes': [], 'note': ''})
        out['timing_ms'] = round((time.time() - started) * 1000)
        return out

    @api.model
    def _assumptions_meta(self, row, scope):
        """Where this scope's rules come from, in words the card can print."""
        if not row:
            return {}
        rules = row.ruleset_id
        return {
            'id': row.id,
            'scope_kind': row.scope_kind,
            'scope_label': row.scope_label or scope.get('label') or '',
            'use_country_rules': bool(row.use_country_rules),
            'country_code': rules.country_code if rules else '',
            'country_name': rules.name if rules else '',
            'note': rules.note if rules else '',
            'can_override': scope.get('kind') in ('company', 'scheme'),
        }

    # -------------------------------------------------------- assumptions
    @api.model
    def _assumptions_dict(self, row):
        if not row:
            return {}
        fields_ = [
            'revenue_target', 'demand_growth_pct', 'employer_rate_pct',
            'employee_rate_pct', 'contribution_cap', 'allowance_pct',
            'ot_multiplier', 'night_uplift_pct', 'work_days',
            'recruit_cost_months', 'severance_months', 'ramp_first_month_pct',
            'attrition_pct_year', 'bonus_month_index', 'bonus_months',
            'other_fixed_monthly', 'other_pct_revenue', 'pit_ladder', 'note',
            # Phase 2 — shifts, when the work arrives, and what a point of
            # productivity costs.
            'shift_evening_pct', 'shift_night_pct', 'evening_uplift_pct',
            'demand_day_pct', 'demand_evening_pct', 'demand_night_pct',
            'productivity_cost_per_point',
        ]
        out = {'id': row.id}
        for name in fields_:
            value = row[name]
            out[name] = value if value not in (False, None) else (
                {} if name == 'pit_ladder' else
                ('' if name == 'note' else 0))
        out['revenue_team_ids'] = row.revenue_team_ids.ids
        out['changed_on'] = str(row.write_date or '')
        out['changed_by'] = self._safe(
            lambda: row.sudo().write_uid.display_name or '', default='')
        return out

    # ----------------------------------------------------------- the roster
    @api.model
    def _roster_signature(self, company):
        """One cheap query that changes whenever the roster changes."""
        self.env.cr.execute("""
            SELECT (SELECT COUNT(*) FROM hr_contract
                     WHERE company_id = %s AND state = 'open'),
                   (SELECT MAX(write_date) FROM hr_contract
                     WHERE company_id = %s),
                   (SELECT COUNT(*) FROM hr_employee
                     WHERE company_id = %s AND active),
                   (SELECT MAX(write_date) FROM hr_employee
                     WHERE company_id = %s)
        """, (company.id, company.id, company.id, company.id))
        return str(self.env.cr.fetchone())

    @api.model
    def _baseline(self, company, refresh=False, restrict=None):
        key = (self.env.cr.dbname, company.id,
               self._restrict_key(restrict),
               self._safe(lambda: self._roster_signature(company), default=''))
        if refresh:
            _BASELINE_CACHE.pop(key, None)
        else:
            hit = _BASELINE_CACHE.get(key)
            if hit and (time.time() - hit[0]) < CACHE_TTL:
                return deepcopy(hit[1])
        built = self._build_baseline(company, restrict=restrict)
        _BASELINE_CACHE[key] = (time.time(), built)
        return deepcopy(built)

    @api.model
    def _restrict_key(self, restrict):
        if not restrict:
            return ''
        return '%s:%s' % (restrict.get('kind') or '',
                          ','.join(str(i) for i in
                                   sorted(restrict.get('ids') or [])))

    # ------------------------------------------------------ the scope roster
    @api.model
    def _division_departments(self, division_id, company_ids):
        """Every department under a division, in these companies.

        A division is attached at the TOP of a branch and covers everything
        beneath it (ruling G2), so this walks down through `parent_path` —
        stored and indexed — rather than up through forty records in Python.
        """
        if 'pb.division' not in self.env or not division_id:
            return []
        links = self.env['pb.division.link'].sudo().search([
            ('division_id', '=', int(division_id)), ('active', '=', True),
        ])
        if company_ids:
            links = links.filtered(
                lambda link: link.company_id.id in set(company_ids))
        return self.env['pb.decision.scope']._department_branch(
            links.mapped('department_id').ids)

    @api.model
    def _scheme_employees(self, config_id, company_ids):
        """The people this payroll scheme pays, for a main run."""
        Employee = self.env['hr.employee']
        if 'pb_paid_by_id' not in Employee._fields or not config_id:
            return []
        return Employee.sudo().search([
            ('company_id', 'in', company_ids or []),
            ('active', '=', True),
            ('pb_paid_by_id', '=', int(config_id)),
        ]).ids

    @api.model
    def _restrict_for(self, scope, company):
        """What narrows this company's roster inside this scope."""
        kind = scope.get('kind')
        if kind == 'division' and scope.get('division_id'):
            ids = self._division_departments(scope['division_id'],
                                             [company.id])
            return {'kind': 'departments', 'ids': ids}
        if kind == 'scheme' and scope.get('config_id'):
            return {'kind': 'employees',
                    'ids': self._scheme_employees(scope['config_id'],
                                                  [company.id])}
        return None

    @api.model
    def _company_as_team(self, company, block):
        """One company drawn as a single team whose ROLES are its own teams.

        This is what makes a group plan work without a second engine. The
        engine knows how to price a team made of roles; a group is a set of
        companies made of teams. Shaped this way, the same twelve months of
        arithmetic runs per company, the levers a person drags mean "more
        people in Manufacturing at Payobook Vietnam", and no code in the
        engine has to learn what a company is.
        """
        roles = []
        for team in block.get('teams') or []:
            roles.append({
                'key': team['key'],
                'name': team['name'],
                'job_id': 0,
                'heads': team['heads'],
                'pay_month_avg': team['pay_month_avg'],
                'level': 1,
            })
        roles.sort(key=lambda r: -r['heads'])
        heads = sum(r['heads'] for r in roles)
        pay = (sum(r['pay_month_avg'] * r['heads'] for r in roles)
               / max(1, heads)) if heads else 0.0
        return {
            'key': 'c%s' % company.id,
            'name': company.display_name,
            'department_id': 0,
            'company_id': company.id,
            'revenue': any(t.get('revenue') for t in (block.get('teams') or []))
                       or not roles,
            'heads': heads,
            'pay_month_avg': round(pay, 2),
            'roles': roles or [{
                'key': 't0', 'name': _("Everyone"), 'job_id': 0, 'heads': 0,
                'pay_month_avg': 0.0, 'level': 1,
            }],
        }

    @api.model
    def _scope_baseline(self, scope, row, refresh=False):
        """The roster for a scope, as one block per legal entity.

        A single-company scope produces exactly one block whose teams are the
        teams Phase 1 produced, and `teams` at the top is that same list — so
        every number, every key and every ordering is identical to what the
        room drew yesterday. That identity is a test (T1), not an intention.
        """
        Assumptions = self.env['pb.decision.assumptions']
        companies = self.env['res.company'].sudo().browse(
            scope.get('company_ids') or [])
        if not companies:
            companies = self.env.company
        config = None
        if scope.get('config_id') and 'hr.formula.config' in self.env:
            config = self.env['hr.formula.config'].sudo().browse(
                scope['config_id']).exists()

        blocks = []
        source = ''
        asof_at = fields.Datetime.to_string(fields.Datetime.now())
        for company in companies:
            restrict = self._restrict_for(scope, company)
            if restrict is not None and not restrict['ids']:
                # A real answer, not a missing one: this company has nobody in
                # this scope. It still gets a block, so the group stage can say
                # so instead of quietly leaving a company out of a total.
                block_baseline = {'asof': str(date.today()), 'asof_at': asof_at,
                                  'headcount': 0, 'teams': [],
                                  'source': 'empty'}
            else:
                block_baseline = self._baseline(company, refresh=refresh,
                                                restrict=restrict)
            source = source or block_baseline.get('source') or ''
            blocks.append({
                'company_id': company.id,
                'company': company.display_name,
                'country': (company.sudo().country_id.code or '').upper(),
                'currency': self._currency_dict(company.currency_id),
                'headcount': block_baseline.get('headcount', 0),
                # GROUP P5 — the days behind the head count, per company.
                'full_time': block_baseline.get(
                    'full_time', block_baseline.get('headcount', 0)),
                'split_people': block_baseline.get('split_people', 0),
                'teams': block_baseline.get('teams') or [],
                'rules': self._safe(
                    lambda c=company: Assumptions.effective(row, c, config),
                    default={}),
            })

        single = len(blocks) == 1
        if single:
            teams = blocks[0]['teams']
        else:
            teams = []
            for block in blocks:
                company = self.env['res.company'].sudo().browse(
                    block['company_id'])
                team = self._company_as_team(company, block)
                block['teams'] = [team]
                teams.append(team)
        return {
            'asof': str(date.today()),
            'asof_at': asof_at,
            'headcount': sum(b['headcount'] for b in blocks),
            # GROUP P5 — a scope may span several companies, so the full-time
            # figure and the "paid in two places" count are summed over the
            # blocks exactly as the head count is. On a company with no
            # stretches of days the two figures are equal, and the screen
            # says nothing extra.
            'full_time': round(sum(b.get('full_time', b['headcount'])
                                   for b in blocks), 1),
            'split_people': sum(b.get('split_people', 0) for b in blocks),
            'teams': teams,
            'blocks': blocks,
            'single': single,
            'mixed': bool(scope.get('mixed')),
            'source': source or 'none',
        }

    @api.model
    def _department_roots(self, company):
        """department id -> (root id, root name), one query, parents walked."""
        rows = self.env['hr.department'].sudo().search_read(
            ['|', ('company_id', '=', False), ('company_id', '=', company.id)],
            ['id', 'name', 'parent_id'])
        parent = {r['id']: (r['parent_id'][0] if r['parent_id'] else 0)
                  for r in rows}
        name = {r['id']: r['name'] for r in rows}
        roots = {}
        for dep_id in parent:
            seen, node = set(), dep_id
            while parent.get(node) and node not in seen:
                seen.add(node)
                node = parent[node]
            roots[dep_id] = (node, name.get(node) or _("Unassigned"))
        return roots

    @api.model
    def _build_baseline(self, company, restrict=None):
        """The whole roster, as ONE query.

        Reading this through the ORM took 800 ms on the 4,500-person demo
        company — 4,533 employee records, 8,592 versions and 4,510 contracts,
        each one converted into a Python recordset nobody ever looks at. The
        room needs four columns and an average. So it asks for four columns.

        `DISTINCT ON` picks one open contract per person (the best-paid, then
        the newest), which is the same answer the ORM gave and one join instead
        of a second pass.
        """
        cr = self.env.cr
        has_contracts = 'hr.contract' in self.env
        source = 'hr.contract + hr.version' if has_contracts else 'hr.version'
        # GROUP P4: a scope may narrow this company's roster to one division's
        # departments or to the people one scheme pays. With no narrowing the
        # statement below is CHARACTER FOR CHARACTER the one Phase 1 shipped,
        # which is what makes the identity test possible.
        extra, params = '', []
        if restrict and restrict.get('kind') == 'departments':
            extra = ' AND COALESCE(c.department_id, v.department_id) IN %s' \
                if has_contracts else ' AND v.department_id IN %s'
            params = [tuple(restrict['ids'])]
        elif restrict and restrict.get('kind') == 'employees':
            extra = ' AND e.id IN %s'
            params = [tuple(restrict['ids'])]
        if has_contracts:
            cr.execute("""
                WITH open_contract AS (
                    SELECT DISTINCT ON (employee_id)
                           employee_id, department_id, job_id, wage
                      FROM hr_contract
                     WHERE company_id = %s AND state = 'open'
                     ORDER BY employee_id, wage DESC NULLS LAST, id DESC
                )
                SELECT e.id,
                       COALESCE(c.department_id, v.department_id) AS dep,
                       COALESCE(c.job_id, v.job_id)               AS job,
                       COALESCE(c.wage, 0)                        AS wage
                  FROM hr_employee e
             LEFT JOIN hr_version v      ON v.id = e.current_version_id
             LEFT JOIN open_contract c   ON c.employee_id = e.id
                 WHERE e.company_id = %s AND e.active""" + extra,
                       tuple([company.id, company.id] + params))
        else:
            cr.execute("""
                SELECT e.id, v.department_id, v.job_id, 0
                  FROM hr_employee e
             LEFT JOIN hr_version v ON v.id = e.current_version_id
                 WHERE e.company_id = %s AND e.active""" + extra,
                       tuple([company.id] + params))
        roster = cr.fetchall()

        # Names come through the ORM so a translated one is the reader's own:
        # forty departments and forty jobs, not four thousand people.
        job_name = {}
        for row in self.env['hr.job'].sudo().search_read(
                ['|', ('company_id', '=', False),
                 ('company_id', '=', company.id)], ['id', 'name']):
            job_name[row['id']] = row['name']

        roots = self._department_roots(company)
        unassigned = _("Unassigned")
        other_roles = _("Other roles")

        # ---- one pass over the roster, in plain dictionaries -------------
        teams = {}
        paid_sum, paid_n, headcount = 0.0, 0, 0
        for _emp_id, dep_id, job_id, wage in roster:
            headcount += 1
            dep_id = dep_id or 0
            job_id = job_id or 0
            wage = float(wage or 0.0)
            root_id, root_name = roots.get(dep_id, (0, unassigned))
            team = teams.setdefault(root_id, {
                'department_id': root_id, 'name': root_name or unassigned,
                'heads': 0, 'pay_sum': 0.0, 'pay_n': 0, 'roles': {},
            })
            team['heads'] += 1
            role = team['roles'].setdefault(job_id, {
                'job_id': job_id, 'name': job_name.get(job_id) or other_roles,
                'heads': 0, 'pay_sum': 0.0, 'pay_n': 0,
            })
            role['heads'] += 1
            if wage > 0:
                role['pay_sum'] += wage
                role['pay_n'] += 1
                team['pay_sum'] += wage
                team['pay_n'] += 1
                paid_sum += wage
                paid_n += 1

        full_time, split_people = self._safe(
            lambda: self._full_time(company, [r[0] for r in roster]),
            default=(float(headcount), 0))

        company_avg = (paid_sum / paid_n) if paid_n else 0.0
        if not company_avg:
            company_avg = self._safe(
                lambda: self._payslip_average(company), default=0.0)
            if company_avg:
                _logger.info('Decision Room: no contract wages on company %s '
                             '— pay read from payslips instead', company.id)

        # WHICH teams earn revenue is a fact about the COMPANY's roster, so
        # it is read from the company's own row. GROUP P4 means a company can
        # now have several rows against its id — one for the company, one for
        # a division inside it, one for a scheme — and `limit=1` with no scope
        # picked whichever the database happened to return first.
        revenue_ids = set()
        row = self.env['pb.decision.assumptions'].sudo().search(
            [('company_id', '=', company.id), ('scope_kind', '=', 'company')],
            limit=1)
        if row:
            revenue_ids = set(row.revenue_team_ids.ids)

        # ---- shape it, largest team first --------------------------------
        ordered = sorted(teams.values(), key=lambda t: -t['heads'])
        out_teams = []
        for team in ordered:
            team_avg = (team['pay_sum'] / team['pay_n']) if team['pay_n'] \
                else company_avg
            roles = sorted(team['roles'].values(), key=lambda r: -r['heads'])
            if len(roles) > MAX_ROLES:
                tail = roles[MAX_ROLES:]
                roles = roles[:MAX_ROLES]
                merged = {
                    'job_id': 0, 'name': other_roles,
                    'heads': sum(r['heads'] for r in tail),
                    'pay_sum': sum(r['pay_sum'] for r in tail),
                    'pay_n': sum(r['pay_n'] for r in tail),
                }
                roles.append(merged)
            out_roles = []
            for role in roles:
                pay = (role['pay_sum'] / role['pay_n']) if role['pay_n'] \
                    else team_avg
                out_roles.append({
                    'key': 'r%s' % (role['job_id'] or 0),
                    'name': role['name'],
                    'job_id': role['job_id'],
                    'heads': role['heads'],
                    'pay_month_avg': round(pay or 0.0, 2),
                    'level': _level_of(role['name']),
                })
            out_roles.sort(key=lambda r: (-r['level'], -r['heads']))
            out_teams.append({
                'key': 't%s' % (team['department_id'] or 0),
                'name': team['name'],
                'department_id': team['department_id'],
                'revenue': (team['department_id'] in revenue_ids)
                           if revenue_ids else True,
                'heads': team['heads'],
                'pay_month_avg': round(team_avg or 0.0, 2),
                'roles': out_roles,
            })

        if len(out_teams) > MAX_TEAMS:
            tail = out_teams[MAX_TEAMS:]
            out_teams = out_teams[:MAX_TEAMS]
            merged_roles = {}
            for team in tail:
                for role in team['roles']:
                    hit = merged_roles.setdefault(role['name'], {
                        'key': 'other_%s' % len(merged_roles),
                        'name': role['name'], 'job_id': role['job_id'],
                        'heads': 0, 'pay_sum': 0.0, 'level': role['level'],
                    })
                    hit['heads'] += role['heads']
                    hit['pay_sum'] += role['pay_month_avg'] * role['heads']
            out_teams.append({
                'key': 'other_teams',
                'name': _("Other teams"),
                'department_id': 0,
                'revenue': any(t['revenue'] for t in tail),
                'heads': sum(t['heads'] for t in tail),
                'pay_month_avg': round(
                    sum(t['pay_month_avg'] * t['heads'] for t in tail)
                    / max(1, sum(t['heads'] for t in tail)), 2),
                'roles': self._cap_roles(sorted(merged_roles.values(),
                                                 key=lambda r: -r['heads']),
                                         other_roles),
            })

        return {
            'asof': str(date.today()),
            # WHEN this roster was actually read, not which day it is.
            # The baseline is cached for ten minutes, so a number on screen
            # can legitimately be a few minutes behind a hire made this
            # morning; the dialog says the time and offers to read it again.
            'asof_at': fields.Datetime.to_string(fields.Datetime.now()),
            'headcount': headcount,
            # GROUP P5 — head count counts PEOPLE; the full-time figure counts
            # their days. Identical to the head count on every company that
            # has never written a stretch of days, which is what keeps the P4
            # identity test true.
            'full_time': full_time,
            'split_people': split_people,
            'teams': out_teams,
            'source': source,
        }

    @api.model
    def _full_time(self, company, employee_ids):
        """`(full-time equivalents, people paid in two places)`.

        Soft on the registry: a database without `pb_workseg` gets the head
        count back unchanged, which is the honest answer there — one
        employment, one whole month, each.
        """
        total = float(len(employee_ids))
        if 'pb.work.segment' not in self.env or not employee_ids:
            return total, 0
        today = fields.Date.context_today(self)
        month = today.replace(day=1)
        rows = self.env['pb.work.segment'].sudo().search_read(
            [('state', '=', 'confirmed'), ('month', '=', month),
             '|', ('home_employee_id', 'in', employee_ids),
                  ('host_employee_id', 'in', employee_ids)],
            ['home_employee_id', 'host_employee_id', 'fte', 'share',
             'home_company_id', 'host_company_id', 'kind'])
        if not rows:
            return total, 0
        known = set(employee_ids)
        adjust, people = 0.0, set()
        for row in rows:
            fte = row['fte'] or row['share'] or 0.0
            home = (row['home_employee_id'] or [0])[0]
            host = (row['host_employee_id'] or [0])[0]
            crossed = ((row['home_company_id'] or [0])[0]
                       != (row['host_company_id'] or [0])[0])
            if home in known and (crossed or row['kind'] in ('joiner',
                                                             'leaver')):
                adjust -= fte
                if crossed:
                    people.add(home)
            if host in known and crossed:
                # The host employment was counted as a whole person by the
                # roster query; it is worth only the days it hosted.
                adjust -= (1.0 - fte)
                people.add(host)
        return round(max(0.0, total + adjust), 1), len(people)

    @api.model
    def _cap_roles(self, roles, other_label):
        """The longest tail of roles becomes one row — it is never DROPPED.

        Slicing the list was the obvious thing to write and it silently lost
        five of AB Mauri's 153 people: the team said 18 heads and its roles
        added up to 13, so December's headcount was 148 and every number built
        on it was quietly wrong. A roll-up that does not conserve the count is
        not a roll-up.
        """
        kept = [{
            'key': r['key'], 'name': r['name'], 'job_id': r['job_id'],
            'heads': r['heads'],
            'pay_month_avg': round(r['pay_sum'] / max(1, r['heads']), 2),
            'level': r['level'],
        } for r in roles[:MAX_ROLES]]
        tail = roles[MAX_ROLES:]
        if tail:
            heads = sum(r['heads'] for r in tail)
            kept.append({
                'key': 'other_roles', 'name': other_label, 'job_id': 0,
                'heads': heads,
                'pay_month_avg': round(
                    sum(r['pay_sum'] for r in tail) / max(1, heads), 2),
                'level': 1,
            })
        return kept

    @api.model
    def _payslip_average(self, company):
        """Last resort: what payslips say a month of pay looks like."""
        if 'hr.payslip' not in self.env:
            return 0.0
        Payslip = self.env['hr.payslip'].sudo()
        field = next((f for f in PAYSLIP_WAGE_FIELDS if f in Payslip._fields),
                     None)
        if not field:
            return 0.0
        groups = Payslip._read_group(
            [('company_id', '=', company.id)], [], ['%s:avg' % field])
        value = (groups and groups[0] and groups[0][0]) or 0.0
        _logger.info('Decision Room: payslip fallback used field %s -> %s',
                     field, value)
        return value or 0.0

    # ------------------------------------------------------ the scope's rule
    @api.model
    def _with_companies(self, company_ids):
        """This facade, with the scope's companies visible to the ORM.

        GR26, and the same family as GR16. A scope is resolved from every
        company the reader is ENTITLED to (`res.users.company_ids`), because a
        person planning a group should not have to go and tick five boxes in a
        switcher first. But the company RECORD RULE on a plan and on a set of
        assumptions reads `company_ids` from the CONTEXT — the switcher — so
        saving a plan for Payobook Vietnam while standing in the head office
        was refused with an access dialog naming a "top-secret record".

        Widening the context to companies the user already holds is not a
        privilege: `allowed_company_ids` may only ever be a subset of
        `user.company_ids`, and that is exactly what this intersects with. A
        company nobody gave this person is still invisible.
        """
        entitled = set(self.env.user.company_ids.ids) or {self.env.company.id}
        wanted = {int(i) for i in (company_ids or []) if i} & entitled
        allowed = sorted(set(self.env.companies.ids) | wanted)
        if not allowed:
            return self
        return self.with_context(allowed_company_ids=allowed)

    @api.model
    def _for_plan(self, plan):
        """The same, for a record that already knows its own companies."""
        ids = (plan.sudo().company_ids.ids
               or plan.sudo().company_id.ids)
        return self._with_companies(ids)

    # ------------------------------------------------------------- the dock
    @api.model
    def _plan_dict(self, plan):
        return {
            'id': plan.id,
            'name': plan.name,
            'user': plan.user_id.display_name or '',
            'user_id': plan.user_id.id,
            'mine': plan.user_id.id == self.env.user.id,
            'is_reference': plan.is_reference,
            'summary': plan.summary or {},
            'goals': plan.goals or {},
            'state': plan.state or {},
            'note': plan.note or '',
            'written': str(plan.write_date or ''),
            # ---- GROUP P4 -------------------------------------------------
            'scope_kind': plan.scope_kind,
            'scope_ref': plan.scope_ref or '',
            'scope_label': plan.scope_label or '',
            'currency': (plan.summary or {}).get('currency')
                        or (plan.currency_id.name or ''),
            'status': plan.status,
            'status_label': dict(PLAN_STATES).get(plan.status, ''),
            'proposed_by': plan.proposed_by.display_name or '',
            'decided_by': plan.decided_by.display_name or '',
            'decided_at': str(plan.decided_at or ''),
            'decision_note': plan.decision_note or '',
            'versions': plan.version_count,
            'exact': plan.exact_result or {},
        }

    @api.model
    def _plans(self, scope):
        """Every plan for the companies this scope covers.

        Deliberately NOT narrowed to the scope itself: a person looking at
        Retail should be able to see, and compare against, the plan somebody
        saved for the whole company. The dock says which scope each one is for
        and the comparison picker refuses the ones in another currency.
        """
        company_ids = (scope.get('company_ids') if isinstance(scope, dict)
                       else scope.ids) or [self.env.company.id]
        plans = self.env['pb.decision.plan'].search(
            [('company_id', 'in', company_ids)], limit=MAX_PLANS * 4)
        return [self._plan_dict(plan) for plan in plans]

    # ------------------------------------------------------------- the rates
    @api.model
    def _rate_table(self, scope, baseline, year):
        """One rate per currency per month, for the browser to convert with.

        Group ledger rule 7: no converted amount is ever stored, and the plan
        JSON holds each company's own money. So the group total has to be built
        at READ time — and the arithmetic happens in the browser, because the
        levers move faster than a round trip. What crosses the wire is not a
        converted number, it is the RATE, with its date and whether anybody
        actually knows it.
        """
        target = self.env['res.currency'].sudo().browse(
            (scope.get('currency') or {}).get('id') or 0)
        blocks = baseline.get('blocks') or []
        codes = {}
        for block in blocks:
            code = (block.get('currency') or {}).get('code')
            if code:
                codes[code] = block['currency']['id']
        out = {
            'target': scope.get('currency') or {},
            'policy': '',
            'rows': {},
            'unknown': [],
            'known': True,
        }
        if not target or len(codes) <= 1 and target.name in codes:
            out['policy'] = self.env['pb.fx'].policy_for(
                self.env['res.company'].browse(scope.get('company_ids') or []))
            return out
        Fx = self.env['pb.fx']
        company = self.env['res.company'].sudo().browse(
            (scope.get('company_ids') or [self.env.company.id])[0])
        out['policy'] = Fx.policy_for(company)
        for code, currency_id in codes.items():
            months = []
            for month in range(1, 13):
                last = calendar.monthrange(year, month)[1]
                meta = Fx.rate(currency_id, target.id,
                               date(year, month, last), company)
                months.append({
                    'month': month,
                    'rate': meta['rate'] if meta['known'] else 0.0,
                    'known': bool(meta['known']),
                    'rate_date': meta.get('rate_date') or '',
                })
                if not meta['known']:
                    out['known'] = False
            out['rows'][code] = months
            if not all(m['known'] for m in months):
                out['unknown'].append({
                    'code': code,
                    'note': Fx.unknown_note(currency_id, target.id,
                                            date(year, 1, 31)),
                })
        return out

    # ---------------------------------------------------- what actually ran
    @api.model
    def get_actuals(self, scope, year=None):
        """What the closed pay runs of this year actually produced.

        Read from the fact tables (`pb.fact.emp`), which already carry the
        scheme, the division, the person and whether the row is a mid-month
        advance — so filtering a scope is a `WHERE`, not a walk over payslips.
        Advances are OUT: counting a mid-month advance and the end-of-month run
        that settles it adds the same money twice.

        The cost is pay plus what the employer paid on top of it — the same
        three component types the Explorer calls "Total cost" — because that is
        what the room's own "workforce cost" means.
        """
        if 'pb.fact.emp' not in self.env:
            return {'available': False, 'months': [],
                    'note': _("Closed pay runs are not being collected on "
                              "this database yet.")}
        scope = scope if isinstance(scope, dict) else \
            self.env['pb.decision.scope'].describe('company',
                                                   str(self.env.company.id))
        year = int(year or date.today().year)
        company_ids = scope.get('company_ids') or [self.env.company.id]
        where = ["company_id IN %s", "year = %s", "NOT is_advance",
                 "category_type IN ('basic', 'allowance', 'employer_cost')"]
        params = [tuple(company_ids), year]
        if scope.get('kind') == 'division' and scope.get('division_id'):
            where.append("division_id = %s")
            params.append(int(scope['division_id']))
        elif scope.get('kind') == 'scheme' and scope.get('config_id'):
            where.append("config_id = %s")
            params.append(int(scope['config_id']))
        self.env.cr.execute("""
            SELECT EXTRACT(MONTH FROM month)::int AS m, company_id,
                   SUM(amount), COUNT(DISTINCT COALESCE(person_id,
                                                        employee_id))
              FROM pb_fact_emp
             WHERE """ + ' AND '.join(where) + """
             GROUP BY 1, 2 ORDER BY 1
        """, tuple(params))
        rows = self.env.cr.fetchall()
        currency_of = {c.id: (c.currency_id.name or '')
                       for c in self.env['res.company'].sudo().browse(
                           company_ids)}
        months = {}
        for month, company_id, amount, people in rows:
            hit = months.setdefault(month, {'month': month, 'people': 0,
                                            'by_company': {}})
            hit['people'] += people or 0
            hit['by_company'][str(company_id)] = {
                'cost': round(float(amount or 0.0), 2),
                'currency': currency_of.get(company_id, ''),
                'people': people or 0,
            }
        out = {
            'available': bool(rows),
            'year': year,
            'months': [months[m] for m in sorted(months)],
            'note': '' if rows else _(
                "No pay run has been closed for %s yet, so there is nothing to "
                "draw over the plan.", year),
            'partial': '',
        }
        # HOW MUCH OF THIS SCOPE THE CLOSED RUNS ACTUALLY KNOW ABOUT.
        #
        # A pay run carries the scheme that produced it only if it was created
        # since that became a thing (GROUP P2), and an older run sits in the
        # facts without one. So a SCHEME scope can legitimately find one person
        # in a month where nine hundred were paid. The figure is passed to the
        # room, which decides in one place — `closedMonths()` — which month is
        # worth naming and says so in the sentence beside the line.
        out['busiest'] = max((m['people'] for m in out['months']), default=0)
        out['roster'] = int(scope.get('people') or 0)
        return out

    # ------------------------------------------------------------- writing
    @api.model
    def save_plan(self, vals):
        """Create or replace one saved plan. Returns its id."""
        self._require_read()
        vals = vals or {}
        name = (vals.get('name') or '').strip()
        if not name:
            raise UserError(_("Give the plan a name first."))
        scope = self.env['pb.decision.scope'].describe(
            (vals.get('scope') or {}).get('kind'),
            (vals.get('scope') or {}).get('ref'))
        company = self.env['res.company'].sudo().browse(
            (scope['company_ids'] or [self.env.company.id])[0])
        Plan = self._with_companies(scope['company_ids'])\
            .env['pb.decision.plan']
        existing = Plan.search([('company_id', '=', company.id),
                                ('scope_kind', '=', scope['kind']),
                                ('scope_ref', '=', scope['ref']),
                                ('name', '=', name)], limit=1)
        payload = {
            'state': vals.get('state') or {},
            'goals': vals.get('goals') or {},
            'summary': vals.get('summary') or {},
            'note': vals.get('note') or '',
            'scope_kind': scope['kind'],
            'scope_ref': scope['ref'],
            'scope_label': scope['label'],
            'company_ids': [(6, 0, scope['company_ids'])],
        }
        if existing:
            if not vals.get('replace'):
                raise UserError(_(
                    "A plan called \"%s\" already exists. Replace it, or give "
                    "this one another name.", name))
            if existing.user_id.id != self.env.user.id and not self._can_manage():
                raise AccessError(_(
                    "\"%s\" was saved by %s. Ask them to replace it, or save "
                    "yours under another name.",
                    name, existing.user_id.display_name or _("someone else")))
            existing.write(payload)
            return existing.id
        if Plan.search_count([('company_id', '=', company.id)]) >= MAX_PLANS:
            raise UserError(_(
                "%s plans are saved for this company. Remove one first.",
                MAX_PLANS))
        payload.update({'name': name, 'company_id': company.id})
        return Plan.create(payload).id

    @api.model
    def delete_plan(self, plan_id):
        self._require_read()
        plan = self.env['pb.decision.plan'].sudo().browse(
            int(plan_id or 0)).exists()
        if plan:
            plan = self._for_plan(plan).env['pb.decision.plan']\
                .browse(plan.id)
        if not plan:
            return False
        if plan.user_id.id != self.env.user.id and not self._can_manage():
            raise AccessError(_(
                "\"%s\" was saved by %s. Only they, or your HR lead, can "
                "remove it.",
                plan.name, plan.user_id.display_name or _("someone else")))
        plan.unlink()
        return True

    @api.model
    def set_reference(self, plan_id):
        """Make one plan the thing everything else is measured against."""
        self._require_read()
        found = self.env['pb.decision.plan'].sudo().browse(
            int(plan_id or 0)).exists()
        room = self._for_plan(found) if found else self
        plans = room.env['pb.decision.plan']
        plan = plans.browse(int(plan_id or 0)).exists()
        if not plan:
            # "compare against the original baseline" — clear the flag
            company = self._company_for(None)
            plans.search([('company_id', '=', company.id),
                          ('is_reference', '=', True)]).write(
                {'is_reference': False})
            return 0
        plan.write({'is_reference': True})
        return plan.id

    @api.model
    def save_assumptions(self, vals):
        """Change what the room believes — the planning lead's job alone.

        Every number is checked HERE against the range the form advertises,
        because a browser is a suggestion and a server is a rule; the refusal
        is a sentence naming the field and its range, not a traceback. Writing
        also drops this company's cached baseline, since one of the fields
        (which teams earn revenue) is part of the baseline itself and a stale
        cache would have the room drawing the old answer for ten minutes.
        """
        self._require_manage()
        vals = vals or {}
        Scope = self.env['pb.decision.scope']
        scope = Scope.describe((vals.get('scope') or {}).get('kind')
                               or ('company' if vals.get('company_id')
                                   else None),
                               (vals.get('scope') or {}).get('ref')
                               or vals.get('company_id'))
        company = self.env['res.company'].sudo().browse(
            (scope['company_ids'] or [self.env.company.id])[0])
        Assumptions = self._with_companies(scope['company_ids'])\
            .env['pb.decision.assumptions']
        row = Assumptions.get_for_scope(scope)
        ranges = {name: (kind, low, high)
                  for _group, name, kind, _step, low, high in EDIT_FORM}
        payload = {}
        for name, value in vals.items():
            if name in ('company_id', 'id', 'scope'):
                continue
            if name == 'use_country_rules':
                # The switch that decides whether the statutory half of this
                # row is read from the country's rules or from the numbers
                # typed here. Not a range — a choice.
                payload['use_country_rules'] = bool(value)
                continue
            if name == 'revenue_team_ids':
                ids = [int(x) for x in (value or []) if int(x or 0) > 0]
                payload['revenue_team_ids'] = [(6, 0, ids)]
                continue
            if name == 'note':
                payload['note'] = value or ''
                continue
            if name not in ranges:
                continue
            kind, low, high = ranges[name]
            try:
                number = float(value or 0.0)
            except (TypeError, ValueError):
                raise UserError(_(
                    "\"%s\" needs to be a number.",
                    Assumptions._fields[name].string)) from None
            if kind != 'money' and (number < low - 1e-9
                                    or number > high + 1e-9):
                raise UserError(_(
                    "\"%(label)s\" has to be between %(low)s and %(high)s.",
                    label=Assumptions._fields[name].string,
                    low=_clean_number(low), high=_clean_number(high)))
            if kind == 'money' and number < 0:
                raise UserError(_(
                    "\"%s\" cannot be negative.",
                    Assumptions._fields[name].string))
            payload[name] = (int(round(number)) if kind == 'int' else number)
        # TYPING ONE OF THE COUNTRY'S NUMBERS IS THE OVERRIDE.
        #
        # A person who has just typed 24 into "Employer contributions" and is
        # shown 23.5 on the way back has been overruled by a switch they never
        # saw. So a write to any of the thirteen statutory numbers takes this
        # scope off the country's rules by itself, and the card's own "Reset
        # to country rules" is the way back.
        if payload and set(payload) & set(RULE_FIELDS):
            payload.setdefault('use_country_rules', False)
        if payload:
            row.write(payload)
            for company_id in (scope['company_ids'] or [company.id]):
                _drop_company_cache(self.env.cr.dbname, company_id)
        config = None
        if scope.get('config_id') and 'hr.formula.config' in self.env:
            config = self.env['hr.formula.config'].sudo().browse(
                scope['config_id']).exists()
        out = Assumptions.effective(row, company, config)
        out['scope'] = self._assumptions_meta(row, scope)
        out['signature'] = self._safe(
            lambda: self._roster_signature(company), default='')
        return out

    @api.model
    def reset_assumptions(self, scope=None):
        """Put a scope back on its country's rules.

        The opposite of typing your own numbers, and it must be one press:
        a person who overrode a contribution rate to try something needs a way
        back that does not involve remembering what the rate used to be.
        """
        self._require_manage()
        Scope = self.env['pb.decision.scope']
        scope = Scope.describe((scope or {}).get('kind'), (scope or {}).get('ref'))
        Assumptions = self._with_companies(scope['company_ids'])\
            .env['pb.decision.assumptions']
        row = Assumptions.get_for_scope(scope)
        row.write({'use_country_rules': True})
        for company_id in scope['company_ids']:
            _drop_company_cache(self.env.cr.dbname, company_id)
        company = self.env['res.company'].sudo().browse(
            (scope['company_ids'] or [self.env.company.id])[0])
        out = Assumptions.effective(row, company)
        out['scope'] = self._assumptions_meta(row, scope)
        return out

    @api.model
    def rulesets(self):
        """Every set of country rules that ships, for the assumptions card."""
        self._require_read()
        return self._safe(
            lambda: self.env['pb.decision.ruleset'].catalogue(), default=[])

    # ------------------------------------------------------- the decision
    @api.model
    def propose_plan(self, plan_id, note=''):
        """Hand a plan to whoever approves plans here."""
        self._require_read()
        plan = self.env['pb.decision.plan'].sudo().browse(
            int(plan_id or 0)).exists()
        if plan:
            plan = self._for_plan(plan).env['pb.decision.plan']\
                .browse(plan.id)
        if not plan:
            raise UserError(_("That plan is not here any more."))
        if plan.user_id.id != self.env.user.id and not self._can_manage():
            raise AccessError(_(
                "\"%(name)s\" was saved by %(who)s. Ask them to propose it.",
                name=plan.name,
                who=plan.user_id.display_name or _("someone else")))
        plan.sudo().action_propose(note or '')
        return self._plan_dict(plan)

    @api.model
    def decide_plan(self, plan_id, approve=True, note=''):
        """Approve a plan, or send it back with a sentence."""
        self._require_read()
        plan = self.env['pb.decision.plan'].sudo().browse(
            int(plan_id or 0)).exists()
        if plan:
            plan = self._for_plan(plan).env['pb.decision.plan']\
                .browse(plan.id)
        if not plan:
            raise UserError(_("That plan is not here any more."))
        if not self._can_manage():
            raise AccessError(_(
                "Approving a plan is your HR or finance lead's to do. Ask "
                "them to take a look — it is waiting on their home page."))
        if approve:
            plan.sudo().action_approve(note or '')
        else:
            plan.sudo().action_reject(note or '')
        return self._plan_dict(plan)

    @api.model
    def copy_plan(self, plan_id):
        """Carry on from an approved plan without rewriting what was agreed."""
        self._require_read()
        plan = self.env['pb.decision.plan'].sudo().browse(
            int(plan_id or 0)).exists()
        if plan:
            plan = self._for_plan(plan).env['pb.decision.plan']\
                .browse(plan.id)
        if not plan:
            raise UserError(_("That plan is not here any more."))
        return self._plan_dict(plan.sudo().action_copy_for_editing())

    @api.model
    def plan_versions(self, plan_id):
        """Every version kept of one plan, newest first."""
        self._require_read()
        plan = self.env['pb.decision.plan'].sudo().browse(
            int(plan_id or 0)).exists()
        if plan:
            plan = self._for_plan(plan).env['pb.decision.plan']\
                .browse(plan.id)
        if not plan:
            return []
        return [{
            'id': version.id,
            'number': version.number,
            'label': version.label or '',
            'by': version.created_by.display_name or '',
            'at': str(version.created_at or ''),
            'snapshot': version.snapshot or {},
        } for version in plan.version_ids]

    @api.model
    def awaiting_approval(self):
        """The plans waiting on this reader, for the home page's chip."""
        if not self._can_read():
            return {'count': 0, 'plans': []}
        if not self._can_manage():
            return {'count': 0, 'plans': []}
        plans = self._with_companies(self.env.user.company_ids.ids)\
            .env['pb.decision.plan'].search(
                [('status', '=', 'proposed')], limit=MAX_PLANS)
        return {
            'count': len(plans),
            'plans': [{'id': p.id, 'name': p.name,
                       'scope_label': p.scope_label or '',
                       'by': p.proposed_by.display_name or ''}
                      for p in plans],
        }

    # ------------------------------------------------------- the exact cost
    @api.model
    def start_exact(self, plan_id):
        self._require_read()
        return self.env['pb.decision.exact'].start(plan_id)

    @api.model
    def exact_status(self, plan_id):
        self._require_read()
        out = self.env['pb.decision.exact'].status(plan_id)
        plan = self.env['pb.decision.plan'].sudo().browse(
            int(plan_id or 0)).exists()
        out['result'] = (plan.exact_result or {}) if plan else {}
        return out

    # -------------------------------------------------------- the brief
    @api.model
    def render_brief(self, payload):
        """One printable page that says what was decided and what it assumed.

        The CLIENT computed every number (it is the only thing holding the
        twelve computed months); the server LAYS THEM OUT and stamps the
        company, the reader and the date on them, so a brief that leaves this
        building carries the same provenance a report would.

        The page is self-contained on purpose — no script, no stylesheet, no
        image, nothing fetched from anywhere — because it is opened in a blank
        tab and may be saved to a laptop and mailed on, and a brief whose
        formatting depends on a server it can no longer reach is not a brief.
        """
        self._require_read()
        payload = payload or {}
        company = self._company_for(payload.get('company_id'))
        html = self.env['ir.qweb']._render('pb_decision_room.brief', {
            'brief': payload,
            'company_name': company.display_name,
            'reader': self.env.user.display_name,
            # In the reader's own locale: an owner in Hanoi reading a
            # Vietnamese brief should not find one American date on it.
            'today': format_date(self.env, fields.Date.context_today(self)),
        })
        return '<!doctype html>\n' + str(html)
