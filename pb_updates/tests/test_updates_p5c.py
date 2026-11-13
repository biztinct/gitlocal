# -*- coding: utf-8 -*-
"""UPDATES P5c — "paid in Payobook" counted honestly (three faults found in P5b,
ledger G85-G87, and the window checks around them).

Every expected number below is worked out BY HAND from the fixture, in the
comment next to it. A company of its own; today frozen at 20 Nov 2026; tax
year 2026; figures before Payobook cover up to 30 Jun 2026 unless said.

Pay schemes (`hr.formula.config`):
  * MONTHLY  month-end (`end_cycle`): GROSS (earning), PIT, SIEMP (deduction,
    written NEGATIVE, like the demo world), SICOMP (employer cost, positive),
    BONUS (earning), TXBASE (information, never printed: stored results
    only), the four inputs that receive figures, ADVIN (the advance received).
  * ADVANCE  mid-month advance (`mid_cycle`), carried to MONTHLY through a
    Mid-Cycle to End-Cycle Mapping row: its GROSS/PIT are working figures.
  * LOOSE    another mid-month advance, linked to nothing.
  * TOPUP    a regular scheme (a bonus / top-up run): GROSS, PIT, BONUS.
  * PLAIN    month-end, GROSS and PIT only — no taxable pay item at all.

Finished payslips are written the way the engine leaves them (one line per
printed pay item, stored results only where the engine kept them), so each
number is exact and nothing depends on a formula.
"""
import base64
import csv
import io
import json
from datetime import date, datetime
from unittest.mock import patch

from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged

try:
    import openpyxl
except ImportError:            # pragma: no cover
    openpyxl = None

NOW = datetime(2026, 11, 20, 3, 0, 0)        # 10:00 in Ho Chi Minh City
COVERS = '2026-06-30'


def csv_b64(rows):
    out = io.StringIO()
    writer = csv.writer(out)
    for row in rows:
        writer.writerow(row)
    return base64.b64encode(out.getvalue().encode('utf-8')).decode()


@tagged('post_install', '-at_install', 'pb_updates', 'pb_updates_p5c')
class TestUpdatesP5c(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        vnd = cls.env.ref('base.VND')
        cls.company = cls.env['res.company'].create(
            {'name': 'P5c Honest Co', 'currency_id': vnd.id})
        cls.company.partner_id.tz = 'Asia/Ho_Chi_Minh'
        cls.env.user.company_ids = [(4, cls.company.id)]
        cls.env.user.company_id = cls.company
        cls.env = cls.env(context=dict(cls.env.context, allowed_company_ids=[cls.company.id]))
        for process in ('records', 'schememap', 'runonly', 'loads'):
            try:
                cls.env['biz.approval.seed'].sudo().set_no_approval_needed(cls.company, process)
            except Exception:   # noqa: BLE001
                pass
        cls.Upd = cls.env['pb.updates.desk']
        cls.Line = cls.env['pb.updates.ytd.line']
        cls.category = cls.env['hr.salary.rule.category'].search([], limit=1)
        cls.team = cls.env['hr.department'].create({'name': 'P5c Team', 'company_id': cls.company.id})
        cls.rules = {}
        cls.monthly = cls._scheme('P5c Monthly', 'P5CMONTH', 'end_cycle', [
            ('GROSS', 'earning'), ('PIT', 'deduction'), ('SIEMP', 'deduction'),
            ('SICOMP', 'employer_cost'), ('BONUS', 'earning'), ('TXBASE', 'info'),
            ('ADVIN', 'deduction'), ('GROSSYTD', 'info'), ('TAXYTD', 'info'), ('TXYTD', 'info'),
            ('MONTHSYTD', 'info')])
        cls.advance = cls._scheme('P5c Advance', 'P5CADV', 'mid_cycle', [
            ('GROSS', 'info'), ('PIT', 'info'), ('SIEMP', 'info'), ('ADV', 'earning')])
        cls.loose = cls._scheme('P5c Loose advance', 'P5CLOOSE', 'mid_cycle', [
            ('GROSS', 'info'), ('ADV', 'earning')])
        cls.topup = cls._scheme('P5c Top-up', 'P5CTOP', 'regular', [
            ('GROSS', 'earning'), ('PIT', 'deduction'), ('BONUS', 'earning')])
        cls.plain = cls._scheme('P5c Plain', 'P5CPLAIN', 'end_cycle', [
            ('GROSS', 'earning'), ('PIT', 'deduction')])
        cls.env['hr.payroll.cycle.component.mapping'].create({
            'mid_cycle_config_id': cls.advance.id, 'end_cycle_config_id': cls.monthly.id,
            'mid_component_id': cls.rules[(cls.advance.id, 'ADV')].id,
            'end_component_id': cls.rules[(cls.monthly.id, 'ADVIN')].id})
        cls.env['hr.formula.scheme.assignment'].create({
            'config_id': cls.monthly.id, 'department_id': cls.team.id, 'cycle_type': 'any'})
        cls.calendar = cls.company.resource_calendar_id or cls.env['resource.calendar'].create(
            {'name': 'P5c Hours', 'company_id': cls.company.id})
        cls.kind = cls.env['hr.contract.type'].search([], limit=1) or cls.env[
            'hr.contract.type'].create({'name': 'P5c Kind'})
        cls.runs = {}
        cls.people = {}
        for code in ('ADA', 'BEN', 'CYD', 'DEE', 'EVE', 'FAY', 'GUS', 'HAL', 'IVY'):
            cls.people[code] = cls._person('DEMO P5c %s' % code.title(), 'P5C' + code)
        cls.env['hr.employee'].browse(cls.people['GUS'].id).write(
            {'date_of_joining': date(2026, 3, 1)} if 'date_of_joining' in cls.env['hr.employee']._fields
            else {})
        P = cls.people
        M, A, L, T, PL = cls.monthly, cls.advance, cls.loose, cls.topup, cls.plain

        def month_end(p, month, gross=100000.0, pit=-10000.0, siemp=-8000.0, sicomp=17500.0,
                      bonus=0.0, txbase=None, config=None):
            values = {'GROSS': gross, 'PIT': pit, 'SIEMP': siemp, 'SICOMP': sicomp, 'BONUS': bonus}
            cfg = config or M
            values = {k: v for k, v in values.items() if (cfg.id, k) in cls.rules}
            fcv = dict(values, TXBASE=txbase) if txbase is not None else None
            return cls._finished(p, cfg, month, values, fcv)

        # ADA — partial taxable pay, a refund month, signs of every kind.
        month_end(P['ADA'], 7)
        month_end(P['ADA'], 8)
        month_end(P['ADA'], 9, txbase=50000.0)
        month_end(P['ADA'], 10, pit=4000.0, txbase=-20000.0)
        # BEN — advance + month-end in July and August, and an August top-up.
        for m in (7, 8):
            cls._finished(P['BEN'], A, m, {'GROSS': 100000.0, 'PIT': -10000.0, 'ADV': 60000.0})
            month_end(P['BEN'], m)
        cls._finished(P['BEN'], T, 8, {'GROSS': 20000.0, 'PIT': -2000.0, 'BONUS': 20000.0},
                      run='P5c August top-up')
        # CYD — month-end only; a clawback in August (BONUS below zero).
        month_end(P['CYD'], 7)
        month_end(P['CYD'], 8, bonus=-5000.0)
        # DEE — an advance that cannot be matched (scheme linked to nothing).
        cls._finished(P['DEE'], L, 7, {'GROSS': 100000.0, 'ADV': 60000.0})
        month_end(P['DEE'], 7)
        # FAY — payslips, no figures before Payobook, no joining date: March, April.
        month_end(P['FAY'], 3)
        month_end(P['FAY'], 4)
        # GUS — same, but joined on 1 March 2026.
        month_end(P['GUS'], 3)
        month_end(P['GUS'], 4)
        # HAL — figures cover up to 15 July; the July payslip straddles it.
        month_end(P['HAL'], 7)
        month_end(P['HAL'], 8)
        # IVY — a July payslip of a scheme WITHOUT a taxable pay item, then
        # August on MONTHLY with its taxable pay stored.
        month_end(P['IVY'], 7, config=PL)
        month_end(P['IVY'], 8, txbase=60000.0)
        cls.Upd.save_ytd_figure('gross', ['GROSS'])
        cls.Upd.save_ytd_figure('taxable', ['TXBASE'])
        cls.Upd.save_ytd_figure('tax', ['PIT'])
        cls.Upd.save_ytd_figure('ee_social', ['SIEMP'])
        cls.Upd.save_ytd_figure('er_social', ['SICOMP'])
        cls.Upd.save_ytd_figure(add_item='BONUS')

    # ------------------------------------------------------------ fixture helpers
    @classmethod
    def _scheme(cls, name, code, cycle, rules):
        config = cls.env['hr.formula.config'].create({
            'name': name, 'code': code, 'cycle_type': cycle, 'country_code': 'VN',
            'company_id': cls.company.id, 'state': 'active'})
        for seq, (rcode, role) in enumerate(rules, start=1):
            money = role != 'info' or rcode in ('GROSS', 'PIT', 'SIEMP')
            cls.rules[(config.id, rcode)] = cls.env['hr.formula.rule'].create({
                'config_id': config.id, 'name': '%s %s' % (name, rcode), 'code': rcode,
                'column_type': 'input', 'sequence': seq, 'default_value': 0.0,
                'value_kind': 'integer' if rcode == 'MONTHSYTD' else 'money', 'net_role': role,
                'appears_on_payslip': money and rcode != 'TXBASE' and not rcode.endswith('YTD'),
                'category_id': cls.category.id})
        return config

    @classmethod
    def _person(cls, name, code):
        employee = cls.env['hr.employee'].create({
            'name': name, 'barcode': code, 'company_id': cls.company.id,
            'work_email': '%s@p5c.example' % code.lower()})
        version = employee.current_version_id if 'current_version_id' in employee._fields else None
        if version and 'department_id' in version._fields:
            version.department_id = cls.team.id
        else:
            employee.department_id = cls.team.id
        cls.env['hr.contract'].create({
            'name': 'P5c contract %s' % name, 'employee_id': employee.id,
            'company_id': cls.company.id, 'wage': 100000.0, 'state': 'open',
            'date_start': '2025-01-01', 'resource_calendar_id': cls.calendar.id,
            'type_id': cls.kind.id})
        return employee

    @classmethod
    def _finished(cls, person, config, month, values, fcv=None, run=None):
        """A FINISHED payslip of `person` on `config` for `month` 2026, its
        lines exactly `values` (pay role from the scheme), stored results
        `fcv` (None: none kept, as on old demo payslips)."""
        ds = date(2026, month, 1)
        de = (date(2026, month + 1, 1) if month < 12 else date(2027, 1, 1)).toordinal() - 1
        de = date.fromordinal(de)
        name = run or '%s %s' % (config.name, ds.strftime('%B'))
        key = (name, config.id)
        if key not in cls.runs:
            cls.runs[key] = cls.env['hr.payslip.run'].create({
                'name': name, 'date_start': ds, 'date_end': de,
                'pb_formula_config_id': config.id})
        contract = cls.env['hr.contract'].search([('employee_id', '=', person.id)], limit=1)
        slip = cls.env['hr.payslip'].create({
            'name': '%s %s' % (name, person.name), 'employee_id': person.id,
            'contract_id': contract.id, 'payslip_run_id': cls.runs[key].id,
            'date_from': ds, 'date_to': de, 'company_id': cls.company.id,
            'formula_config_id': config.id, 'calculation_method': 'formula'})
        lines = []
        for code, amount in values.items():
            rule = cls.rules[(config.id, code)]
            salary_rule = rule._pb_ensure_salary_rule(cls.company)
            lines.append({'slip_id': slip.id, 'name': rule.name, 'code': code,
                          'category_id': cls.category.id, 'amount': amount, 'quantity': 1.0,
                          'rate': 100.0, 'salary_rule_id': salary_rule.id,
                          'contract_id': contract.id, 'employee_id': person.id,
                          'pay_role': rule.net_role})
        cls.env['hr.payslip.line'].create(lines)
        vals = {'state': 'done'}
        if fcv is not None:
            vals['formula_computed_values'] = json.dumps(fcv)
        slip.write(vals)
        return slip

    def setUp(self):
        super().setUp()
        patcher = patch.object(type(self.env['pb.records.apply']), '_records_now',
                               lambda _self: NOW)
        patcher.start()
        self.addCleanup(patcher.stop)

    def cols(self, used):
        return {'used': {str(k): v for k, v in used.items()}, 'identity': {'code': 1},
                'heads': {}}

    def load(self, rows, used, covers=COVERS, name='P5c figures'):
        answer = self.Upd.review(csv_b64(rows), 'p5c.csv', self.cols(used), kind='ytd',
                                 cutover=covers)
        self.assertTrue(answer['ok'], answer.get('msg'))
        res = self.Upd.apply(name, csv_b64(rows), 'p5c.csv', self.cols(used), answer['changes'],
                             {'rows': len(rows) - 1}, kind='ytd', cutover=covers)
        self.assertTrue(res['ok'], res.get('msg'))
        return res

    def standard(self):
        """Figures before Payobook (up to 30 Jun 2026) for ADA, BEN, CYD, DEE,
        EVE; HAL's cover up to 15 Jul 2026."""
        self.load([['Code', 'Gross pay', 'Taxable pay', 'Income tax withheld', 'Months counted'],
                   ['P5CADA', '600000', '300000', '30000', '6'],
                   ['P5CBEN', '500000', '', '', '6'],
                   ['P5CCYD', '500000', '', '', ''],
                   ['P5CDEE', '500000', '', '', ''],
                   ['P5CEVE', '300000', '', '', '6'],
                   ['P5CIVY', '400000', '200000', '', '']],
                  {2: 'y:gross', 3: 'y:taxable', 4: 'y:tax', 5: 'y:months'})
        self.load([['Code', 'Gross pay', 'Months counted'], ['P5CHAL', '650000', '7']],
                  {2: 'y:gross', 3: 'y:months'}, covers='2026-07-15', name='P5c Hal')

    def view(self):
        people = list(self.people.values())
        _figures, rows = self.Upd._ytd_rows(2026, [p.id for p in people])
        return {r['emp_id']: r for r in rows}

    def cell(self, code, key):
        return self.view()[self.people[code].id]['cells'][key]

    def mapping(self, code, figure, basis='before_period'):
        res = self.Upd.save_ytd_map(self.monthly.id, code, figure, basis)
        self.assertTrue(res['ok'], res.get('msg'))

    # ================================================================ fault 1: coverage
    def test_C1_partial_taxable_pay_is_never_a_total(self):
        self.standard()
        c = self.cell('ADA', 'taxable')
        # Four finished MONTHLY payslips (Jul-Oct), the scheme has TXBASE, only
        # September (50,000) and October (-20,000) kept it: 2 of 4.
        self.assertEqual(c['state'], 'partial')
        self.assertEqual((c['have'], c['expected']), (2, 4))
        self.assertEqual(c['paid'], 30000.0, '50,000 + (-20,000), signed')
        self.assertFalse(c['year_total'])
        self.assertEqual(c['chip'], '2 of 4 payslips have this figure')
        self.assertIn('Incomplete: 2 of 4 payslips have this figure', c['note'])
        # P5's code added only those two, as ABS, and showed 370,000 as the total.
        self.assertNotEqual(c['total'], 370000.0)

    def test_C2_a_scheme_without_the_item_is_not_expected_to_carry_it(self):
        self.standard()
        c = self.cell('IVY', 'taxable')
        # July is PLAIN (no taxable pay item): not expected. August MONTHLY kept 60,000.
        self.assertEqual(c['state'], 'complete')
        self.assertEqual((c['have'], c['expected']), (1, 1))
        self.assertEqual(c['total'], 260000.0, '200,000 before + 60,000')
        self.assertTrue(c['year_total'])
        self.assertEqual(c['note'], 'Complete')

    def test_C3_partial_coverage_refuses_a_pay_run_and_the_download(self):
        self.standard()
        self.mapping('TXYTD', 'taxable')
        plan = self.Line.sudo()._plan_for_slip(self.people['ADA'], self.monthly, '2026-11-01',
                                               '2026-11-30')
        self.assertEqual(plan['TXYTD']['incomplete'], 'partial')
        self.assertTrue(self.Line._plan_blocked(plan['TXYTD']))
        run = self.env['hr.payslip.run'].create({
            'name': 'P5c November', 'date_start': '2026-11-01', 'date_end': '2026-11-30',
            'pb_formula_config_id': self.monthly.id})
        contract = self.env['hr.contract'].search([('employee_id', '=', self.people['ADA'].id)])
        slip = self.env['hr.payslip'].create({
            'name': 'P5c Nov Ada', 'employee_id': self.people['ADA'].id, 'contract_id': contract.id,
            'payslip_run_id': run.id, 'date_from': '2026-11-01', 'date_to': '2026-11-30',
            'company_id': self.company.id, 'formula_config_id': self.monthly.id,
            'calculation_method': 'formula'})
        with self.assertRaises(UserError) as caught:
            slip.compute_sheet()
        self.assertIn('only 2 of the 4 finished payslips', str(caught.exception))
        dl = self.Upd.download_for_payrun(self.monthly.id, '2026-11-01')
        self.assertTrue(dl['ok'], dl.get('msg'))
        wb = openpyxl.load_workbook(io.BytesIO(base64.b64decode(dl['file_b64'])))
        ws = wb.worksheets[0]
        heads = [c.value for c in ws[1]]
        ada = next(r for r in ws.iter_rows(min_row=2, values_only=True) if r[0] == 'P5CADA')
        col = next(i for i, h in enumerate(heads) if h and '(TXYTD)' in h)
        self.assertIn(ada[col], (None, ''), 'no number that looks like a total')
        self.assertIn('only 2 of 4 finished payslips have this figure', ada[-1])
        adj = [r for r in wb.worksheets[1].iter_rows(min_row=2, values_only=True)
               if r[0] == self.people['ADA'].id]
        self.assertFalse(adj, 'left out of Monthly adjustments')

    def test_C4_view_download_marks_incomplete(self):
        self.standard()
        dl = self.Upd.download_ytd_view(2026)
        wb = openpyxl.load_workbook(io.BytesIO(base64.b64decode(dl['file_b64'])))
        ws = wb.active
        heads = [c.value for c in ws[1]]
        self.assertIn('Taxable pay · complete?', heads)
        ada = next(r for r in ws.iter_rows(min_row=2, values_only=True) if r[0] == 'P5CADA')
        total = ada[heads.index('Taxable pay · total')]
        marker = ada[heads.index('Taxable pay · complete?')]
        self.assertIn(total, (None, ''), 'an incomplete total is not written as one')
        self.assertIn('Incomplete: 2 of 4 payslips have this figure', marker)
        self.assertEqual(ada[heads.index('Gross pay · total')], 1000000.0)
        self.assertEqual(ada[heads.index('Gross pay · complete?')], 'Complete')

    # ================================================================ fault 2: sign
    def test_S1_signs_of_every_kind(self):
        self.standard()
        ada = self.view()[self.people['ADA'].id]['cells']
        # Gross (earning): 4 x 100,000.
        self.assertEqual(ada['gross']['paid'], 400000.0)
        # Tax withheld (deduction, this scheme writes it NEGATIVE): 3 x 10,000
        # taken, then a 4,000 refund in October (positive = the opposite sign)
        # reduces the year: 30,000 - 4,000 = 26,000. P5's ABS read 34,000.
        self.assertEqual(ada['tax']['paid'], 26000.0)
        self.assertEqual(ada['tax']['total'], 56000.0, '30,000 before + 26,000')
        self.assertTrue(ada['tax']['below_zero'], 'the refund month is shown')
        # Employee contributions (deduction, negative): 4 x 8,000 = 32,000.
        self.assertEqual(ada['ee_social']['paid'], 32000.0)
        # Employer contributions (employer cost, positive): 4 x 17,500 = 70,000.
        self.assertEqual(ada['er_social']['paid'], 70000.0)
        # Taxable pay (information): signed, the October month below zero shown.
        self.assertTrue(ada['taxable']['below_zero'])
        self.assertIn('Includes a month below zero (October 2026)', ada['taxable']['note'])
        # A pay item as its own figure (earning): CYD's August clawback -5,000.
        cyd = self.cell('CYD', 'BONUS')
        self.assertEqual(cyd['paid'], -5000.0)
        self.assertTrue(cyd['below_zero'])

    def test_S2_a_positive_convention_scheme_keeps_its_sign(self):
        # TOPUP writes PIT negative too; an employer cost is positive: both are
        # amounts. A scheme with no clear usual sign falls back to the size.
        L = self.Line.sudo()
        ledger = L._ledger([self.people['BEN'].id], date(2026, 1, 1), date(2026, 12, 31),
                           ['PIT', 'SICOMP'])
        self.assertEqual(ledger['conv'][(self.monthly.id, 'PIT')], -1)
        self.assertEqual(ledger['conv'][(self.monthly.id, 'SICOMP')], 1)

    # ================================================================ fault 3: once
    def test_D1_advance_and_month_end_count_once_top_up_still_counts(self):
        self.standard()
        ben = self.view()[self.people['BEN'].id]['cells']
        # July and August: the month-end 100,000 each (the advances' 100,000
        # are working figures of the same month), plus the August top-up
        # 20,000: 220,000. P5 counted 420,000.
        self.assertEqual(ben['gross']['paid'], 220000.0)
        self.assertEqual(ben['gross']['total'], 720000.0)
        self.assertEqual(ben['gross']['state'], 'complete')
        self.assertEqual(ben['months']['paid'], 2.0, 'July, August — each month once')
        self.assertEqual(ben['months']['total'], 8.0)
        # Tax: month-end 10,000 x 2 + top-up 2,000 = 22,000.
        self.assertEqual(ben['tax']['paid'], 22000.0)

    def test_D2_only_month_end(self):
        self.standard()
        cyd = self.cell('CYD', 'gross')
        self.assertEqual((cyd['paid'], cyd['total'], cyd['state']), (200000.0, 700000.0, 'complete'))

    def test_D3_an_advance_that_cannot_be_matched_is_shown_apart(self):
        self.standard()
        dee = self.cell('DEE', 'gross')
        self.assertEqual(dee['state'], 'split')
        self.assertEqual(dee['paid'], 100000.0, 'the month-end payslip only')
        self.assertEqual(dee['advance'], 100000.0, 'the advance, apart')
        self.assertFalse(dee['year_total'])
        self.assertTrue(dee['advance_label'])
        self.mapping('GROSSYTD', 'gross')
        plan = self.Line.sudo()._plan_for_slip(self.people['DEE'], self.monthly, '2026-08-01',
                                               '2026-08-31')
        self.assertEqual(plan['GROSSYTD']['incomplete'], 'split')
        sentence = self.Line._gap_sentence(self.people['DEE'], dict(plan['GROSSYTD'],
                                                                    item_label='Gross so far'))
        self.assertIn('Mid-Cycle to End-Cycle Mapping', sentence)

    def test_D4_advance_only_month_is_not_counted(self):
        # A finished advance with no finished month-end payslip: not counted,
        # and the month is not a month counted.
        self._finished(self.people['CYD'], self.advance, 9, {'GROSS': 100000.0, 'ADV': 60000.0})
        self.standard()
        cyd = self.view()[self.people['CYD'].id]['cells']
        self.assertEqual(cyd['gross']['paid'], 200000.0)

    def test_D5_same_scheme_same_period_twice_is_counted_and_said(self):
        # A second finished July payslip of MONTHLY for CYD (another run, same
        # dates): real pay or a test nobody cancelled — counted, never quietly.
        self._finished(self.people['CYD'], self.monthly, 7, {'GROSS': 100000.0}, run='P5c July again')
        self.standard()
        row = self.view()[self.people['CYD'].id]
        self.assertEqual(row['cells']['gross']['paid'], 300000.0, '100,000 x 2 in July + August')
        self.assertEqual(row['twice_labels'], ['July 2026'])
        self.assertIn('Two finished payslips of the same pay scheme and pay period in July 2026',
                      row['cells']['gross']['note'])
        self.assertEqual(row['cells']['months']['paid'], 2.0, 'July once')
        self.mapping('GROSSYTD', 'gross')
        plan = self.Line.sudo()._plan_for_slip(self.people['CYD'], self.monthly, '2026-09-01',
                                               '2026-09-30')
        self.assertEqual(plan['GROSSYTD']['twice'], ['2026-07-01'])
        self.assertFalse(self.Line._plan_blocked(plan['GROSSYTD']))

    # ================================================================ the window
    def test_W1_before_this_period_and_months_including_it(self):
        self.standard()
        self.mapping('GROSSYTD', 'gross')
        self.mapping('TAXYTD', 'tax')
        self.mapping('MONTHSYTD', 'months', 'with_period')
        plan = self.Line.sudo()._plan_for_slip(self.people['ADA'], self.monthly, '2026-11-01',
                                               '2026-11-30')
        # 600,000 + Jul..Oct 400,000.
        self.assertEqual(plan['GROSSYTD']['value'], 1000000.0)
        # 30,000 + 26,000 (signed refund).
        self.assertEqual(plan['TAXYTD']['value'], 56000.0)
        # 6 + Jul, Aug, Sep, Oct + November itself = 11.
        self.assertEqual(plan['MONTHSYTD']['value'], 11.0)
        self.assertFalse(any(self.Line._plan_blocked(i) for i in plan.values()))
        # October's period: only Jul..Sep before it — 600,000 + 300,000.
        plan = self.Line.sudo()._plan_for_slip(self.people['ADA'], self.monthly, '2026-10-01',
                                               '2026-10-31')
        self.assertEqual(plan['GROSSYTD']['value'], 900000.0)
        self.assertEqual(plan['MONTHSYTD']['value'], 10.0, '6 + 3 + October')
        # BEN, November: 500,000 + 220,000 (advances not added, top-up added).
        plan = self.Line.sudo()._plan_for_slip(self.people['BEN'], self.monthly, '2026-09-01',
                                               '2026-09-30')
        self.assertEqual(plan['GROSSYTD']['value'], 720000.0)
        self.assertEqual(plan['MONTHSYTD']['value'], 9.0, '6 + Jul, Aug + September')

    def test_W2_a_payslip_straddling_covers_up_to(self):
        self.standard()
        hal = self.view()[self.people['HAL'].id]['cells']
        # Figures cover up to 15 Jul; the July payslip (1-31 Jul) overlaps them.
        self.assertEqual(hal['gross']['state'], 'overlap')
        self.assertEqual(hal['gross']['paid'], 100000.0, 'August only')
        self.assertFalse(hal['gross']['year_total'])
        # Months: 7 before + August (July is already in the figures) = 8.
        self.assertEqual(hal['months']['paid'], 1.0)
        self.mapping('GROSSYTD', 'gross')
        plan = self.Line.sudo()._plan_for_slip(self.people['HAL'], self.monthly, '2026-09-01',
                                               '2026-09-30')
        self.assertEqual(plan['GROSSYTD']['incomplete'], 'overlap')
        sentence = self.Line._gap_sentence(self.people['HAL'], dict(plan['GROSSYTD'],
                                                                    item_label='Gross so far'))
        self.assertIn('overlaps the figures before Payobook', sentence)
        self.assertIn('15 Jul 2026', sentence)

    def test_W3_opening_figures_and_no_payslips(self):
        self.standard()
        eve = self.cell('EVE', 'gross')
        self.assertEqual((eve['state'], eve['total'], eve['year_total']), ('none', 300000.0, True))
        self.mapping('GROSSYTD', 'gross')
        L = self.Line.sudo()
        # July (the first Payobook period): nothing in between — 300,000.
        plan = L._plan_for_slip(self.people['EVE'], self.monthly, '2026-07-01', '2026-07-31')
        self.assertEqual(plan['GROSSYTD']['value'], 300000.0)
        self.assertFalse(L._plan_blocked(plan['GROSSYTD']))
        # August: July has no finished payslip — refused, never 300,000.
        plan = L._plan_for_slip(self.people['EVE'], self.monthly, '2026-08-01', '2026-08-31')
        self.assertTrue(plan['GROSSYTD']['gap'])
        self.assertTrue(L._plan_blocked(plan['GROSSYTD']))

    def test_W4_payslips_and_no_opening_figures(self):
        self.standard()
        rows = self.view()
        fay = rows[self.people['FAY'].id]
        # No figures, no joining date, payslips from March: January and
        # February are not covered — not a year total.
        self.assertEqual(fay['start_missing'], 2)
        self.assertEqual(fay['cells']['gross']['paid'], 200000.0)
        self.assertFalse(fay['cells']['gross']['year_total'])
        self.assertIn('no figures before Payobook for January 2026 to February 2026',
                      fay['cells']['gross']['note'])
        gus = rows[self.people['GUS'].id]
        if 'date_of_joining' in self.env['hr.employee']._fields:
            # Joined 1 March: March and April are the whole year so far.
            self.assertEqual(gus['start_missing'], 0)
            self.assertTrue(gus['cells']['gross']['year_total'])
        # Download for the pay run names a person without figures, no value.
        self.mapping('GROSSYTD', 'gross')
        dl = self.Upd.download_for_payrun(self.monthly.id, '2026-11-01')
        wb = openpyxl.load_workbook(io.BytesIO(base64.b64decode(dl['file_b64'])))
        fay_row = next(r for r in wb.worksheets[0].iter_rows(min_row=2, values_only=True)
                       if r[0] == 'P5CFAY')
        self.assertIn('No figures before Payobook for 2026', fay_row[-1])

    # ================================================================ how it was worked out
    def test_H1_how_this_number_was_worked_out(self):
        self.standard()
        d = self.Upd.get_ytd_cell_detail(2026, self.people['BEN'].id, 'gross')
        self.assertTrue(d['ok'], d.get('msg'))
        self.assertEqual(len(d['counted']), 3, 'two month-end payslips and the top-up')
        top = next(i for i in d['counted'] if i['run'] == 'P5c August top-up')
        self.assertIn('20,000', top['amount'])
        self.assertIn('720,000', d['total_label'])
        reasons = [i['why'] for i in d['left']]
        self.assertEqual(len(d['left']), 2, 'two advances')
        self.assertTrue(all('Mid-month advance' in w for w in reasons))
        d = self.Upd.get_ytd_cell_detail(2026, self.people['ADA'].id, 'taxable')
        missing = [i for i in d['counted'] if i.get('missing')]
        self.assertEqual(len(missing), 2, 'July and August do not have it')
        self.assertFalse(d['year_total'])
        # A person nobody may see / a wrong year: refused quietly.
        self.assertFalse(self.Upd.get_ytd_cell_detail(2019, self.people['BEN'].id, 'gross')['ok'])

    def test_H2_view_speed_shape(self):
        self.standard()
        view = self.Upd.get_ytd_view(2026)
        self.assertTrue(view['ok'])
        self.assertGreaterEqual(view['open_people'], 3, 'Ada, Dee, Hal at least')
        rows = {r['emp_id']: r for r in view['rows']}
        self.assertTrue(rows[self.people['BEN'].id]['cells']['gross']['detail'])

    def test_H3_no_vendor_name_in_new_strings(self):
        self.standard()
        texts = []
        for code in self.people:
            for c in self.view()[self.people[code].id]['cells'].values():
                texts += [c.get('note') or '', c.get('chip') or '', c.get('below_note') or '']
        for code in ('ADA', 'BEN', 'DEE', 'HAL'):
            d = self.Upd.get_ytd_cell_detail(2026, self.people[code].id, 'gross')
            texts += [i['why'] for i in d['counted'] + d['left']] + [d.get('note') or '']
        self.assertFalse([t for t in texts if 'odoo' in t.lower()])
