# Part of Payobook. See LICENSE file for full copyright and licensing details.
"""Sudima Phase M — the executive analytics facade (``pb.insights``).

Handover §6, cases 1-11:

  1  gates (board / AccessError / bonus tile per tier)
  2  the trend reads the STORED roll-ups — query count flat as runs grow
  3  department split from payslip truth + the ``approx`` contract fallback
  4  statutory employee vs employer split
  5  soft-dep degradation (engine removed from the registry, field removed)
  6  snapshots are company-filtered, and the facade is write-free
  7  the report gallery skips an unresolvable xmlid
  8  multi-company (C18.11/18)
  9  asset self-containment — no external URL anywhere in the module
 10  the analytics menu forest is retired, its actions still resolve
 11  vi.po actually translates (C18.74 markers)

Fixtures are dated 2031 so they sort AHEAD of every real run on the DB the
tests run against (the suite is scoped with ``-u pb_insights`` on the live
Payobook19v2 database, C18.40) — "the latest run" is then deterministically
ours, without touching a single existing record.
"""

import os
from datetime import date
from unittest.mock import patch

from odoo.exceptions import AccessError
from odoo.tests import TransactionCase, tagged



@tagged('post_install', '-at_install')
class TestInsights(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Insights = cls.env['pb.insights']
        cls.Run = cls.env['hr.payslip.run']
        cls.Slip = cls.env['hr.payslip']
        cls.Line = cls.env['hr.payslip.line']

        cls.company_a = cls.env['res.company'].create({'name': 'M Insights Co A'})
        cls.company_b = cls.env['res.company'].create({'name': 'M Insights Co B'})

        Cat = cls.env['hr.salary.rule.category']
        cls.cat_net = Cat.create({'name': 'M NET', 'code': 'NET', 'category_type': 'net'})
        cls.cat_gross = Cat.create({'name': 'M GROSS', 'code': 'GROSS',
                                    'category_type': 'basic'})
        cls.cat_ins = Cat.create({'name': 'M INS', 'code': 'MINS',
                                  'category_type': 'social_security'})
        cls.cat_insco = Cat.create({'name': 'M INSCO', 'code': 'MINSCO',
                                    'category_type': 'employer_cost'})
        cls.rule = cls.env['hr.salary.rule'].create({
            'name': 'M Insights rule', 'code': 'MRULE', 'sequence': 500,
            'category_id': cls.cat_net.id,
        })

        cls.dept_a1 = cls.env['hr.department'].create(
            {'name': 'M Engineering', 'company_id': cls.company_a.id})
        cls.dept_a2 = cls.env['hr.department'].create(
            {'name': 'M Operations', 'company_id': cls.company_a.id})

        # two employees in dept A1, one in A2, one in company B
        cls.emp_1 = cls._employee('M Emp One', cls.company_a, cls.dept_a1)
        cls.emp_2 = cls._employee('M Emp Two', cls.company_a, cls.dept_a1)
        cls.emp_3 = cls._employee('M Emp Three', cls.company_a, cls.dept_a2)
        cls.emp_b = cls._employee('M Emp B', cls.company_b, False)

        # ---- runs. 2031 dates keep them newest on any database ----
        cls.run_old = cls._payrun('M Run Jan', date(2031, 1, 1), date(2031, 1, 31))
        cls._slip(cls.run_old, cls.emp_1, cls.company_a, net=1000, gross=1300)

        cls.run_done = cls._payrun('M Run Feb', date(2031, 2, 1), date(2031, 2, 28))
        cls._slip(cls.run_done, cls.emp_1, cls.company_a,
                  net=1000, gross=1300, ins=-200, insco=150)
        cls._slip(cls.run_done, cls.emp_2, cls.company_a,
                  net=2000, gross=2500, ins=-400, insco=300)
        cls._slip(cls.run_done, cls.emp_3, cls.company_a,
                  net=3000, gross=3600, ins=-600, insco=450)
        cls.run_done.write({'state': 'done'})

        # newest run of all — company B only (multi-company probe)
        cls.run_b = cls._payrun('M Run Mar B', date(2031, 3, 1), date(2031, 3, 31))
        cls._slip(cls.run_b, cls.emp_b, cls.company_b, net=7000, gross=8000)

        cls._settle(cls.run_old | cls.run_done | cls.run_b)

        # ---- users. None of them is a system user (the gate short-circuits) --
        def _user(login, groups):
            return cls.env['res.users'].create({
                'name': login, 'login': login, 'company_id': cls.company_a.id,
                'company_ids': [(6, 0, [cls.company_a.id, cls.company_b.id])],
                'group_ids': [(6, 0, [cls.env.ref(g).id
                                      for g in ['base.group_user'] + list(groups)])],
            })

        cls.u_none = _user('m_ins_none', [])
        cls.u_manager = _user('m_ins_mgr',
                              ['pb_hr_payroll_base.group_payroll_base_manager'])
        cls.u_analytics = _user('m_ins_ana',
                                ['pb_hr_payroll_base.group_payroll_analytics_user'])
        cls.u_payroll = _user('m_ins_pay',
                              ['pb_hr_payroll_base.group_payroll_base_manager',
                               'om_hr_payroll.group_hr_payroll_manager'])

    # ------------------------------------------------------------- helpers
    @classmethod
    def _employee(cls, name, company, department):
        vals = {'name': name, 'company_id': company.id}
        if department:
            vals['department_id'] = department.id
        return cls.env['hr.employee'].create(vals)

    @classmethod
    def _settle(cls, runs):
        """Make the STORED run roll-ups reflect the fixture's payslip lines.

        ``hr.payslip.run._compute_pb_totals`` (pb_payruns) aggregates with RAW
        SQL and does not flush first, so inside one test transaction it can run
        before the lines exist in the database and store zeros. Flush the lines,
        recompute explicitly, flush again. (In production the lines are long
        since flushed by the payroll compute; reported in the Phase-M write-up
        as a robustness note on pb_payruns — not this module's to fix, C18.1.)
        """
        cls.env.flush_all()
        runs._compute_pb_totals()
        cls.env.flush_all()

    @classmethod
    def _payrun(cls, name, date_start, date_end):
        return cls.Run.create({'name': name, 'date_start': date_start,
                               'date_end': date_end})

    @classmethod
    def _contract(cls, employee, company, wage=1000.0):
        # om_hr_payroll makes resource_calendar_id and type_id required
        ctype = cls.env['hr.contract.type'].search([], limit=1) \
            or cls.env['hr.contract.type'].create({'name': 'M Insights type'})
        calendar = company.resource_calendar_id \
            or cls.env['resource.calendar'].search(
                [('company_id', '=', company.id)], limit=1) \
            or cls.env['resource.calendar'].search([], limit=1)
        return cls.env['hr.contract'].create({
            'name': 'C %s' % employee.name, 'employee_id': employee.id,
            'company_id': company.id, 'wage': wage, 'state': 'open',
            'date_start': date(2030, 1, 1), 'type_id': ctype.id,
            'resource_calendar_id': calendar.id,
        })

    @classmethod
    def _slip(cls, payrun, employee, company, net=0.0, gross=0.0, ins=0.0, insco=0.0):
        contract = cls.env['hr.contract'].search(
            [('employee_id', '=', employee.id)], limit=1) \
            or cls._contract(employee, company)
        slip = cls.Slip.create({
            'name': '%s / %s' % (payrun.name, employee.name),
            'employee_id': employee.id, 'company_id': company.id,
            'contract_id': contract.id,
            'date_from': payrun.date_start, 'date_to': payrun.date_end,
            'payslip_run_id': payrun.id,
        })
        for amount, category, code in ((net, cls.cat_net, 'NET'),
                                       (gross, cls.cat_gross, 'GROSS'),
                                       (ins, cls.cat_ins, 'MSIEMP'),
                                       (insco, cls.cat_insco, 'MSICOMP')):
            if not amount:
                continue
            cls.Line.create({
                'name': code, 'code': code, 'category_id': category.id,
                'salary_rule_id': cls.rule.id, 'slip_id': slip.id,
                'employee_id': employee.id, 'contract_id': contract.id,
                'amount': amount, 'quantity': 1.0, 'rate': 100.0,
            })
        return slip

    def _board(self, user, companies=None, **kw):
        """The board as ``user``, scoped to ``companies`` (default: company A)."""
        companies = companies or [self.company_a]
        return self.Insights.with_user(user).with_context(
            allowed_company_ids=[c.id for c in companies]).get_insights(**kw)

    # ------------------------------------------------------------ §6.1 gate
    def test_01_gates(self):
        board = self._board(self.u_manager)
        self.assertIn('hero', board)
        self.assertIn('trend', board)

        # the analytics tier the sidebar item also exposes gets in (C18.9)
        self.assertIn('hero', self._board(self.u_analytics))

        with self.assertRaises(AccessError):
            self._board(self.u_none)

        # bonus tile: absent for the plain base manager, present for the
        # payroll-manager tier (when the Phase-K field is deployed)
        self.assertFalse(board['can_bonus'])
        self.assertIsNone(board['pulse'].get('bonus'))
        pay_board = self._board(self.u_payroll)
        self.assertTrue(pay_board['can_bonus'])
        if 'hr.overtime.request' in self.env \
                and 'bonus_hours' in self.env['hr.overtime.request']._fields:
            self.assertIsInstance(pay_board['pulse'].get('bonus'), dict)

    # ------------------------------------------------- §6.2 stored roll-ups
    def test_02_trend_reads_stored_totals(self):
        board = self._board(self.u_manager, months=24)
        points = {p['id']: p for p in board['trend']['points']}
        self.assertIn(self.run_done.id, points)
        self.assertEqual(points[self.run_done.id]['net'], self.run_done.pb_total_net)
        self.assertEqual(points[self.run_done.id]['gross'], self.run_done.pb_total_gross)
        self.assertEqual(points[self.run_done.id]['count'], self.run_done.pb_employee_count)
        self.assertEqual(points[self.run_done.id]['net'], 6000.0)

        # …and the payload does not grow a query per run: warm the caches, take
        # a baseline, add two more runs, measure again.
        self._board(self.u_manager, months=24)
        before = self.env.cr.sql_log_count
        self._board(self.u_manager, months=24)
        baseline = self.env.cr.sql_log_count - before

        # four extra runs with a +2 tolerance: the old per-run read_group loop
        # costs +1 query/run (+4), so it can no longer squeak under the margin
        # (review M-2 — with two runs the regression passed at the boundary)
        for i in (4, 5, 6, 7):
            extra = self._payrun('M Run Extra %s' % i,
                                 date(2031, i, 1), date(2031, i, 28))
            self._slip(extra, self.emp_1, self.company_a, net=500 * i, gross=600 * i)
            self._settle(extra)
        self._board(self.u_manager, months=24)          # warm the new rows
        before = self.env.cr.sql_log_count
        grown = self._board(self.u_manager, months=24)
        delta = self.env.cr.sql_log_count - before

        self.assertGreater(len(grown['trend']['points']), 5)
        self.assertLessEqual(
            delta, baseline + 2,
            "the trend must not cost a query per run (stored roll-ups): "
            "%s queries with 4 extra runs vs %s before" % (delta, baseline))

    # ------------------------------------------------- §6.3 department split
    def test_03_department_split(self):
        board = self._board(self.u_manager)
        deps = board['departments']
        self.assertFalse(deps['approx'])
        self.assertEqual(deps['basis'], 'payslip')
        self.assertEqual(deps['run_name'], self.run_done.name)
        rows = {r['name']: r for r in deps['rows']}
        # hand-computed: Engineering = 1000 + 2000 over 2 heads, Operations = 3000
        self.assertEqual(rows['M Engineering']['net'], 3000.0)
        self.assertEqual(rows['M Engineering']['count'], 2)
        self.assertEqual(rows['M Engineering']['per_head'], 1500.0)
        self.assertEqual(rows['M Operations']['net'], 3000.0)
        self.assertEqual(rows['M Operations']['count'], 1)

        # no DONE run in the set -> the contract-wage fallback, badged approx
        facade = self.Insights.with_user(self.u_manager).with_context(
            allowed_company_ids=[self.company_a.id]).sudo()
        fallback = facade._departments(self.run_old)
        self.assertTrue(fallback['approx'])
        self.assertEqual(fallback['basis'], 'contract')

    # ---------------------------------------------------- §6.4 statutory
    def test_04_statutory_split(self):
        # scope to the done run by asking for a window it heads
        facade = self.Insights.with_user(self.u_manager).with_context(
            allowed_company_ids=[self.company_a.id]).sudo()
        stat = facade._statutory(self.run_done)
        self.assertEqual(stat['basis'], 'category')
        self.assertEqual(stat['employee'], 1200.0)     # |-200 -400 -600|
        self.assertEqual(stat['employer'], 900.0)      # 150 + 300 + 450
        self.assertEqual(stat['total'], 2100.0)
        legs = {r['code']: r['leg'] for r in stat['rows']}
        self.assertEqual(legs['MSIEMP'], 'employee')
        self.assertEqual(legs['MSICOMP'], 'employer')

    # ------------------------------------------- §6.5 soft-dep degradation
    def test_05_soft_deps_degrade(self):
        facade = self.Insights.with_user(self.u_manager).with_context(
            allowed_company_ids=[self.company_a.id]).sudo()

        models = self.env.registry.models
        engine = 'pb.attendance.exception.engine'
        with patch.dict(models):
            models.pop(engine, None)
            self.assertIsNone(facade._pulse_attendance())
            pulse = facade._pulse()
            self.assertIsNone(pulse['attendance'])
            self.assertIn('leave', pulse)          # the row still renders

        if 'hr.overtime.request' in self.env:
            OT = self.env['hr.overtime.request']
            # `_fields` is a READ-ONLY mappingproxy in Odoo 19 (patch.dict on it
            # raises) — swap the whole attribute for a filtered copy instead.
            without_bonus = {k: v for k, v in OT._fields.items() if k != 'bonus_hours'}
            with patch.object(type(OT), '_fields', without_bonus):
                self.assertIsNone(
                    self.Insights.with_user(self.u_payroll).with_context(
                        allowed_company_ids=[self.company_a.id]).sudo()._pulse_bonus())

        # and the whole board still builds with every pulse model gone
        with patch.dict(models):
            for name in (engine, 'hr.leave', 'hr.overtime.request'):
                models.pop(name, None)
            board = self._board(self.u_manager)
            self.assertEqual(
                [k for k, v in board['pulse'].items() if v is not None], [])
            self.assertIn('hero', board)

    # ------------------------------- §6.6 snapshots scoped + facade read-only
    def test_06_snapshots_scoped_and_facade_is_read_only(self):
        if 'payroll.analytics' not in self.env:
            self.skipTest("payroll_analytics_approval is not installed")
        Analytics = self.env['payroll.analytics']
        snap_a = Analytics.create({
            'period_name': 'M Snapshot A', 'country': 'VN',
            'date_from': self.run_done.date_start, 'date_to': self.run_done.date_end,
            'payslip_run_id': self.run_done.id, 'state': 'approved',
        })
        snap_b = Analytics.create({
            'period_name': 'M Snapshot B', 'country': 'VN',
            'date_from': self.run_b.date_start, 'date_to': self.run_b.date_end,
            'payslip_run_id': self.run_b.id, 'state': 'ready',
        })
        ids_a = {s['id'] for s in self._board(self.u_manager)['snapshots']}
        self.assertIn(snap_a.id, ids_a)
        self.assertNotIn(snap_b.id, ids_a, "company B's snapshot must not leak")

        both = self._board(self.u_manager,
                           companies=[self.company_a, self.company_b])['snapshots']
        self.assertLessEqual({snap_a.id, snap_b.id}, {s['id'] for s in both})

        # the facade never writes — assert it at the SOURCE (safety rail 1)
        here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        with open(os.path.join(here, 'models', 'pb_insights.py'), encoding='utf-8') as fh:
            source = fh.read()
        for forbidden in ('.write(', '.create(', '.unlink(', '.copy(',
                          'cr.execute("UPDATE', 'cr.execute("INSERT',
                          'cr.execute("DELETE'):
            self.assertNotIn(forbidden, source,
                             "pb.insights is a read-only facade: found %s" % forbidden)

    # ---------------------------------- §6.7 every number is a door (Phase O)
    def test_07_gallery_retired(self):
        """The report gallery is gone; only the Explorer availability flag
        remains. The nine cards it held were a verbatim copy of the Explorer's
        own lens grid, so the board shipped a duplicate menu."""
        board = self._board(self.u_manager)
        self.assertNotIn('reports', board,
                         "the report gallery must not come back")
        self.assertIn('explorer', board)
        self.assertIn('available', board['explorer'])

    def test_07b_drill_payloads_carry_ids(self):
        """The board is only clickable if its payload keeps the record ids.

        Every one of these was previously computed and then discarded, which is
        exactly why the tiles were dead click targets.
        """
        board = self._board(self.u_manager)

        # hero: the run behind the headline
        self.assertIn('run_id', board['hero'])

        # departments: a row is either drillable or explicitly marked inert —
        # never a silent no-op on a falsy id
        for row in board['departments'].get('rows', []):
            self.assertIn('drillable', row)
            if row['drillable']:
                self.assertTrue(row['id'])
            else:
                self.assertFalse(row['id'],
                                 "only the unassigned row may be non-drillable")

        # statutory: the legs map lets a click name its own category_type
        stat = board['statutory']
        if stat.get('total'):
            self.assertIn('legs', stat)
            self.assertIn('rows_hidden', stat)
            for row in stat.get('rows', []):
                self.assertIn('category_type', row)

        # snapshots: the RUN id, not just its name — dropping it is what forced
        # the card onto the legacy payroll.analytics form
        for snap in board.get('snapshots', []):
            self.assertIn('run_id', snap)

    def test_07c_pulse_is_drillable(self):
        """Pulse tiles ship ids and per-day series, with the cap surfaced."""
        pulse = self._board(self.u_manager)['pulse']
        att = pulse.get('attendance')
        if att:
            self.assertIn('kind_employees', att)
            self.assertIn('kind_overflow', att, "a truncated drill must say so")
            self.assertIn('by_day', att, "the micro-chart needs a daily series")
            self.assertIn('capped', att)
        leave = pulse.get('leave')
        if leave:
            self.assertIn('density', leave)
            self.assertIn('out_today_ids', leave)
        ot = pulse.get('ot')
        if ot:
            self.assertIn('near_cap_ids', ot,
                          "'N near the ceiling' is only useful if you can see which N")

    # --------------------------------------------------- §6.8 multi-company
    def test_08_multi_company(self):
        only_a = self._board(self.u_manager, companies=[self.company_a])
        self.assertEqual(only_a['hero']['run_name'], self.run_done.name)
        ids_a = {p['id'] for p in only_a['trend']['points']}
        self.assertIn(self.run_done.id, ids_a)
        self.assertNotIn(self.run_b.id, ids_a)

        both = self._board(self.u_manager,
                           companies=[self.company_a, self.company_b])
        ids_both = {p['id'] for p in both['trend']['points']}
        self.assertLessEqual({self.run_done.id, self.run_b.id}, ids_both)
        # company B's run is the newest -> it heads the hero when B is selected
        self.assertEqual(both['hero']['run_name'], self.run_b.name)

    # ------------------------------------------- §6.9 asset self-containment
    def test_09_no_external_assets(self):
        module = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        offenders = []
        for root, _dirs, files in os.walk(os.path.join(module, 'static')):
            for name in files:
                path = os.path.join(root, name)
                with open(path, encoding='utf-8', errors='ignore') as fh:
                    body = fh.read()
                if 'http://' in body or 'https://' in body:
                    offenders.append(os.path.relpath(path, module))
        self.assertFalse(offenders,
                         "Insights assets must be self-contained (no CDN): %s"
                         % offenders)

        # no asset LIST may reference a remote URL either — the live CDN
        # Chart.js was hiding in pb_hr_payroll_base's web.assets_backend, not
        # in a file (it loaded on every backend page, this cockpit included).
        import ast as _ast
        addons = os.path.dirname(module)
        for name in ('pb_insights', 'pb_explorer', 'payroll_analytics_approval',
                     'pb_hr_payroll_analytics', 'pb_hr_payroll_base'):
            manifest = os.path.join(addons, name, '__manifest__.py')
            if not os.path.isfile(manifest):
                continue
            with open(manifest, encoding='utf-8') as fh:
                data = _ast.literal_eval(fh.read())
            for bundle, entries in (data.get('assets') or {}).items():
                for entry in entries:
                    self.assertFalse(
                        str(entry).startswith(('http://', 'https://')),
                        "%s ships a REMOTE asset in %s: %s"
                        % (name, bundle, entry))

        # the cleaned-up sibling must be CDN-free too (handover §1.3)
        sibling = os.path.join(os.path.dirname(module), 'payroll_analytics_approval',
                               'static')
        if os.path.isdir(sibling):
            leftovers = []
            for root, _dirs, files in os.walk(sibling):
                for name in files:
                    path = os.path.join(root, name)
                    with open(path, encoding='utf-8', errors='ignore') as fh:
                        body = fh.read()
                    if 'cdn.' in body or 'https://' in body:
                        leftovers.append(os.path.relpath(path, sibling))
            self.assertFalse(leftovers,
                             "payroll_analytics_approval still ships an external "
                             "asset reference: %s" % leftovers)

    # --------------------------------------------------- §6.10 menu retired
    def test_10_analytics_menu_forest_is_retired(self):
        if not self.env['ir.module.module'].search_count(
                [('name', '=', 'pb_hr_payroll_analytics'), ('state', '=', 'installed')]):
            self.skipTest("pb_hr_payroll_analytics is not installed")
        self.assertFalse(
            self.env.ref('pb_hr_payroll_analytics.menu_hr_analytics_root',
                         raise_if_not_found=False),
            "the analytics menu root must be retired (run -u pb_hr_payroll_analytics)")
        for menu in ('menu_hr_analytics_dashboard', 'menu_hr_analytics_personnel_costs',
                     'menu_hr_analytics_statutory', 'menu_formula_config_analytics'):
            self.assertFalse(
                self.env.ref('pb_hr_payroll_analytics.%s' % menu,
                             raise_if_not_found=False))
        # …while the actions the gallery launches are untouched
        self.assertTrue(self.env.ref(
            'pb_hr_payroll_analytics.action_prepare_hr_analytics_dashboard',
            raise_if_not_found=False))
        self.assertTrue(self.env.ref(
            'pb_hr_payroll_analytics.action_view_hr_analytics_personnel_costs',
            raise_if_not_found=False))

    # ------------------------------------------------------- §6.11 vi.po
    def test_11_vietnamese_translations_load(self):
        from odoo.tools.translate import code_translations
        py = code_translations.get_python_translations('pb_insights', 'vi_VN')
        web = code_translations.get_web_translations('pb_insights', 'vi_VN')
        # C18.74: without the `#. odoo-python` / `#. odoo-javascript` markers a
        # .po file parses fine and translates NOTHING.
        self.assertTrue(py, "vi_VN python translations are empty — missing the "
                            "'#. odoo-python' extracted-comment marker?")
        self.assertTrue(web, "vi_VN web translations are empty — missing the "
                             "'#. odoo-javascript' extracted-comment marker?")
        self.assertIn('Insights is restricted to payroll analytics managers.', py)
