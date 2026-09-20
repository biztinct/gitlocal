# -*- coding: utf-8 -*-
"""The home dashboard's one data call.

THREE RULES GOVERN THIS FILE, and all of them are about honesty.

1. NO FABRICATED NUMBER, EVER. A brand-new tenant sees zeros and a helpful
   empty state; it never sees a company that does not exist. The legacy
   analytics fallback that used to fill these in was a hard-coded sample dict
   and it reached a real customer's screen.

2. NO HARD DEPENDENCY ON ANOTHER COCKPIT. The manifest declares `web`,
   `om_hr_payroll` and `pb_hr_payroll_base` and nothing else. The activation
   checklist below asks questions of the learning module and of the import
   module, and both of those questions are asked through `optional()`, which
   answers "not on this database" instead of raising. There is no python
   import of either module anywhere in here, and there must never be one:
   this dashboard is the first screen of every tenant, including the lean
   ones.

3. EVERY FIGURE NAMES THE MONTH IT IS ABOUT (LOOK P4). The headline numbers
   used to report whichever payroll month happened to be the most recent and
   never say which one, which is the one thing that makes a number
   uncheckable — on payobook they were reporting a single November test
   payslip beside a headcount of four and a half thousand people. The month
   is now resolved HERE, on the server (LOOK rule 18), named in the payload,
   and the reader may choose another one.
"""
from odoo import api, models

# The two scenarios the activation checklist watches, under the namespace
# `learn.progress` stores them in (pb_learn/models/learn_progress.py
# SCENARIO_PREFIX). Strings, not imports — see rule 2 above.
SCENARIO_PREFIX = 'scenario:'
SC_WELCOME = 'sc_welcome'
SC_PAYRUN = 'sc_payrun'

# The one predicate the KPI block is restricted to, in one place because it now
# appears in three statements. With a Mid+End cycle BOTH payslips carry the full
# GROSS, so counting both doubles the payroll AND the headcount.
_END_CYCLE = "(fc.cycle_type = 'end_cycle' OR fc.id IS NULL)"


class PbDashboard(models.AbstractModel):
    _name = 'pb.dashboard'
    _description = 'Payobook Dashboard data provider'

    # ===================================================== the payroll month
    # A PERIOD IS A SCOPE, NOT A FILTER (LOOK rule 18). It resolves on the
    # SERVER, the payload says which month every figure is about, and the
    # browser adopts what came back rather than what it asked for.
    #
    # The vocabulary is the one LOOK P3 shipped on the Budget board, matched
    # rather than imported — `pb_dashboard` may not depend on `pb_budget`, or
    # on anything else (rule 2 above). Accepted: nothing (the latest month with
    # payroll), `'current'`, `'YYYY-MM'` and `'YYYY-MM..YYYY-MM'`. A stretch
    # collapses to the newest month inside it that has payroll, because this
    # board's numbers are a MONTH's ("Monthly payroll", "Avg salary") and a
    # figure summed over four months under that label would be a lie no chip
    # could repair. Anything this cannot read — including P3's `'Q1'`, which
    # needs a fiscal year this board has no notion of — falls back to the
    # latest month, silently, exactly as ledger rule 21 requires: a saved link
    # is never an error and never an empty screen.

    @api.model
    def _month_words(self, day, full=True):
        """"November 2026", in the reader's own language.

        `strftime` answers in the SERVER's locale, which is C, so a Vietnamese
        reader would be shown "Nov" on a screen where every other word is
        Vietnamese. Babel ships with the platform and knows theirs.
        """
        fmt = 'LLLL y' if full else 'LLL'
        try:
            from babel.dates import format_date
            return format_date(
                day, fmt, locale=(self.env.context.get('lang') or 'en_US'))
        except Exception:                            # noqa: BLE001
            return day.strftime('%B %Y' if full else '%b')

    @api.model
    def _month_state(self, day, today):
        """past | current | future, for the month `day` falls in."""
        if (day.year, day.month) == (today.year, today.month):
            return 'current'
        return 'past' if (day.year, day.month) < (today.year, today.month) \
            else 'future'

    @api.model
    def _payroll_months(self, companies):
        """Every payroll month that exists, oldest to newest, with its people.

        ONE grouped statement over `hr_payslip` and NOTHING ELSE — never a
        join to `hr_payslip_line`. That table is 1.7 GB on the master database
        against 1.9 GB of memory on the box, so any statement the planner
        answers by scanning it costs **12.5 seconds** whether it is warm or
        cold. Measured, 2026-09-09, on payobook: this statement is **32 ms**
        over 28,286 payslips and ten months.

        That is also why a chip's micro bar is HOW MANY PEOPLE were paid
        rather than how much they were paid: the money for the month on screen
        is the headline figure directly above the strip, read once, and asking
        the line table for ten months of it is the twelve-second statement.

        `count(... ) FILTER` carries the same end-of-month restriction as the
        KPI block, so the two never disagree; `all_slips` has no filter, so a
        month that ran only a mid-month advance still appears and says so
        rather than vanishing from the strip.
        """
        self.env.cr.execute("""
            SELECT to_char(p.date_from, 'YYYY-MM') AS mkey,
                   min(p.date_from) AS day,
                   count(DISTINCT p.employee_id) FILTER (WHERE {end_cycle}) AS people,
                   count(*) FILTER (WHERE {end_cycle}) AS slips,
                   count(*) AS all_slips
              FROM hr_payslip p
              LEFT JOIN hr_formula_config fc ON fc.id = p.formula_config_id
             WHERE p.company_id IN %s AND p.date_from IS NOT NULL
             GROUP BY 1
             ORDER BY 1
        """.format(end_cycle=_END_CYCLE), (companies,))
        return self.env.cr.fetchall()

    @api.model
    def _resolve_period(self, asked, months):
        """Which of `months` this board is about. Never None while one exists.

        `months` is `_payroll_months`' output, oldest first, so the default —
        and every fallback — is simply the last of them: the latest month that
        has payroll, which is exactly what this board reported before it could
        name anything.
        """
        from datetime import date as _date
        if not months:
            return None
        keys = [row[0] for row in months]
        raw = str(asked or '').strip()
        wanted = ''
        if raw == 'current':
            wanted = self._today().strftime('%Y-%m')
        elif '..' in raw:
            lo, _sep, hi = raw.partition('..')
            lo = self._as_month_key(lo)
            hi = self._as_month_key(hi)
            if lo and hi:
                if lo > hi:                  # dragged right to left; same span
                    lo, hi = hi, lo
                inside = [k for k in keys if lo <= k <= hi]
                wanted = inside[-1] if inside else ''
        elif raw:
            wanted = self._as_month_key(raw)
        key = wanted if wanted in keys else keys[-1]
        row = months[keys.index(key)]
        day = row[1] or _date.today()
        return {
            'key': key,
            'label': self._month_words(day),
            'short': self._month_words(day, full=False),
            'state': self._month_state(day, self._today()),
            'latest': key == keys[-1],
            'asked': raw,
            # The one thing a reader has to be told when a link did not land
            # where it said it would: it fell back, and it is not an error.
            'fell_back': bool(raw) and key != wanted,
        }

    @api.model
    def _as_month_key(self, raw):
        """`'2026-03'`, or `''` for anything that is not a month at all."""
        key = str(raw or '').strip()
        if key == 'current':
            return self._today().strftime('%Y-%m')
        if len(key) == 7 and key[4] == '-' \
                and key[:4].isdigit() and key[5:].isdigit() \
                and 1 <= int(key[5:]) <= 12:
            return key
        return ''

    @api.model
    def _today(self):
        from odoo import fields
        return fields.Date.context_today(self)

    @api.model
    def _period_kpis(self, companies, key):
        """The money and the headcount for ONE payroll month.

        `ANY(%s)` over the month's own payslip ids, and that is not a stylistic
        choice: handed a bare `p.date_from = <day>` predicate the planner
        sequentially scans all 719,487 payslip lines and the statement takes
        **12.5 seconds** for a real month. Handed the ids it uses the
        `slip_id` index. Measured on payobook for June 2026 (3,852
        end-of-month payslips): **12.5 s -> 2.1 s**, and for a one-payslip
        month **16 ms**, with every figure identical to the digit.
        """
        self.env.cr.execute("""
            SELECT p.id FROM hr_payslip p
              LEFT JOIN hr_formula_config fc ON fc.id = p.formula_config_id
             WHERE p.company_id IN %s
               AND to_char(p.date_from, 'YYYY-MM') = %s
               AND {end_cycle}
        """.format(end_cycle=_END_CYCLE), (companies, key))
        slip_ids = [r[0] for r in self.env.cr.fetchall()]
        if not slip_ids:
            return 0, 0.0, 0.0
        self.env.cr.execute("""
            SELECT count(DISTINCT p.employee_id),
                   coalesce(sum(CASE WHEN pl.code = 'GROSS' THEN pl.total ELSE 0 END), 0),
                   coalesce(sum(CASE WHEN cat.code IN ('INSCO', 'COMP') THEN pl.total ELSE 0 END), 0)
              FROM hr_payslip_line pl
              JOIN hr_payslip p ON p.id = pl.slip_id
              JOIN hr_salary_rule_category cat ON cat.id = pl.category_id
             WHERE pl.slip_id = ANY(%s)
        """, (slip_ids,))
        head, payroll, contributions = self.env.cr.fetchone() or (0, 0.0, 0.0)
        return int(head or 0), float(payroll or 0.0), float(contributions or 0.0)

    @api.model
    def get_dashboard_data(self, period=None):
        env = self.env

        def safe(fn, default=0):
            try:
                return fn()
            except Exception:
                return default

        def optional(model, fn, default=0):
            """Read a model another module owns, or report `default`.

            THE REGISTRY IS THE PROBE, not the module table: what the caller
            needs is for `env[model]` not to raise, and that is exactly what
            this tests. It needs no rights at all, which an
            `ir.module.module` read under superuser did (pb_learn ledger,
            run D1).

            Everything this dashboard reads from pb_learn or from the import
            module goes through here. That is a structural property rather
            than a promise — `tests/test_activation.py::test_04` walks the
            syntax tree of this file and fails if a single one of those reads
            sits outside an `optional()` call.
            """
            if model not in env:
                return default
            return safe(fn, default)

        cdom = [('company_id', 'in', env.companies.ids)]
        employees = safe(lambda: env['hr.employee'].search_count(cdom))
        contracts = (safe(lambda: env['hr.contract'].search_count(cdom + [('state', '=', 'open')]))
                     or safe(lambda: env['hr.contract'].search_count(cdom)))

        # ---- Latest pay run ----
        # NOT company-scoped, and that is a property of the model rather than
        # an oversight: `hr.payslip.run` carries no `company_id` field in this
        # codebase — om_hr_payroll does not declare one and none of the eight
        # modules that inherit it adds one. A `company_id` domain here would
        # raise on every call, which `safe()` would turn into a silent zero.
        runs = safe(lambda: env['hr.payslip.run'].search_count([]))
        run = safe(lambda: env['hr.payslip.run'].search([], order='id desc', limit=1), None)
        run_data = {'name': '—', 'slips': 0, 'done': 0, 'pending': 0, 'readiness': 0, 'state': ''}
        if run:
            # Indexed count-only queries (payslip_run_id is indexed) — never load
            # the run's payslips into memory.
            P = env['hr.payslip']
            total = safe(lambda: P.search_count([('payslip_run_id', '=', run.id)]))
            done = safe(lambda: P.search_count([('payslip_run_id', '=', run.id), ('state', '=', 'done')]))
            pend = safe(lambda: P.search_count([('payslip_run_id', '=', run.id),
                                                ('state', '=', 'verify')]))
            run_data = {
                'name': run.name or '—',
                'slips': total,
                'done': done,
                'pending': pend,
                'readiness': round(done / total * 100) if total else 0,
                'state': run.state or '',
            }

        # ---- Pending approvals ----
        pending = safe(lambda: env['payroll.analytics'].search_count([('state', '=', 'ready')]))
        if not pending:
            pending = safe(lambda: env['hr.payslip'].search_count([('state', '=', 'verify')]))

        # ---- Company KPIs, for the payroll month this board is ABOUT --------
        # Real payslip data, company-scoped, aggregated in SQL rather than read
        # from the legacy analytics snapshot, which can be stale.
        #
        # The month is resolved on the server (rule 3 at the top of this file)
        # and travels back in the payload, so the figures below and the words
        # over them can never disagree. Left alone, it is the latest payroll
        # month — the same month, to the digit, this block reported before it
        # could name one.
        companies = tuple(env.companies.ids) or (env.company.id,)
        payroll = contributions = avg = 0
        headcount = employees
        # A SAVEPOINT, because a failed statement poisons the whole transaction
        # on this platform: without one, a `safe()` that swallowed a SQL error
        # here would leave every later read in this method failing too, and the
        # home page would go blank rather than report honest zeros.
        def sql_safe(fn, default):
            try:
                with env.cr.savepoint():
                    return fn()
            except Exception:                        # noqa: BLE001
                return default

        months = sql_safe(lambda: self._payroll_months(companies), [])
        resolved = safe(lambda: self._resolve_period(period, months), None)
        busiest = max([row[2] for row in months] or [0]) or 0
        periods = [{
            'key': row[0],
            'label': self._month_words(row[1]),
            'short': self._month_words(row[1], full=False),
            # THE YEAR IS ON EVERY CHIP, not only where it changes. This strip
            # runs over whatever months the database has — October 2025 and
            # October 2026 sit eight chips apart on the demo data — and two
            # chips reading "Oct" is the one thing a period control may not do.
            'year': row[1].year,
            'people': int(row[2] or 0),
            'slips': int(row[3] or 0),
            'all_slips': int(row[4] or 0),
            'share': round((row[2] or 0) / busiest * 100, 1) if busiest else 0.0,
            'state': self._month_state(row[1], self._today()),
            'latest': index == len(months) - 1,
        } for index, row in enumerate(months)]
        if resolved:
            hc, payroll, contributions = sql_safe(
                lambda: self._period_kpis(companies, resolved['key']),
                (0, 0.0, 0.0))
            avg = round(payroll / hc) if hc else 0
        # NO FALLBACK. A database with no payslips reports zeros. The legacy
        # analytics-dashboard record used to fill these in, and its figures were
        # a hard-coded sample dict, so a brand-new tenant was shown a company
        # that does not exist (LEARNOS ledger rule 1 — honest zeros). This
        # module must not read that model at all; the phase greps for it.
        # The same holds for the month: with no payslips there are no months,
        # `period` is null, and the screen says so in its own words.

        # ---- Formula engine ----
        cfgs = safe(lambda: env['hr.formula.config'].search([]), None)
        f_count = len(cfgs) if cfgs else 0
        rules = sum(c.rule_count for c in cfgs) if cfgs else 0
        active = len(cfgs.filtered(lambda c: c.state == 'active')) if cfgs else 0
        tests = sum(len(c.test_result_ids) for c in cfgs) if cfgs else 0
        f_health = round(active / f_count * 100) if f_count else 0

        # ---- Presentation context ----
        # The money formatter used to hard-code `₫`. Ship the company's own
        # currency instead; the browser only formats what it is given.
        cur = env.company.currency_id
        currency = {
            'symbol': (cur.symbol if cur else None) or '',
            'position': (cur.position if cur else None) or 'before',
        }
        # ---- Activation checklist (LEARNOS Phase 3) ----
        # FIVE STEPS, FIVE REAL COUNTS. Nothing here is remembered in a flag,
        # inferred from a button press or carried in a browser: every item
        # reports the state of the database, so a step somebody finished in
        # another tab is already ticked when this loads, and a step nobody has
        # done cannot be ticked by pressing its button and coming back.
        #
        # The panel is shown while activation is incomplete and disappears for
        # good once the tenant has a pay run — which is also item 5, so the
        # last tick and the last render are the same event.
        def scenario_state(key):
            """'not_started' | 'in_progress' | 'done', for THIS learner.

            LEARNOS Phase 6 widened this from a boolean. A walkthrough somebody
            STARTED and did not finish used to read here as untouched, so the
            checklist said "Watch the tour" to a person who was four steps into
            it — the one case where the row could tell them something they did
            not already know. One row per learner per key (learn.progress has a
            unique constraint on the pair), so the first row is the answer.
            """
            rows = optional('learn.progress', lambda: env['learn.progress'].search_read(
                [('user_id', '=', env.uid), ('key', '=', SCENARIO_PREFIX + key)],
                ['state'], limit=1))
            return (rows[0]['state'] if rows else None) or 'not_started'

        def scenario_row(item_key, scenario_key):
            state = scenario_state(scenario_key)
            return {'key': item_key, 'done': state == 'done', 'state': state}

        # Is the learning module on this database at all? The same registry
        # probe `optional()` uses, asked once, because it decides whether the
        # two learning steps are OFFERED rather than only whether they can be
        # read. A step whose predicate can never be satisfied is a step that
        # sits unticked forever, which is worse than a shorter list.
        learn_here = 'learn.progress' in env

        # HEADCOUNT > 1, NOT > 0. The golden template ships the admin's
        # `hr.employee` row (id 1, renamed per tenant), and provisioning does
        # not create it — so a tenant that has never added anybody still
        # reports one employee. Contracts carry the "is this tenant empty"
        # question everywhere else in this file for the same reason.
        batches = optional('hr.payroll.import.batch',
                           lambda: env['hr.payroll.import.batch'].search_count(cdom))
        activation_items = []
        if learn_here:
            activation_items.append(scenario_row('meet', SC_WELCOME))
        activation_items.append({'key': 'employee', 'done': employees > 1})
        activation_items.append({'key': 'import', 'done': bool(contracts) or bool(batches)})
        if learn_here:
            activation_items.append(scenario_row('practice', SC_PAYRUN))
        activation_items.append({'key': 'real', 'done': runs > 0})

        return {
            'user': env.user.name or 'there',
            'company': env.company.name or 'Payobook',
            'currency': currency,
            # WHAT THIS BOARD IS ABOUT, and everything it could be about.
            'period': resolved,
            'periods': periods,
            'activation': {'show': not runs, 'items': activation_items},
            'kpis': {
                'headcount': headcount,
                'contracts': contracts,
                'payroll': payroll,
                'contributions': contributions,
                'avg': avg,
                'pending': pending,
            },
            'run': run_data,
            'formula': {'count': f_count, 'rules': rules, 'active': active,
                        'tests': tests, 'health': f_health},
        }
