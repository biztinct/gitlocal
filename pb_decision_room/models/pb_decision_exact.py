# -*- coding: utf-8 -*-
"""The exact-cost lane — what the payroll engine says this plan costs.

THE ROOM'S NUMBERS ARE AVERAGES, AND THEY SAY SO
------------------------------------------------
Everything on the Decision Room's stage is built from company averages: an
employer percentage, an allowance share, a ceiling, twelve months of the same
arithmetic. That is the right shape for a lever a person drags — it answers in
a millisecond and it is close enough to decide with.

It is not, however, what payroll will actually produce. This company already
owns an engine that knows exactly what it will produce: `hr.formula.config`,
the scheme that pays these people, with its own components, its own formulas
and its own ceilings. So the room can ASK it. That takes seconds rather than
milliseconds, which is why it is a background job and not a lever.

WHAT IS PORTED AND WHAT IS NOT
------------------------------
The fixed-point evaluation pass is ported from `wfp.employer.cost.calculator`
(`pb_hr_workforce_planning/models/employer_cost_calculator.py`) — constants and
inputs first, formulas evaluated, then two more passes so a forward reference
settles. That module is READ and never edited.

The BUCKETING is not ported. The legacy calculator sorted every component by
`wfp_category`, a field a person had to tag by hand on every rule of every
scheme, and which the group ledger retires (ruling G7). This uses the scheme's
OWN answer instead: `net_role` — earning, deduction, net, employer cost,
information — which the VALUEKIND programme derives from the scheme's net-pay
formula and which is already what the payslip and the fact tables read. Two
things fall out of that for free:

  * a component that is FOLDED INTO A TOTAL (`net_role_detail`) is not added on
    top of the total it is part of, which is the mistake that once reported
    ₫14 billion of gross against a true ₫927 million;
  * a component that is not a money amount at all (`value_kind` — a headcount,
    a date, a location, a yes/no) never reaches a sum.

A scheme whose components have never been classified cannot be priced this way,
and the answer says exactly that and points at the screen that fixes it. It is
not an error and it is not a zero.

WHY THERE IS A QUEUE TABLE
--------------------------
No job-queue module is assumed on this build. A row with a state, a progress
figure and a message, plus an `ir.cron` that picks up the oldest queued row, is
the whole mechanism. `start()` triggers the cron immediately, so in practice
the job begins within a second; a server under load simply takes longer and the
chip on screen says "waiting to start" instead of pretending.

NOTHING HERE WRITES TO PAYROLL. It evaluates formulas in memory and stores one
JSON blob on the plan.
"""

import logging
import time

from odoo import api, fields, models, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

#: Pay is priced in bands, because two people on ₫12,001,000 and ₫12,002,000
#: cost the same to a rounding nobody can see. The band widens if a company is
#: so varied that the narrow one would mean thousands of evaluations.
BASE_BUCKET = 1000.0
MAX_GROUPS = 400
#: A guard on a job nobody should ever be able to start against a whole group
#: of two hundred thousand people by accident.
MAX_PEOPLE = 60000
#: How long one job may run before it gives up and says so.
MAX_SECONDS = 600

#: What net pay does with a component. The scheme's own vocabulary.
ROLE_EARNING = 'earning'
ROLE_DEDUCTION = 'deduction'
ROLE_NET = 'net'
ROLE_EMPLOYER = 'employer_cost'

#: Only these value kinds are money. Everything else is a fact about the
#: person, not an amount, and never reaches a total.
MONEY_KINDS = ('money',)

JOB_STATES = [
    ('queued', "Waiting to start"),
    ('running', "Working it out"),
    ('done', "Done"),
    ('failed', "Could not finish"),
]


class PbDecisionExactJob(models.Model):
    _name = 'pb.decision.exact.job'
    _description = 'Decision Room exact-cost job'
    _order = 'id desc'

    plan_id = fields.Many2one(
        'pb.decision.plan', string="Plan", required=True, index=True,
        ondelete='cascade')
    state = fields.Selection(
        JOB_STATES, string="Where it stands", default='queued', required=True,
        index=True)
    progress = fields.Integer(string="Done (%)", default=0)
    message = fields.Char(string="What happened")
    groups = fields.Integer(string="Pay bands priced")
    people = fields.Integer(string="People priced")
    seconds = fields.Float(string="Seconds taken")
    user_id = fields.Many2one(
        'res.users', string="Asked by", default=lambda self: self.env.user,
        ondelete='set null')
    started_at = fields.Datetime(string="Started")
    finished_at = fields.Datetime(string="Finished")

    def as_dict(self):
        self.ensure_one()
        return {
            'id': self.id,
            'plan_id': self.plan_id.id,
            'state': self.state,
            'progress': self.progress,
            'message': self.message or '',
            'groups': self.groups,
            'people': self.people,
            'seconds': round(self.seconds or 0.0, 1),
        }

    # ------------------------------------------------------------ the queue
    @api.model
    def _cron_run(self):
        """One job per pass. Guarded on the REGISTRY, not on the method.

        GR14: a cron row lands in the database the moment the module installs,
        and a worker already running does not have the code yet. Asking the
        registry whether the model is there is the check that cannot throw.
        """
        if 'pb.decision.exact' not in self.env:
            return False
        job = self.sudo().search([('state', '=', 'queued')],
                                 order='id asc', limit=1)
        if not job:
            return False
        self.env['pb.decision.exact'].run_job(job.id)
        return True


class PbDecisionExact(models.AbstractModel):
    _name = 'pb.decision.exact'
    _description = 'Decision Room exact cost'

    # ------------------------------------------------------------- starting
    @api.model
    def start(self, plan_id):
        """Queue one job for one plan, and nudge the cron."""
        Room = self.env['pb.decision.room']
        Room._require_read()
        plan = self.env['pb.decision.plan'].browse(int(plan_id or 0)).exists()
        if not plan:
            raise UserError(_("That plan is not here any more."))
        Job = self.env['pb.decision.exact.job'].sudo()
        running = Job.search([('plan_id', '=', plan.id),
                              ('state', 'in', ('queued', 'running'))], limit=1)
        if running:
            return running.as_dict()
        job = Job.create({'plan_id': plan.id, 'user_id': self.env.user.id})
        cron = self.env.ref('pb_decision_room.cron_decision_exact',
                            raise_if_not_found=False)
        if cron:
            cron.sudo()._trigger()
        return job.as_dict()

    @api.model
    def status(self, plan_id):
        job = self.env['pb.decision.exact.job'].sudo().search(
            [('plan_id', '=', int(plan_id or 0))], order='id desc', limit=1)
        return job.as_dict() if job else {}

    # -------------------------------------------------------------- running
    @api.model
    def _mark(self, job_id, vals):
        """Write progress on a cursor of its own, so it is visible NOW.

        The job's own transaction will not commit for another minute, and a
        progress figure nobody can read until the work is finished is not a
        progress figure.
        """
        columns = ', '.join('%s = %%s' % name for name in vals)
        try:
            with self.env.registry.cursor() as cr:
                cr.execute(
                    "UPDATE pb_decision_exact_job SET " + columns
                    + ", write_date = now() AT TIME ZONE 'UTC' WHERE id = %s",
                    tuple(list(vals.values()) + [job_id]))
        except Exception as e:      # noqa: BLE001
            _logger.warning('exact cost: progress not written: %s', e)

    @api.model
    def run_job(self, job_id):
        job = self.env['pb.decision.exact.job'].sudo().browse(
            int(job_id or 0)).exists()
        if not job or job.state not in ('queued', 'running'):
            return False
        started = time.time()
        # ONE WRITER PER ROW, and it is `_mark`.
        #
        # Progress has to be readable while the job is still running, so it is
        # written on a cursor of its own and committed at once. The platform
        # runs on REPEATABLE READ, which means this transaction may not then
        # update a row another transaction has changed since it began — so the
        # main transaction must never touch the queue row at all. It writes
        # the RESULT, on the plan, and nothing else.
        self._mark(job.id, {'state': 'running', 'progress': 1,
                            'started_at': fields.Datetime.now()})
        try:
            result = self._price(job, started)
        except Exception as e:      # noqa: BLE001
            _logger.exception('Decision Room exact cost failed')
            self._mark(job.id, {
                'state': 'failed',
                'message': _("The pay engine stopped part way through: %s",
                             str(e)[:180]),
                'finished_at': fields.Datetime.now(),
                'seconds': time.time() - started,
            })
            return False
        seconds = time.time() - started
        result['seconds'] = round(seconds, 1)
        job.plan_id.sudo().write({'exact_result': result})
        self._mark(job.id, {
            'state': 'done',
            'progress': 100,
            'groups': result.get('groups') or 0,
            'people': result.get('people') or 0,
            'seconds': seconds,
            'message': (result.get('note') or '')[:250],
            'finished_at': fields.Datetime.now(),
        })
        _logger.info('Decision Room: exact cost for plan %s in %.1f s '
                     '(%s bands, %s people)', job.plan_id.id, seconds,
                     result.get('groups'), result.get('people'))
        return True

    # ----------------------------------------------------------- the pricing
    @api.model
    def _roster_rows(self, scope):
        """(employee, scheme, department root, wage) for the scope's people.

        One query. The room already proved the shape on 4,533 people at ~70 ms
        (WF12); adding the scheme is one more column on the same join.
        """
        company_ids = [int(i) for i in (scope.get('company_ids') or []) if i]
        if not company_ids:
            return []
        has_paid_by = 'pb_paid_by_id' in self.env['hr.employee']._fields
        scheme_col = 'e.pb_paid_by_id' if has_paid_by else 'NULL::integer'
        where = ["e.company_id IN %s", "e.active"]
        params = [tuple(company_ids)]
        if scope.get('kind') == 'scheme' and scope.get('config_id'):
            if not has_paid_by:
                return []
            where.append("e.pb_paid_by_id = %s")
            params.append(int(scope['config_id']))
        if scope.get('department_ids'):
            where.append("COALESCE(c.department_id, v.department_id) IN %s")
            params.append(tuple(scope['department_ids']))
        self.env.cr.execute("""
            WITH open_contract AS (
                SELECT DISTINCT ON (employee_id)
                       employee_id, department_id, job_id, wage
                  FROM hr_contract
                 WHERE company_id IN %%s AND state = 'open'
                 ORDER BY employee_id, wage DESC NULLS LAST, id DESC
            )
            SELECT e.id,
                   %s                                          AS scheme,
                   COALESCE(c.department_id, v.department_id)   AS dep,
                   COALESCE(c.job_id, v.job_id)                 AS job,
                   COALESCE(c.wage, 0)                          AS wage,
                   e.company_id
              FROM hr_employee e
         LEFT JOIN hr_version v    ON v.id = e.current_version_id
         LEFT JOIN open_contract c ON c.employee_id = e.id
             WHERE %s
             LIMIT %s
        """ % (scheme_col, ' AND '.join(where), MAX_PEOPLE),
            tuple([tuple(company_ids)] + params))
        return self.env.cr.fetchall()

    @api.model
    def _bands(self, rows):
        """People grouped into pay bands, widening the band if there are too many."""
        bucket = BASE_BUCKET
        while True:
            groups = {}
            for _emp, scheme, _dep, job, wage, company in rows:
                base = round(float(wage or 0.0) / bucket) * bucket
                key = (scheme or 0, job or 0, base, company)
                hit = groups.setdefault(key, {
                    'scheme': scheme or 0, 'job': job or 0, 'base': base,
                    'company': company, 'heads': 0,
                })
                hit['heads'] += 1
            if len(groups) <= MAX_GROUPS or bucket > 1e12:
                return groups, bucket
            bucket *= 10

    @api.model
    def _classified(self, config):
        """The scheme's rules, already sorted, with the bucketing decided.

        Returns `(rules, roles, source)` where `roles` maps a rule id to what
        net pay does with it. Two places that answer can come from, in order:

          `stored`  somebody has classified this scheme and the answers are on
                    the rules — the VALUEKIND board's own output;
          `derived` nobody has, so the scheme's OWN net-pay formula is walked
                    here, READ ONLY, and the roles it implies are used for this
                    one calculation. Nothing is written back: re-deciding a
                    scheme's components is a person's job on the board that
                    exists for it, not a side effect of pricing a plan.

        `roles` is `None` when neither can answer, and the room then says so
        rather than reporting a zero.
        """
        rules = config.rule_ids.sorted(key=lambda r: r.sequence)
        if not rules or 'net_role' not in rules._fields:
            return rules, None, ''
        roles = {}
        seen_any = False
        for rule in rules:
            role = rule.net_role or ''
            if role:
                seen_any = True
            detail = bool(rule.net_role_detail) \
                if 'net_role_detail' in rule._fields else False
            kind = rule.value_kind if 'value_kind' in rule._fields else 'money'
            roles[rule.id] = (role, detail, kind)
        # A CLASSIFICATION THAT CANNOT NAME NET PAY IS NOT A CLASSIFICATION.
        #
        # One tagged component out of sixty is what a half-finished afternoon
        # on the board looks like, and trusting it prices the whole scheme at
        # the value of that one component — ₫0, on the live master, with no
        # error anywhere. The test is whether the scheme knows which component
        # IS net pay: without that, nothing can be bucketed, and the scheme's
        # own formulas are read instead.
        if any(role == ROLE_NET for role, _d, _k in roles.values()):
            return rules, roles, 'stored'
        derived = self._derive_roles(config, rules)
        if derived:
            return rules, derived, 'derived'
        return rules, (roles if seen_any else None), ('stored' if seen_any
                                                      else '')

    @api.model
    def _derive_roles(self, config, rules):
        """Ask the scheme what its own net-pay formula does with each part.

        `_build_net_role_classification()` is the classifier the VALUEKIND
        programme built and it does not write — `classify_net_roles()` is the
        one that stores. Calling the first is how this lane can price a scheme
        nobody has got round to classifying yet without quietly making that
        decision on their behalf.
        """
        if not hasattr(config, '_build_net_role_classification'):
            return None
        try:
            result = config._build_net_role_classification()
        except Exception as e:      # noqa: BLE001
            _logger.info('exact cost: scheme %s cannot be classified: %s',
                         config.id, e)
            return None
        if not result or result.get('error'):
            return None
        classification = result.get('_classification')
        if not classification:
            return None
        out, any_role = {}, False
        for rule in rules:
            role = classification.roles.get(rule.id) or ''
            if role:
                any_role = True
            kind = rule.value_kind if 'value_kind' in rule._fields else 'money'
            out[rule.id] = (role,
                            bool(classification.details.get(rule.id)), kind)
        return out if any_role else None

    @api.model
    def _evaluate(self, config, rules, base):
        """The scheme's own formulas, run once for one base salary.

        The fixed-point pass is the legacy calculator's, unchanged in spirit:
        constants and inputs first, formulas next, then two more sweeps so a
        formula that reads a column defined after it settles. A rule that
        throws is worth zero and is logged; the alternative is one bad
        component taking the whole year's answer down.
        """
        values = {}
        for rule in rules:
            if rule.column_type != 'input':
                continue
            value = rule.default_value or 0.0
            code = (rule.code or '').upper()
            if code in ('BASIC', 'BASE', 'WAGE', 'BASE_SALARY', 'BASESALARY',
                        'SALARY', 'BASICSALARY'):
                value = base
            values[rule.code] = value
            if rule.column_letter:
                values[rule.column_letter] = value
        # A scheme that names its base salary in its own words: the biggest
        # money input is the one the rest of the scheme is built on.
        if not any(v == base for v in values.values()):
            money_inputs = [r for r in rules
                            if r.column_type == 'input'
                            and getattr(r, 'value_kind', 'money') == 'money']
            if money_inputs:
                first = money_inputs[0]
                values[first.code] = base
                if first.column_letter:
                    values[first.column_letter] = base

        computed = dict(values)
        for rule in rules:
            try:
                if rule.column_type == 'constant':
                    value = rule.constant_value or 0.0
                elif rule.column_type == 'formula' and rule.excel_formula:
                    value = rule.evaluate(computed)
                elif rule.column_type == 'input':
                    value = computed.get(rule.code, rule.default_value or 0.0)
                else:
                    value = computed.get(rule.code, 0.0)
            except Exception as e:          # noqa: BLE001
                _logger.debug('exact cost: rule %s: %s', rule.code, e)
                value = 0.0
            computed[rule.code] = value
            if rule.column_letter:
                computed[rule.column_letter] = value
        for _pass in range(2):
            changed = False
            for rule in rules:
                if rule.column_type != 'formula':
                    continue
                try:
                    value = rule.evaluate(computed)
                except Exception:           # noqa: BLE001
                    value = 0.0
                if computed.get(rule.code) != value:
                    computed[rule.code] = value
                    if rule.column_letter:
                        computed[rule.column_letter] = value
                    changed = True
            if not changed:
                break
        return computed

    @api.model
    def _buckets(self, rules, roles, computed):
        """One person's month, sorted the way net pay sorts it (ruling G7)."""
        out = {'earnings': 0.0, 'deductions': 0.0, 'employer': 0.0,
               'net': 0.0}
        for rule in rules:
            role, detail, kind = roles.get(rule.id, ('', False, 'money'))
            if not role or detail or kind not in MONEY_KINDS:
                continue
            amount = computed.get(rule.code, 0.0)
            try:
                amount = float(amount)
            except (TypeError, ValueError):
                continue
            if role == ROLE_EARNING:
                out['earnings'] += amount
            elif role == ROLE_DEDUCTION:
                out['deductions'] += abs(amount)
            elif role == ROLE_EMPLOYER:
                out['employer'] += abs(amount)
            elif role == ROLE_NET:
                out['net'] = amount
        out['total'] = out['earnings'] + out['employer']
        return out

    @api.model
    def _price(self, job, started):
        plan = job.plan_id
        Room = self.env['pb.decision.room']
        Scope = self.env['pb.decision.scope']
        scope = Scope.describe(plan.scope_kind, plan.scope_ref)
        if scope.get('division_id'):
            scope['department_ids'] = Room._division_departments(
                scope['division_id'], scope['company_ids'])
            if not scope['department_ids']:
                return {'ok': False, 'year': 0.0, 'months': [], 'groups': 0,
                        'people': 0,
                        'note': _("That division has no teams on it, so there "
                                  "is nobody to price.")}
        state = plan.state or {}
        raise_pct = float(state.get('raise') or 0.0)
        raise_month = int(state.get('raiseMonth') or 1)
        moves = [m for m in (state.get('moves') or []) if isinstance(m, dict)]

        rows = self._roster_rows(scope)
        if not rows:
            return {'ok': False, 'year': 0.0, 'months': [],
                    'note': _("There is nobody on this scope's roster to "
                              "price."), 'groups': 0, 'people': 0}
        bands, bucket = self._bands(rows)
        configs = {}
        for band in bands.values():
            if band['scheme'] and band['scheme'] not in configs:
                configs[band['scheme']] = self.env[
                    'hr.formula.config'].sudo().browse(band['scheme']).exists()

        unpriced_schemes, priced_rules = [], {}
        derived_schemes = []
        for config_id, config in configs.items():
            if not config:
                continue
            rules, roles, source = self._classified(config)
            if roles is None:
                unpriced_schemes.append(config.name or str(config_id))
                continue
            if source == 'derived':
                derived_schemes.append(config.name or str(config_id))
            priced_rules[config_id] = (rules, roles)

        if not priced_rules:
            return {
                'ok': False, 'year': 0.0, 'months': [], 'groups': 0,
                'people': sum(b['heads'] for b in bands.values()),
                'bucket': bucket,
                'note': _(
                    "The exact cost is worked out from the payroll scheme that "
                    "pays each person. Nobody here has a scheme that says what "
                    "each of its parts does, so there is nothing to run. Open "
                    "Mapping → Who is paid by what, then re-classify the "
                    "scheme's components, and try again."),
            }

        cache = {}
        months = [{'earnings': 0.0, 'deductions': 0.0, 'employer': 0.0,
                   'net': 0.0, 'total': 0.0, 'heads': 0.0}
                  for _m in range(12)]
        done, total_bands = 0, len(bands)
        people = 0
        priced_people = 0
        # Moves are keyed on the room's team key, `t<department root>`.
        move_by_dept = {}
        for move in moves:
            key = str(move.get('team') or '')
            if not key.startswith('t'):
                continue
            try:
                dept = int(key[1:])
            except ValueError:
                continue
            move_by_dept.setdefault(dept, []).append(
                (int(move.get('month') or 1), float(move.get('n') or 0)))
        heads_by_dept = {}
        for _emp, _scheme, dep, _job, _wage, _company in rows:
            heads_by_dept[dep or 0] = heads_by_dept.get(dep or 0, 0) + 1
        dept_of_band = {}
        # NOT `job`: that name already holds the queue row this method is
        # reporting progress on, and rebinding it here turned `job.id` into
        # an integer's missing attribute half way through the year.
        for _emp, scheme, dep, job_id, wage, company in rows:
            base = round(float(wage or 0.0) / bucket) * bucket
            key = (scheme or 0, job_id or 0, base, company)
            dept_of_band.setdefault(key, {})
            dept_of_band[key][dep or 0] = dept_of_band[key].get(dep or 0, 0) + 1

        for key, band in bands.items():
            done += 1
            people += band['heads']
            if time.time() - started > MAX_SECONDS:
                raise UserError(_(
                    "This is taking longer than ten minutes, so it stopped. "
                    "Try a smaller scope — one company or one scheme."))
            if done % 20 == 0:
                self._mark(job.id, {
                    'progress': int(done * 95 / max(1, total_bands))})
            pair = priced_rules.get(band['scheme'])
            if not pair:
                continue
            rules, roles = pair
            priced_people += band['heads']
            for m in range(12):
                raised = raise_pct if (m + 1) >= raise_month else 0.0
                base = band['base'] * (1 + raised / 100.0)
                ckey = (band['scheme'], round(base, 2))
                if ckey not in cache:
                    cache[ckey] = self._buckets(
                        rules, roles,
                        self._evaluate(configs[band['scheme']], rules, base))
                one = cache[ckey]
                heads = float(band['heads'])
                for dept, deltas in move_by_dept.items():
                    share = dept_of_band.get(key, {}).get(dept, 0)
                    if not share:
                        continue
                    pool = max(1, heads_by_dept.get(dept, 0))
                    for month, n in deltas:
                        if (m + 1) >= month:
                            heads += n * (share / pool)
                heads = max(0.0, heads)
                for name in ('earnings', 'deductions', 'employer', 'net',
                             'total'):
                    months[m][name] += one[name] * heads
                months[m]['heads'] += heads

        year = sum(m['total'] for m in months)
        note = ''
        if derived_schemes:
            note = _(
                "Nobody has confirmed what each part of %(names)s does, so the "
                "scheme's own net pay formula was read to work it out. Confirm "
                "the components on the scheme and this figure becomes final.",
                names=', '.join(sorted(derived_schemes)[:3]))
        if unpriced_schemes:
            unpriced_note = _(
                "%(n)s of the schemes here have not had their components "
                "classified yet (%(names)s), so their people are not in this "
                "figure.",
                n=len(unpriced_schemes),
                names=', '.join(sorted(unpriced_schemes)[:3]))
            note = (note + ' ' + unpriced_note).strip() if note \
                else unpriced_note
        return {
            'ok': True,
            'derived': bool(derived_schemes),
            'year': round(year, 2),
            'months': [{k: round(v, 2) for k, v in m.items()} for m in months],
            'groups': total_bands,
            'people': people,
            'priced_people': priced_people,
            'bucket': bucket,
            'currency': (plan.company_id.currency_id.name or ''),
            'scope_label': plan.scope_label or '',
            'computed_at': fields.Datetime.to_string(fields.Datetime.now()),
            'note': note,
            'estimate': (plan.summary or {}).get('cost') or 0.0,
        }
