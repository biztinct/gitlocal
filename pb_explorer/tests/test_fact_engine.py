# -*- coding: utf-8 -*-
"""Phase N §6 — the fact engine and the Explorer facade.

The two tests that matter most are 01 (parity: the fast path and the honest
path return the same numbers) and 02/03 (freshness: a fast answer is never a
stale one). Everything else guards a specific rail from the plan's risk table.
"""

import os

from odoo import fields
from odoo.exceptions import AccessError, UserError
from odoo.tests import common, tagged


@tagged('post_install', '-at_install')
class TestFactEngine(common.TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env['res.company'].create({'name': 'Explorer Co'})
        cls.company_b = cls.env['res.company'].create({'name': 'Explorer Co B'})
        cls.dept = cls.env['hr.department'].create({
            'name': 'Explorer Dept', 'company_id': cls.company.id})
        cls.dept2 = cls.env['hr.department'].create({
            'name': 'Explorer Dept 2', 'company_id': cls.company.id})

        # Categories, one per type we assert on.
        def _cat(name, code, ctype):
            return cls.env['hr.salary.rule.category'].create({
                'name': name, 'code': code, 'category_type': ctype})
        cls.cat_basic = _cat('X Basic', 'XBAS', 'basic')
        cls.cat_net = _cat('X Net', 'XNET', 'net')
        cls.cat_emp_cost = _cat('X Employer', 'XEMP', 'employer_cost')

        cls.struct = cls.env['hr.payroll.structure'].create({
            'name': 'Explorer Structure', 'code': 'XSTRUCT',
            'company_id': cls.company.id})
        # hr_payslip_line.contract_id is NOT NULL on this schema, so every
        # fixture employee needs a real contract.
        cls.calendar = cls.env['resource.calendar'].create({
            'name': 'Explorer Calendar', 'company_id': cls.company.id})
        cls.ctype = cls.env['hr.contract.type'].search([], limit=1) or \
            cls.env['hr.contract.type'].create({'name': 'Explorer Type'})

        cls.emp1 = cls._mk_employee('Explorer One', cls.dept)
        cls.emp2 = cls._mk_employee('Explorer Two', cls.dept)
        cls.emp3 = cls._mk_employee('Explorer Three', cls.dept2)

        cls.april = cls._mk_run('Explorer Run Apr', '2026-04-01', '2026-04-30')
        cls._mk_slip(cls.april, cls.emp1, basic=1000.0, net=800.0, emp_cost=150.0)
        cls._mk_slip(cls.april, cls.emp2, basic=2000.0, net=1600.0, emp_cost=300.0)
        cls._mk_slip(cls.april, cls.emp3, basic=3000.0, net=2400.0, emp_cost=450.0)

        cls.builder = cls.env['pb.fact.builder']
        cls.explorer = cls.env['pb.explorer']

    # ------------------------------------------------------------- helpers
    @classmethod
    def _mk_employee(cls, name, dept, company=None):
        company = company or cls.company
        emp = cls.env['hr.employee'].create({
            'name': name, 'company_id': company.id,
            'department_id': dept.id if dept else False})
        cls.env['hr.contract'].create({
            'name': 'Contract %s' % name,
            'employee_id': emp.id,
            'company_id': company.id,
            'date_start': '2026-01-01',
            'wage': 1000.0,
            'type_id': cls.ctype.id,
            'resource_calendar_id': cls.calendar.id,
        })
        return emp

    @classmethod
    def _mk_run(cls, name, dfrom, dto, state='done'):
        run = cls.env['hr.payslip.run'].create({
            'name': name, 'date_start': dfrom, 'date_end': dto})
        if state != 'draft':
            run.write({'state': state})
        return run

    @classmethod
    def _mk_slip(cls, run, employee, basic, net, emp_cost, company=None):
        company = company or cls.company
        contract = cls.env['hr.contract'].search(
            [('employee_id', '=', employee.id)], limit=1)
        slip = cls.env['hr.payslip'].create({
            'name': 'Slip %s' % employee.name,
            'employee_id': employee.id,
            'date_from': run.date_start, 'date_to': run.date_end,
            'payslip_run_id': run.id, 'company_id': company.id,
            'struct_id': cls.struct.id, 'contract_id': contract.id,
        })
        for cat, code, amount in ((cls.cat_basic, 'XBAS', basic),
                                  (cls.cat_net, 'XNET', net),
                                  (cls.cat_emp_cost, 'XEMP', emp_cost)):
            rule = cls.env['hr.salary.rule'].search([('code', '=', code)], limit=1)
            if not rule:
                # hr.salary.rule has NO struct_id: the structure owns rules
                # through the rule_ids m2m (hr_salary_rule.py:28).
                rule = cls.env['hr.salary.rule'].create({
                    'name': code, 'code': code, 'category_id': cat.id,
                    'sequence': 10, 'condition_select': 'none',
                    'amount_select': 'fix', 'amount_fix': 0.0})
                cls.struct.rule_ids = [(4, rule.id)]
            cls.env['hr.payslip.line'].create({
                'slip_id': slip.id, 'salary_rule_id': rule.id,
                'employee_id': employee.id, 'contract_id': contract.id,
                'name': code, 'code': code, 'category_id': cat.id,
                'sequence': 10, 'amount': amount, 'quantity': 1.0,
                'condition_select': 'none', 'amount_select': 'fix',
            })
        return slip

    def _scoped(self, model=None):
        """Facade pinned to the test company (C18.11/18)."""
        model = model or self.explorer
        return model.with_context(
            allowed_company_ids=[self.company.id]).with_company(self.company)

    # ------------------------------------------------- §6.1 aggregate parity
    def test_01_aggregate_parity(self):
        """The builder's stored facts equal the live aggregate, row for row.

        This is the contract that lets every other read take the fast path:
        if these ever diverge, the Explorer is quietly lying.
        """
        self.builder.build_runs([self.april.id])

        # The honest path: run the SHARED statement directly.
        self.env.cr.execute(self.builder._aggregate_sql('line'),
                            ((self.april.id,),))
        live = {}
        for row in self.env.cr.fetchall():
            # (run, cycle, division, dept, cat, ctype, code, rule, name, amt, ...)
            live[(row[4], row[6], row[7])] = round(float(row[10] or 0.0), 2)

        stored = {}
        for f in self.env['pb.fact.line'].search([('run_id', '=', self.april.id)]):
            stored[(f.department_id.id or None, f.category_type, f.code)] = \
                round(f.amount, 2)

        self.assertTrue(live, "the aggregate returned nothing — fixture is broken")
        self.assertEqual(stored, live,
                         "stored facts diverge from the live aggregate")

    def test_01b_reconciles_to_source(self):
        """Fact totals equal the payslip-line truth they were derived from."""
        self.builder.build_runs([self.april.id])
        self.env.cr.execute("""
            SELECT COALESCE(SUM(pl.total), 0) FROM hr_payslip_line pl
            JOIN hr_payslip p ON p.id = pl.slip_id
            JOIN hr_salary_rule_category c ON c.id = pl.category_id
            WHERE p.payslip_run_id = %s AND c.category_type = 'net'
        """, (self.april.id,))
        source_net = round(float(self.env.cr.fetchone()[0]), 2)
        fact_net = round(sum(self.env['pb.fact.line'].search([
            ('run_id', '=', self.april.id), ('category_type', '=', 'net')
        ]).mapped('amount')), 2)
        self.assertEqual(fact_net, source_net)
        self.assertEqual(fact_net, 4800.0)   # 800 + 1600 + 2400

    # ------------------------------------------------------- §6.2 freshness
    def test_02_stale_facts_rebuild(self):
        """Changing the source moves the token and forces a rebuild."""
        self.builder.build_runs([self.april.id])
        before = sum(self.env['pb.fact.line'].search([
            ('run_id', '=', self.april.id), ('category_type', '=', 'net')
        ]).mapped('amount'))
        self.assertEqual(round(before, 2), 4800.0)

        # A fourth employee joins the run.
        emp4 = self._mk_employee('Explorer Four', self.dept)
        self._mk_slip(self.april, emp4, basic=500.0, net=400.0, emp_cost=75.0)

        ready, pending = self.builder.ensure_fresh([self.april.id])
        self.assertIn(self.april.id, ready)
        self.assertFalse(pending)
        after = sum(self.env['pb.fact.line'].search([
            ('run_id', '=', self.april.id), ('category_type', '=', 'net')
        ]).mapped('amount'))
        self.assertEqual(round(after, 2), 5200.0,
                         "ensure_fresh served stale facts")

    def test_03_empty_run_is_stable(self):
        """A run with no payslips gets a header and does NOT thrash-rebuild.

        Without a token for the empty case every read would rebuild it forever
        — silent, and expensive exactly on the databases with the most runs.
        """
        empty = self._mk_run('Explorer Empty', '2026-05-01', '2026-05-31')
        self.builder.build_runs([empty.id])
        hdr = self.env['pb.fact.run'].search([('run_id', '=', empty.id)])
        self.assertEqual(len(hdr), 1, "empty run must still get a header")
        self.assertTrue(hdr.token, "empty run must carry a token")
        built_at = hdr.built_on

        ready, _p = self.builder.ensure_fresh([empty.id])
        self.assertIn(empty.id, ready)
        hdr2 = self.env['pb.fact.run'].search([('run_id', '=', empty.id)])
        self.assertEqual(hdr2.built_on, built_at,
                         "empty run was rebuilt despite nothing changing")

    # -------------------------------------------- §6.4 R1: the raw sudo write
    def test_04_raw_sudo_state_write_marks_dirty(self):
        """The demo advances runs with a raw sudo write, never the approval
        action (pb_demo/models/demo_history.py:175) — the hook must catch it."""
        draft = self._mk_run('Explorer Draft', '2026-06-01', '2026-06-30',
                             state='draft')
        self._mk_slip(draft, self.emp1, basic=100.0, net=80.0, emp_cost=15.0)
        self.builder.build_runs([draft.id])
        hdr = self.env['pb.fact.run'].search([('run_id', '=', draft.id)])
        self.assertEqual(hdr.basis, 'provisional')
        self.assertFalse(hdr.dirty)

        draft.sudo().write({'state': 'done'})       # the raw path
        self.assertTrue(hdr.dirty, "write hook did not fire on the sudo path")

        self.builder.ensure_fresh([draft.id])
        hdr = self.env['pb.fact.run'].search([('run_id', '=', draft.id)])
        self.assertEqual(hdr.basis, 'approved',
                         "basis did not follow the state change")

    # ------------------------------------- §6.5 R5: history must not move
    def test_05_dimensions_are_as_of_period(self):
        """A later transfer must not rewrite an earlier period's departments.

        `hr_employee.current_version_id` means "right now" (C18.80). Resolving
        dimensions through it would silently restate history on every rebuild,
        so the builder resolves AS OF the period end instead.

        The fixture needs a version that actually predates the period: Odoo
        stamps one version at employee creation (dated today), and
        `hr_version_check_unique_date_version` forbids a second one on the same
        day. With ONLY a today-dated version there is no history to be as-of
        about — the builder then falls back to the earliest version and counts
        it in `asof_fallback_count`, which is the honest answer but not what
        this rail is about.
        """
        january = self.env['hr.version'].create({
            'employee_id': self.emp1.id,
            'department_id': self.dept.id,
            'date_version': '2026-01-01',
        })
        self.assertTrue(january)

        self.env['pb.fact.run'].search([('run_id', '=', self.april.id)]).unlink()
        self.builder.build_runs([self.april.id])
        before = self.env['pb.fact.emp'].search([
            ('run_id', '=', self.april.id), ('employee_id', '=', self.emp1.id)])
        self.assertTrue(before)
        self.assertEqual(before[0].department_id, self.dept,
                         "April should resolve to the January placement")

        # Transfer, effective AFTER the April period.
        self.env['hr.version'].create({
            'employee_id': self.emp1.id,
            'department_id': self.dept2.id,
            'date_version': fields.Date.add(fields.Date.today(), days=1),
        })
        # Rebuild THIS run only: rebuild_all() would re-derive every run in the
        # database, which on a production-sized DB is a 700k-line scan.
        self.env['pb.fact.run'].search([('run_id', '=', self.april.id)]).unlink()
        self.builder.build_runs([self.april.id])
        after = self.env['pb.fact.emp'].search([
            ('run_id', '=', self.april.id), ('employee_id', '=', self.emp1.id)])
        self.assertEqual(after[0].department_id, self.dept,
                         "a later transfer rewrote an April fact row")

    # ------------------------------------------------- §6.6 company scoping
    def test_06_company_scoping(self):
        """Company B's payroll never leaks into company A's answer."""
        run_b = self._mk_run('Explorer Run B', '2026-04-01', '2026-04-30')
        emp_b = self._mk_employee('Explorer B One', False, company=self.company_b)
        self._mk_slip(run_b, emp_b, basic=9999.0, net=9999.0, emp_cost=9999.0,
                      company=self.company_b)

        res = self._scoped().query({'measure': 'net', 'dimension': 'run_id',
                                    'grain': 'none'})
        keys = {s['key'] for s in res['series']}
        self.assertIn(str(self.april.id), keys)
        self.assertNotIn(str(run_b.id), keys,
                         "company B's run leaked into company A's query")

    # ------------------------------------------------------- §6.7 access
    def test_07_access_is_gated(self):
        outsider = self.env['res.users'].create({
            'name': 'Explorer Outsider', 'login': 'explorer_outsider',
            'company_id': self.company.id, 'company_ids': [(4, self.company.id)],
            'group_ids': [(6, 0, [self.env.ref('base.group_user').id])],
        })
        facade = self.env['pb.explorer'].with_user(outsider)
        for call in (lambda: facade.get_schema(),
                     lambda: facade.query({'measure': 'net'}),
                     lambda: facade.drill({'measure': 'net'}),
                     lambda: facade.export_csv({'measure': 'net'})):
            with self.assertRaises(AccessError):
                call()

    # ------------------------------------------ §6.8 the read-only doctrine
    def test_08_facade_never_writes(self):
        """pb.explorer is a reader. The builder is the only writer, and it is
        a different file — asserted at the SOURCE, like pb_insights test_06."""
        here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        with open(os.path.join(here, 'models', 'pb_explorer.py'),
                  encoding='utf-8') as fh:
            source = fh.read()
        for forbidden in ('.write(', '.create(', '.unlink(', '.copy(',
                          'cr.execute("UPDATE', 'cr.execute("INSERT',
                          'cr.execute("DELETE'):
            self.assertNotIn(forbidden, source,
                             "pb.explorer must stay read-only: found %s"
                             % forbidden)

    # ------------------------------------ §6.9 the double-count category error
    def test_09_headcount_by_component_is_refused(self):
        """One employee spans many components, so headcount-by-component would
        count people repeatedly. It must be refused, not answered wrongly."""
        with self.assertRaises(UserError):
            self._scoped().query({'measure': 'headcount', 'dimension': 'code'})

    def test_09b_headcount_is_distinct(self):
        """Headcount is a DISTINCT employee count, never a sum of per-grain
        counts (the pb.fact.line.headcount trap)."""
        self.builder.build_runs([self.april.id])
        res = self._scoped().query({'measure': 'headcount',
                                    'dimension': 'none', 'grain': 'none'})
        self.assertEqual(res['grand_total'], 3.0,
                         "headcount must be 3 distinct employees, not 9 rows")

    # ---------------------------------------------------- §6.10 export cap
    def test_10_export_reports_truncation(self):
        self.builder.build_runs([self.april.id])
        out = self._scoped().export_csv({'measure': 'net',
                                         'dimension': 'department_id'})
        self.assertTrue(out['ok'])
        self.assertIn('csv_b64', out)
        self.assertIn('truncated', out)
        self.assertIn('cap', out)

    # ------------------------------------ §6.11 waterfall reconciliation
    def test_11_waterfall_reconciles_exactly(self):
        """Σ(bars) must equal the headline delta to the cent.

        A variance waterfall whose bars do not add up is worse than no
        waterfall: it looks authoritative and is wrong. The identity is
        Δ = Σ_matched(b−a) + Σ_joiners(b) − Σ_leavers(a), so `residual` is
        structurally zero — this test is what proves the implementation
        matches the identity.
        """
        # A second, later run: one employee leaves, one joins, one gets a rise.
        run2 = self._mk_run('Explorer Run May', '2026-05-01', '2026-05-31')
        self._mk_slip(run2, self.emp1, basic=1200.0, net=960.0, emp_cost=180.0)
        self._mk_slip(run2, self.emp2, basic=2000.0, net=1600.0, emp_cost=300.0)
        joiner = self._mk_employee('Explorer Joiner', self.dept)
        self._mk_slip(run2, joiner, basic=700.0, net=560.0, emp_cost=105.0)
        # emp3 was in April and is absent in May -> a leaver.

        story = self._scoped().narrate({'measure': 'net',
                                        'dimension': 'department_id',
                                        'grain': 'month'})
        w = story['waterfall']
        self.assertTrue(w, "expected a waterfall across two periods")
        self.assertEqual(w['residual'], 0.0,
                         "waterfall does not reconcile: %s" % w)
        self.assertAlmostEqual(
            round(sum(s['value'] for s in w['steps']), 2), w['delta'], 2,
            "the bars do not sum to the headline delta")
        self.assertEqual(w['joiners'], 1)
        self.assertEqual(w['leavers'], 1)
        self.assertEqual(w['matched'], 2)

    def test_11b_single_period_says_why(self):
        """One period cannot explain a movement — say so, do not invent one."""
        story = self._scoped().narrate({
            'measure': 'net', 'grain': 'month',
            'filters': {'run_id': [self.april.id]}})
        self.assertIsNone(story['waterfall'])
        self.assertTrue(story['reason'],
                        "an empty narrative must explain itself")

    # -------------------------------- §6.11c ask() deterministic fallback
    def test_11c_ask_without_llm(self):
        """The ask bar must produce a valid spec with no AI configured (C1),
        and must SHOW which words drove each chip."""
        res = self._scoped().ask('employer cost by department by quarter')
        self.assertTrue(res['ok'])
        self.assertEqual(res['spec']['measure'], 'employer_cost')
        self.assertEqual(res['spec']['dimension'], 'department_id')
        self.assertEqual(res['spec']['grain'], 'quarter')
        chips = {m['chip'] for m in res['matched']}
        self.assertLessEqual({'measure', 'dimension', 'grain'}, chips,
                             "the parser must show its working")

    def test_11d_ask_longest_phrase_wins(self):
        """'cost per head' must not degrade to 'cost'."""
        res = self._scoped().ask('cost per head by department')
        self.assertEqual(res['spec']['measure'], 'cost_per_head')

    # ------------------------------ §6.13 the drill contract (Phase O)
    def test_13_resolve_spec_from_lens_and_spec(self):
        """Both cockpit entry points resolve to a valid spec."""
        by_lens = self._scoped().resolve_spec('statutory', False)
        self.assertEqual(by_lens['measure'], 'statutory')
        self.assertEqual(by_lens['dimension'], 'category_type')

        handed = self._scoped().resolve_spec(False, {
            'measure': 'employer_cost', 'dimension': 'department_id',
            'grain': 'quarter', 'chart': 'column',
            'filters': {'department_id': [self.dept.id]}})
        self.assertEqual(handed['measure'], 'employer_cost')
        self.assertEqual(handed['grain'], 'quarter')
        self.assertEqual(handed['filters']['department_id'], [self.dept.id])

    def test_13b_hostile_spec_degrades(self):
        """A spec arriving from an action context is untrusted input. It must
        degrade to defaults, never raise and never reach SQL uninterpolated."""
        out = self._scoped().resolve_spec(False, {
            'measure': "net'; DROP TABLE hr_payslip; --",
            'dimension': '../../etc/passwd',
            'grain': {'nested': 'junk'},
            'chart': 12345,
            'filters': {'department_id': ['not-an-id'], 'bogus_field': [1]},
        })
        self.assertEqual(out['measure'], 'net')
        self.assertEqual(out['dimension'], 'department_id')
        self.assertEqual(out['grain'], 'month')
        self.assertEqual(out['chart'], 'column')
        self.assertNotIn('bogus_field', out['filters'])
        self.assertNotIn('department_id', out['filters'])   # non-numeric dropped
        # and it still answers
        self.assertTrue(self._scoped().query(out)['ok'])

    def test_13c_unknown_lens_is_safe(self):
        out = self._scoped().resolve_spec('no-such-lens', False)
        self.assertEqual(out['measure'], 'net')

    def test_13d_classic_reports_resolve(self):
        """The classic destinations the retired Insights gallery carried now
        live here; only installed ones are offered."""
        schema = self._scoped().get_schema()
        self.assertIn('classic', schema)
        for rep in schema['classic']:
            self.assertTrue(self.env.ref(rep['xmlid'], raise_if_not_found=False),
                            "an unresolvable classic report was offered")

    # -------------------------------------- optional-column probes (C18)
    def test_14_optional_dimension_columns_exist(self):
        """Every optional column the aggregate names must exist in THIS DB.

        pb_division lives on hr.formula.config only when pb_demo is installed;
        on a customer DB it does not, and the un-probed `fc.pb_division` made
        the whole Explorer answer with `column fc.pb_division does not exist`.
        Executing the aggregate is the honest check — Postgres resolves every
        column name whether or not any row matches.
        """
        builder = self.env['pb.fact.builder']
        for grain in ('line', 'emp'):
            self.env.cr.execute(builder._aggregate_sql(grain), ((0,),))
            self.assertEqual(self.env.cr.fetchall(), [])
        # ...and the coverage query, which shares the same two expressions.
        self.assertEqual(builder._coverage((0,)), {})

    def test_14b_missing_config_column_falls_back_to_the_run(self):
        """With the config column absent, division must come from the run —
        never silently vanish, and never emit an unjoinable `fc.` reference."""
        builder = self.env['pb.fact.builder']
        real = type(builder)._has_config_field

        def _no_division(self, fname):
            return False if fname == 'pb_division' else real(self, fname)

        type(builder)._has_config_field = _no_division
        try:
            self.assertIn('r.pb_division', builder._division_sql())
            self.env.cr.execute(builder._aggregate_sql('line'), ((0,),))
            self.assertEqual(self.env.cr.fetchall(), [])
        finally:
            type(builder)._has_config_field = real

    # ----------------------------------------------- §6.12 self-contained
    def test_12_no_external_assets(self):
        module = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        offenders = []
        static = os.path.join(module, 'static')
        for root, _dirs, files in os.walk(static):
            for name in files:
                path = os.path.join(root, name)
                with open(path, encoding='utf-8', errors='ignore') as fh:
                    body = fh.read()
                if 'http://' in body or 'https://' in body:
                    offenders.append(os.path.relpath(path, module))
        self.assertFalse(offenders,
                         "Explorer assets must be self-contained (no CDN): %s"
                         % offenders)
