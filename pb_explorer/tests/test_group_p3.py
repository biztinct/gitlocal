# -*- coding: utf-8 -*-
"""GROUP P3 §6 — "Numbers that remember".

What these tests are actually about, in one line each:

  T1  every fact row remembers its scheme, its money, its division and its
      person, and the new columns were APPENDED (GR4) rather than inserted.
  T2  the total does not change when you slice it a different way.
  T3  a person is one person, even when they were paid twice in a month.
  T4  two currencies are never added together, and a missing rate is said out
      loud instead of guessed (rule 7).
  T5  every converted figure can name the rate and the date it used.
  T6  the breadcrumb round-trips: standing somewhere IS filtering by it.
  T7  a per-person figure is the money divided by the people in the same cell.
  T8  the seven new phrases mean what they say.
  T11 the three old reports no longer count another company's payslips.
  T12 no cockpit falls back to the platform's own error text (GR17).
"""

import os
import re
import unittest

from odoo.tests import common, tagged

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPO = os.path.dirname(HERE)


def _js_files(module):
    root = os.path.join(REPO, module, 'static', 'src', 'js')
    out = []
    for base, _dirs, files in os.walk(root):
        out += [os.path.join(base, f) for f in files if f.endswith('.js')]
    return out


def _strip_comments(src):
    src = re.sub(r'/\*[\s\S]*?\*/', '', src)
    return re.sub(r'//[^\n]*', '', src)


@tagged('post_install', '-at_install')
class TestGroupP3(common.TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        Currency = cls.env['res.currency'].with_context(active_test=False)
        cls.vnd = Currency.search([('name', '=', 'VND')], limit=1)
        cls.sgd = Currency.search([('name', '=', 'SGD')], limit=1)
        if not cls.vnd or not cls.sgd:
            raise unittest.SkipTest(
                'VND and SGD must both exist on this database')
        (cls.vnd | cls.sgd).write({'active': True})

        cls.co_vn = cls.env['res.company'].create({
            'name': 'P3 Vietnam', 'currency_id': cls.vnd.id})
        cls.co_sg = cls.env['res.company'].create({
            'name': 'P3 Singapore', 'currency_id': cls.sgd.id})
        vietnam = cls.env['res.country'].search([('code', '=', 'VN')], limit=1)
        singapore = cls.env['res.country'].search([('code', '=', 'SG')], limit=1)
        cls.co_vn.country_id = vietnam
        cls.co_sg.country_id = singapore

        cls.group = cls.env['pb.group'].create({
            'name': 'P3 Group', 'code': 'P3G',
            'presentation_currency_id': cls.vnd.id,
            'fx_policy': 'month_end',
        })
        (cls.co_vn | cls.co_sg).write({'pb_group_id': cls.group.id})

        # departments, one per company, and a group-level division over both
        cls.dept_vn = cls.env['hr.department'].create({
            'name': 'P3 Retail VN', 'company_id': cls.co_vn.id})
        cls.dept_vn_child = cls.env['hr.department'].create({
            'name': 'P3 Bread', 'company_id': cls.co_vn.id,
            'parent_id': cls.dept_vn.id})
        cls.dept_sg = cls.env['hr.department'].create({
            'name': 'P3 Retail SG', 'company_id': cls.co_sg.id})
        cls.division = cls.env['pb.division'].create({'name': 'P3 Retail'})
        for dept in (cls.dept_vn, cls.dept_sg):
            cls.env['pb.division.link'].create({
                'division_id': cls.division.id,
                'department_id': dept.id,
                'date_from': '2020-01-01',
            })

        # two schemes on the VN company: the salary run and the advance
        cls.scheme_main = cls._mk_config('P3 End Month', 'P3END', 'end_cycle',
                                         cls.co_vn)
        cls.scheme_adv = cls._mk_config('P3 Mid Month', 'P3MID', 'mid_cycle',
                                        cls.co_vn)

        cls.cat_basic = cls._cat('P3 Basic', 'P3BAS', 'basic')
        cls.cat_net = cls._cat('P3 Net', 'P3NET', 'net')
        cls.struct = cls.env['hr.payroll.structure'].create({
            'name': 'P3 Structure', 'code': 'P3STRUCT',
            'company_id': cls.co_vn.id})
        cls.calendar = cls.env['resource.calendar'].create({
            'name': 'P3 Calendar', 'company_id': cls.co_vn.id})
        cls.ctype = cls.env['hr.contract.type'].search([], limit=1) or \
            cls.env['hr.contract.type'].create({'name': 'P3 Type'})

        cls.emp_vn = cls._mk_employee('P3 One', cls.dept_vn_child, cls.co_vn)
        cls.emp_sg = cls._mk_employee('P3 Two', cls.dept_sg, cls.co_sg)

        # August: a salary run and a mid-month advance for the SAME person,
        # plus a Singapore run in Singapore dollars.
        cls.run_main = cls._mk_run('P3 Aug Salary', '2026-08-01', '2026-08-31')
        cls._mk_slip(cls.run_main, cls.emp_vn, 1000.0, 800.0, cls.co_vn,
                     cls.scheme_main)
        cls.run_adv = cls._mk_run('P3 Aug Advance', '2026-08-01', '2026-08-15')
        cls._mk_slip(cls.run_adv, cls.emp_vn, 200.0, 200.0, cls.co_vn,
                     cls.scheme_adv)
        cls.run_sg = cls._mk_run('P3 Aug Singapore', '2026-08-01', '2026-08-31')
        cls._mk_slip(cls.run_sg, cls.emp_sg, 500.0, 400.0, cls.co_sg,
                     False)

        cls.builder = cls.env['pb.fact.builder']
        cls.builder.build_runs([cls.run_main.id, cls.run_adv.id, cls.run_sg.id])

    # ------------------------------------------------------------- helpers
    @classmethod
    def _cat(cls, name, code, ctype):
        return cls.env['hr.salary.rule.category'].create({
            'name': name, 'code': code, 'category_type': ctype})

    @classmethod
    def _mk_config(cls, name, code, cycle, company):
        return cls.env['hr.formula.config'].create({
            'name': name, 'code': code, 'cycle_type': cycle,
            'country_code': 'VN', 'company_id': company.id, 'state': 'active'})

    @classmethod
    def _mk_employee(cls, name, dept, company):
        emp = cls.env['hr.employee'].create({
            'name': name, 'company_id': company.id,
            'department_id': dept.id if dept else False})
        cls.env['hr.contract'].create({
            'name': 'Contract %s' % name, 'employee_id': emp.id,
            'company_id': company.id, 'date_start': '2026-01-01',
            'wage': 1000.0, 'type_id': cls.ctype.id,
            'resource_calendar_id': cls.calendar.id})
        return emp

    @classmethod
    def _mk_run(cls, name, dfrom, dto):
        run = cls.env['hr.payslip.run'].create({
            'name': name, 'date_start': dfrom, 'date_end': dto})
        run.write({'state': 'done'})
        return run

    @classmethod
    def _mk_slip(cls, run, employee, basic, net, company, config):
        contract = cls.env['hr.contract'].search(
            [('employee_id', '=', employee.id)], limit=1)
        vals = {
            'name': 'Slip %s %s' % (employee.name, run.name),
            'employee_id': employee.id,
            'date_from': run.date_start, 'date_to': run.date_end,
            'payslip_run_id': run.id, 'company_id': company.id,
            'struct_id': cls.struct.id, 'contract_id': contract.id,
            # The classic reports only ever look at finished payslips.
            'state': 'done',
        }
        if config and 'formula_config_id' in cls.env['hr.payslip']._fields:
            vals['formula_config_id'] = config.id
        slip = cls.env['hr.payslip'].create(vals)
        for cat, code, amount in ((cls.cat_basic, 'P3BAS', basic),
                                  (cls.cat_net, 'P3NET', net)):
            rule = cls.env['hr.salary.rule'].search(
                [('code', '=', code)], limit=1)
            if not rule:
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
                'condition_select': 'none', 'amount_select': 'fix'})
        return slip

    def _ex(self, companies=None):
        companies = companies or (self.co_vn | self.co_sg)
        return self.env['pb.explorer'].with_context(
            allowed_company_ids=companies.ids).with_company(companies[0])

    def _add_rate(self, currency, day, rate, company=None):
        return self.env['res.currency.rate'].create({
            'currency_id': currency.id, 'name': day, 'rate': rate,
            'company_id': (company or self.co_vn).id})

    # ======================================================= T1 the columns
    def test_01_facts_remember_where_they_came_from(self):
        rows = self.env['pb.fact.emp'].search([
            ('run_id', '=', self.run_main.id)])
        self.assertTrue(rows)
        for row in rows:
            self.assertEqual(row.config_id, self.scheme_main.id,
                             'the scheme did not travel onto the fact row')
            self.assertEqual(row.config_name, self.scheme_main.name)
            self.assertTrue(row.config_version,
                            'a fact row must be able to name its version')
            self.assertEqual(row.currency_id, self.vnd.id)
            self.assertEqual(row.division_id, self.division.id,
                             'the division as at the period end is missing')
            self.assertEqual(row.person_id, row.employee_id.id)
            self.assertEqual(row.fte, 1.0)
            self.assertFalse(row.is_advance)
        advance = self.env['pb.fact.emp'].search([
            ('run_id', '=', self.run_adv.id)])
        self.assertTrue(advance)
        self.assertTrue(all(r.is_advance for r in advance),
                        'a mid-month advance must be flagged as one')

    def test_01b_new_columns_are_appended_last(self):
        """GR4: both consumers read the shared statement POSITIONALLY."""
        builder = self.env['pb.fact.builder']
        self.env.cr.execute(builder._aggregate_sql('line'), ((0,),))
        line_cols = [d[0] for d in self.env.cr.description]
        self.assertEqual(line_cols[-2:], ['config_id', 'is_advance'])
        self.env.cr.execute(builder._aggregate_sql('emp'), ((0,),))
        emp_cols = [d[0] for d in self.env.cr.description]
        self.assertEqual(emp_cols[-2:], ['config_id', 'is_advance'])

    def test_01c_division_follows_the_department_tree(self):
        """An attachment at the top of a branch covers everything under it."""
        self.assertEqual(
            self.env['pb.division'].division_for(
                self.dept_vn_child, '2026-08-31'),
            self.division)

    # ================================================= T2 slicing adds up
    def test_02_every_slicing_gives_the_same_total(self):
        base = {'measure': 'net', 'grain': 'none', 'filters': {},
                'currency': 'own'}
        totals = {}
        for dimension in ('none', 'company_id', 'division_id', 'scheme',
                          'department_id', 'kind'):
            payload = self._ex(self.co_vn).query(
                dict(base, dimension=dimension))
            totals[dimension] = round(sum(
                s['total'] for s in payload['series']), 2)
        self.assertEqual(len(set(totals.values())), 1,
                         'the same money adds to different totals depending '
                         'on how it is sliced: %s' % totals)
        self.assertEqual(totals['none'], 800.0,
                         'the advance must be out of the default view')

    # =========================================== T3 a person is one person
    def test_03_a_person_is_counted_once(self):
        spec = {'measure': 'headcount', 'dimension': 'none', 'grain': 'month'}
        main = self._ex(self.co_vn).query(dict(spec))
        self.assertEqual(main['grand_total'], 1)
        self.assertEqual(main['heads']['people'], 1)
        both = self._ex(self.co_vn).query(dict(spec, advances='all'))
        self.assertEqual(both['grand_total'], 1,
                         'the same person paid an advance and a salary in one '
                         'month must still be one person')
        # …and the money DOES change when the advance is let back in.
        money_main = self._ex(self.co_vn).query(
            {'measure': 'net', 'dimension': 'none', 'grain': 'none'})
        money_all = self._ex(self.co_vn).query(
            {'measure': 'net', 'dimension': 'none', 'grain': 'none',
             'advances': 'all'})
        self.assertEqual(money_main['grand_total'], 800.0)
        self.assertEqual(money_all['grand_total'], 1000.0)

    def test_03b_full_time_equivalents(self):
        payload = self._ex(self.co_vn).query(
            {'measure': 'fte', 'dimension': 'none', 'grain': 'none'})
        self.assertEqual(payload['grand_total'], 1.0)

    # ============================================ T4 / T5 money and rates
    def test_04_two_currencies_are_never_added(self):
        own = self._ex().query({'measure': 'net', 'dimension': 'company_id',
                                'grain': 'none', 'currency': 'own'})
        self.assertTrue(own['mixed'], 'two currencies must stay apart')
        self.assertEqual(len(own['parts']), 2)
        names = {p['currency']['name'] for p in own['parts']}
        self.assertEqual(names, {'VND', 'SGD'})

    def test_04b_a_missing_rate_is_said_out_loud(self):
        payload = self._ex().query({'measure': 'net', 'dimension': 'company_id',
                                    'grain': 'month', 'currency': 'group'})
        money = payload['money']
        self.assertTrue(money['unconverted'],
                        'a currency with no rate must be reported, not dropped')
        missing = money['unconverted'][0]
        self.assertEqual(missing['currency']['name'], 'SGD')
        self.assertTrue(missing['note'], 'a refusal must carry its reason')
        self.assertNotIn('Odoo', missing['note'])
        # …and the total is the converted rows ONLY, never a mixed sum.
        self.assertEqual(payload['grand_total'], 800.0)

    def test_05_a_converted_figure_names_its_rate(self):
        # BOTH sides need a row. A rate between two currencies is one row
        # divided by the other, so pricing only the foreign one answers
        # "nobody has priced this" — which is exactly what the screen said
        # the first time this was tried (ledger GR19).
        self._add_rate(self.vnd, '2026-08-31', 1.0)
        self._add_rate(self.sgd, '2026-08-31', 0.00005)
        payload = self._ex().query({'measure': 'net', 'dimension': 'company_id',
                                    'grain': 'month', 'currency': 'group'})
        money = payload['money']
        self.assertTrue(payload['converted'])
        self.assertTrue(money['rates'], 'a converted figure must name its rate')
        badge = money['rates'][0]
        for key in ('rate', 'rate_date', 'policy', 'src', 'dst', 'period'):
            self.assertIn(key, badge)
        self.assertEqual(badge['policy'], 'month_end',
                         "the badge must report the GROUP's own policy")
        self.assertEqual(badge['dst'], 'VND')
        self.assertFalse(money['unconverted'])
        self.assertGreater(payload['grand_total'], 800.0,
                           'the Singapore money never made it into the total')

    def test_05b_one_currency_never_converts(self):
        payload = self._ex(self.co_vn).query(
            {'measure': 'net', 'dimension': 'company_id', 'grain': 'none'})
        self.assertFalse(payload['converted'])
        self.assertFalse(payload['mixed'])

    # ================================================== T6 the breadcrumb
    def test_06_the_breadcrumb_round_trips(self):
        spec = self._ex().resolve_spec(False, {
            'measure': 'net', 'dimension': 'department_id',
            'path': [{'level': 'company_id', 'key': self.co_vn.id,
                      'label': 'P3 Vietnam'}]})
        self.assertEqual(spec['filters']['company_id'], [self.co_vn.id],
                         'standing somewhere must also filter by it')
        payload = self._ex().query(spec)
        self.assertEqual(payload['trail']['path'][0]['level'], 'company_id')
        self.assertEqual(payload['grand_total'], 800.0,
                         'the Singapore company leaked past the breadcrumb')
        # going back up drops the step AND its filter
        up = self._ex().resolve_spec(False, dict(spec, path=[], filters={}))
        self.assertFalse(up['filters'])
        self.assertEqual(self._ex().query(up)['trail']['path'], [])

    def test_06b_the_trail_only_offers_rungs_that_exist(self):
        trail = self._ex().query({'measure': 'net'})['trail']
        self.assertIn('division_id', trail['levels'])
        self.assertIn('department_id', trail['levels'])
        self.assertTrue(trail['root_label'])
        one = self._ex(self.co_vn).query({'measure': 'net'})['trail']
        self.assertNotIn('country', one['levels'],
                         'one country needs no country rung')

    # ================================================= T7 per person, and
    #                                                    the compare lens
    def test_07_per_person_is_the_money_over_the_people(self):
        cell = self._ex(self.co_vn).query(
            {'measure': 'net', 'dimension': 'scheme', 'grain': 'none',
             'per_head': True})
        self.assertEqual(cell['grand_total'], 800.0,
                         'one person, so per person equals the total')
        self.assertIn('per person', cell['measure_label'].lower())

    def test_07b_the_compare_lens_is_schemes_by_month(self):
        spec = self._ex().resolve_spec('compare', False)
        self.assertEqual(spec['dimension'], 'scheme')
        self.assertEqual(spec['grain'], 'month')
        self.assertEqual(spec['chart'], 'compare')
        payload = self._ex(self.co_vn).query(spec)
        self.assertTrue(payload['ok'])

    def test_07c_export_matches_the_table(self):
        spec = {'measure': 'net', 'dimension': 'scheme', 'grain': 'none'}
        payload = self._ex(self.co_vn).query(spec)
        csv = self._ex(self.co_vn).export_csv(spec)
        self.assertEqual(csv['rows'], len(payload['series']))
        self.assertTrue(csv['csv_b64'])

    # ================================================= T8 ask in English
    def test_08_the_new_phrases_mean_what_they_say(self):
        ex = self._ex()
        cases = [
            ('net pay by scheme', 'dimension', 'scheme'),
            ('cost by division', 'dimension', 'division_id'),
            ('cost by country', 'dimension', 'country'),
        ]
        for text, key, want in cases:
            spec = ex.ask(text)['spec']
            self.assertEqual(spec[key], want, 'phrase %r' % text)
        self.assertEqual(ex.ask('net pay including advances')['spec']['advances'],
                         'all')
        self.assertEqual(ex.ask('net pay main runs only')['spec']['advances'],
                         'main')
        self.assertEqual(
            ex.ask('total cost in group currency')['spec']['currency'], 'group')
        self.assertEqual(
            ex.ask('total cost in its own money')['spec']['currency'], 'own')
        dollars = ex.ask('total cost in dollars')['spec']
        usd = self.env['res.currency'].with_context(
            active_test=False).search([('name', '=', 'USD')], limit=1)
        if usd:
            self.assertEqual(dollars['target_currency'], usd.id)

    # ============================================== T11 the three old reports
    def test_11_the_old_reports_count_one_company(self):
        if 'hr.analytics.personnel.costs' not in self.env:
            self.skipTest('the classic analytics reports are not installed')
        Costs = self.env['hr.analytics.personnel.costs']
        report = Costs.create({
            'period_name': 'August 2026',
            'date_from': '2026-08-01', 'date_to': '2026-08-31',
            'company_id': self.co_vn.id})
        slips = report._get_payslips_for_period()
        self.assertTrue(slips, 'the fixture produced no payslips at all')
        self.assertTrue(all(s.company_id == self.co_vn for s in slips),
                        "another company's payslips are in this report")
        Contrib = self.env['hr.analytics.statutory.contrib']
        contrib = Contrib.create({
            'period_name': 'August 2026',
            'date_from': '2026-08-01', 'date_to': '2026-08-31',
            'country': 'VN', 'company_id': self.co_vn.id})
        slips = contrib._get_payslips_for_period()
        self.assertTrue(all(s.company_id == self.co_vn for s in slips))

    def test_11b_the_employee_drill_down_has_a_company(self):
        if 'hr.payroll.employee.detail' not in self.env:
            self.skipTest('the classic analytics reports are not installed')
        Detail = self.env['hr.payroll.employee.detail']
        self.assertIn('company_id', Detail._fields)
        row = Detail.create({
            'employee_id': self.emp_sg.id,
            'department_id': self.dept_sg.id,
            'month': '2026-08-01'})
        self.assertEqual(row.company_id, self.co_sg)
        self.assertEqual(row.currency_id, self.sgd,
                         "a row of money must be in ITS OWN company's money")

    def test_11c_the_pay_run_board_shows_one_group_of_companies(self):
        board = self.env['pb.payruns'].with_context(
            allowed_company_ids=[self.co_vn.id]).with_company(
            self.co_vn).get_board_data()
        names = {b['name'] for b in board['batches']}
        self.assertIn('P3 Aug Salary', names)
        self.assertNotIn('P3 Aug Singapore', names,
                         "another company's pay run is on this board")
        both = self.env['pb.payruns'].with_context(
            allowed_company_ids=(self.co_vn | self.co_sg).ids).with_company(
            self.co_vn).get_board_data()
        by_name = {b['name']: b for b in both['batches']}
        self.assertEqual(by_name['P3 Aug Singapore']['currency_name'], 'SGD')
        self.assertEqual(by_name['P3 Aug Salary']['currency_name'], 'VND')
        self.assertTrue(both['many_currencies'])

    def test_11d_insights_names_the_money_it_is_showing(self):
        board = self.env['pb.insights'].with_context(
            allowed_company_ids=(self.co_vn | self.co_sg).ids).with_company(
            self.co_vn).get_insights(6)
        self.assertTrue(board['money']['many'])
        self.assertTrue(board['money']['note'])
        self.assertEqual(board['currency'], board['money']['symbol'])

    # ========================================================= T12 GR17
    def test_12_no_cockpit_falls_back_to_the_platform_error(self):
        """The platform's RPC error `.message` is the literal string "Odoo
        Server Error". A ladder that ends on it prints the one word this
        product may never say, in a red box, on the screen."""
        offenders = []
        for module in ('pb_group', 'pb_scheme_map', 'pb_explorer',
                       'pb_insights'):
            for path in _js_files(module):
                code = _strip_comments(open(path, encoding='utf-8').read())
                for match in re.finditer(
                        r'\|\|\s*\(?\s*(?:e|err|error)\s*&&\s*'
                        r'(?:e|err|error)\.message\s*\)?\s*\|\|', code):
                    offenders.append('%s: %s' % (path, match.group(0)))
                for match in re.finditer(
                        r'(?:e|err|error)\.data\?\.message\s*\|\|\s*'
                        r'(?:e|err|error)\.message\b', code):
                    offenders.append('%s: %s' % (path, match.group(0)))
        self.assertFalse(offenders,
                         'GR17 — a fallback to the platform error text:\n%s'
                         % '\n'.join(offenders))

    def test_12b_no_vendor_word_on_screen(self):
        """Nothing a person can read says the vendor's name."""
        offenders = []
        for module in ('pb_explorer',):
            root = os.path.join(REPO, module, 'static', 'src')
            for base, _dirs, files in os.walk(root):
                for name in files:
                    if not name.endswith(('.xml', '.js', '.scss')):
                        continue
                    path = os.path.join(base, name)
                    body = open(path, encoding='utf-8').read()
                    if name.endswith('.xml'):
                        body = re.sub(r'<!--[\s\S]*?-->', '', body)
                    else:
                        body = _strip_comments(body)
                    if 'Odoo' in body:
                        offenders.append(path)
        self.assertFalse(offenders, 'the vendor word is user-visible in %s'
                                    % offenders)
