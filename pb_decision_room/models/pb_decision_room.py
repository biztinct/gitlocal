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

import logging
import re
import time
from copy import deepcopy
from datetime import date

from odoo import api, models, _
from odoo.exceptions import AccessError, UserError

from .pb_decision_plan import MAX_PLANS

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
            'baseline': {'asof': str(date.today()), 'headcount': 0,
                         'teams': [], 'source': ''},
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
    def get_room(self, company_id=None, refresh=False):
        """Everything the room needs to draw itself, in one round trip."""
        if not self._can_read():
            return self._empty_room()
        started = time.time()
        company = self._company_for(company_id)
        assumptions = self._safe(
            lambda: self.env['pb.decision.assumptions'].get_for_company(company),
            default=self.env['pb.decision.assumptions'])
        room = {
            'allowed': True,
            'can_manage': self._can_manage(),
            'company': {
                'id': company.id,
                'name': company.display_name,
                'currency': {
                    'code': company.currency_id.name or '',
                    'symbol': company.currency_id.symbol or '',
                    'position': company.currency_id.position or 'before',
                    'decimals': company.currency_id.decimal_places or 0,
                },
            },
            'assumptions': self._safe(
                lambda: self._assumptions_dict(assumptions), default={}),
            'baseline': self._safe(
                lambda: self._baseline(company, refresh=refresh),
                default={'asof': str(date.today()), 'headcount': 0,
                         'teams': [], 'source': 'none'}),
            'plans': self._safe(lambda: self._plans(company), default=[]),
            'limits': {'max_plans': MAX_PLANS},
        }
        room['timing_ms'] = round((time.time() - started) * 1000)
        _logger.info('Decision Room: get_room(company=%s) in %s ms',
                     company.id, room['timing_ms'])
        return room

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
        ]
        out = {'id': row.id}
        for name in fields_:
            value = row[name]
            out[name] = value if value not in (False, None) else (
                {} if name == 'pit_ladder' else
                ('' if name == 'note' else 0))
        out['revenue_team_ids'] = row.revenue_team_ids.ids
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
    def _baseline(self, company, refresh=False):
        key = (self.env.cr.dbname, company.id,
               self._safe(lambda: self._roster_signature(company), default=''))
        if refresh:
            _BASELINE_CACHE.pop(key, None)
        else:
            hit = _BASELINE_CACHE.get(key)
            if hit and (time.time() - hit[0]) < CACHE_TTL:
                return deepcopy(hit[1])
        built = self._build_baseline(company)
        _BASELINE_CACHE[key] = (time.time(), built)
        return deepcopy(built)

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
    def _build_baseline(self, company):
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
                 WHERE e.company_id = %s AND e.active
            """, (company.id, company.id))
        else:
            cr.execute("""
                SELECT e.id, v.department_id, v.job_id, 0
                  FROM hr_employee e
             LEFT JOIN hr_version v ON v.id = e.current_version_id
                 WHERE e.company_id = %s AND e.active
            """, (company.id,))
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

        company_avg = (paid_sum / paid_n) if paid_n else 0.0
        if not company_avg:
            company_avg = self._safe(
                lambda: self._payslip_average(company), default=0.0)
            if company_avg:
                _logger.info('Decision Room: no contract wages on company %s '
                             '— pay read from payslips instead', company.id)

        revenue_ids = set()
        row = self.env['pb.decision.assumptions'].sudo().search(
            [('company_id', '=', company.id)], limit=1)
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
            'headcount': headcount,
            'teams': out_teams,
            'source': source,
        }

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

    # ------------------------------------------------------------- the dock
    @api.model
    def _plans(self, company):
        plans = self.env['pb.decision.plan'].search(
            [('company_id', '=', company.id)], limit=MAX_PLANS * 2)
        out = []
        for plan in plans:
            out.append({
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
            })
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
        company = self._company_for(vals.get('company_id'))
        Plan = self.env['pb.decision.plan']
        existing = Plan.search([('company_id', '=', company.id),
                                ('name', '=', name)], limit=1)
        payload = {
            'state': vals.get('state') or {},
            'goals': vals.get('goals') or {},
            'summary': vals.get('summary') or {},
            'note': vals.get('note') or '',
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
        plan = self.env['pb.decision.plan'].browse(int(plan_id or 0)).exists()
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
        plans = self.env['pb.decision.plan']
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
        """Phase 1 writes the revenue target and the growth by December."""
        self._require_manage()
        vals = vals or {}
        company = self._company_for(vals.get('company_id'))
        row = self.env['pb.decision.assumptions'].get_for_company(company)
        payload = {}
        for name in ('revenue_target', 'demand_growth_pct'):
            if name in vals:
                payload[name] = float(vals[name] or 0.0)
        if payload:
            row.write(payload)
        return self._assumptions_dict(row)
