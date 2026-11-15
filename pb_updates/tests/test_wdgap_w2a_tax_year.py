# -*- coding: utf-8 -*-
"""WDGAP W2-A — the Updates year-to-date sheet and the employee tax sheet
follow the pay scheme's tax year.

Numbered as in the report (`docs/handovers/wdgap/WDGAP_W2_A_REPORT.md`):

  U1  a sheet of figures before Payobook stores each person's tax year by
      their own scheme: April scheme → 2026–27 (start month kept on the row),
      January scheme → 2026 with NO month stored (a row as before W2-A)
  U2  `_plan_for_slip` under an April start: figures + paid in Payobook
      counted from 1 April; a payslip of the previous tax year never counts
  U3  joined this tax year (D31) follows the tax year: joined in February
      is LAST tax year for an April scheme
  U4  a calendar row never feeds an April scheme (another tax year)
  U5  the year-to-date view reads each person's own tax year
  U6  R1 — every January answer is the calendar answer (home, view, plan,
      download wording); old rows keep their meaning (label computed)
  U7  the employee tax sheet: April → "Tax year 2026–27", totals Apr..May;
      January → "YTD 2026", totals Jan..May (byte-for-byte the old sums)
"""
import base64
import csv
import io
import json
import re
from datetime import date, datetime
from unittest.mock import patch

from odoo.tests import HttpCase, TransactionCase, tagged

NOW = datetime(2026, 11, 20, 3, 0, 0)
COVERS = '2026-06-30'
PASSWORD = 'W2a-tax-sheet-2026!'


def csv_b64(rows):
    out = io.StringIO()
    writer = csv.writer(out)
    for row in rows:
        writer.writerow(row)
    return base64.b64encode(out.getvalue().encode('utf-8')).decode()


def month_end(first):
    nxt = date(first.year + (first.month == 12), first.month % 12 + 1, 1)
    return date.fromordinal(nxt.toordinal() - 1)


class W2aFixture:
    """A company of its own with an April scheme and a January scheme, each
    assigned to its own team (the scheme map answers who is on which)."""

    @classmethod
    def _w2a_world(cls):
        vnd = cls.env.ref('base.VND')
        cls.company = cls.env['res.company'].create({'name': 'W2A Tax Year Co',
                                                     'currency_id': vnd.id})
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
        cls.calendar = cls.company.resource_calendar_id or cls.env['resource.calendar'].create(
            {'name': 'W2A Hours', 'company_id': cls.company.id})
        cls.rules, cls.runs = {}, {}
        cls.april = cls._scheme('W2A April scheme', 'W2AAPRIL', '4')
        cls.jan = cls._scheme('W2A January scheme', 'W2AJAN', '1')
        cls.team_apr = cls.env['hr.department'].create({'name': 'W2A April team',
                                                        'company_id': cls.company.id})
        cls.team_jan = cls.env['hr.department'].create({'name': 'W2A January team',
                                                        'company_id': cls.company.id})
        for config, team in ((cls.april, cls.team_apr), (cls.jan, cls.team_jan)):
            cls.env['hr.formula.scheme.assignment'].create({
                'config_id': config.id, 'department_id': team.id, 'cycle_type': 'any'})

    @classmethod
    def _scheme(cls, name, code, month):
        config = cls.env['hr.formula.config'].create({
            'name': name, 'code': code, 'cycle_type': 'end_cycle', 'country_code': 'VN',
            'company_id': cls.company.id, 'state': 'active', 'tax_year_start_month': month})
        for seq, (rcode, role) in enumerate((('GROSS', 'earning'), ('PIT', 'deduction'),
                                             ('GROSSYTD', 'info'), ('TAXYTD', 'info')), start=1):
            cls.rules[(config.id, rcode)] = cls.env['hr.formula.rule'].create({
                'config_id': config.id, 'name': '%s %s' % (name, rcode), 'code': rcode,
                'column_type': 'input', 'sequence': seq, 'default_value': 0.0,
                'value_kind': 'money', 'net_role': role,
                'appears_on_payslip': not rcode.endswith('YTD'), 'category_id': cls.category.id})
        return config

    @classmethod
    def _person(cls, name, code, team, joined=False, user=None):
        vals = {'name': name, 'barcode': code, 'company_id': cls.company.id,
                'work_email': '%s@w2a.example' % code.lower()}
        if 'date_of_joining' in cls.env['hr.employee']._fields:
            vals['date_of_joining'] = joined
        if user:
            vals['user_id'] = user.id
        employee = cls.env['hr.employee'].create(vals)
        version = employee.current_version_id if 'current_version_id' in employee._fields else None
        if version and 'department_id' in version._fields:
            version.department_id = team.id
        else:
            employee.department_id = team.id
        cls.env['hr.contract'].create({
            'name': 'W2A contract %s' % name, 'employee_id': employee.id,
            'company_id': cls.company.id, 'wage': 100000.0, 'state': 'open',
            'date_start': '2025-01-01', 'resource_calendar_id': cls.calendar.id})
        return employee

    @classmethod
    def _finished(cls, person, config, first, gross=100000.0, pit=-10000.0):
        last = month_end(first)
        key = (config.id, first)
        if key not in cls.runs:
            cls.runs[key] = cls.env['hr.payslip.run'].create({
                'name': '%s %s' % (config.name, first), 'date_start': first, 'date_end': last,
                'pb_formula_config_id': config.id})
        contract = cls.env['hr.contract'].search([('employee_id', '=', person.id)], limit=1)
        slip = cls.env['hr.payslip'].create({
            'name': 'W2A %s %s' % (person.name, first), 'employee_id': person.id,
            'contract_id': contract.id, 'payslip_run_id': cls.runs[key].id,
            'date_from': first, 'date_to': last, 'company_id': cls.company.id,
            'formula_config_id': config.id, 'calculation_method': 'formula'})
        lines = []
        for code, amount in (('GROSS', gross), ('PIT', pit)):
            rule = cls.rules[(config.id, code)]
            salary_rule = rule._pb_ensure_salary_rule(cls.company)
            lines.append({'slip_id': slip.id, 'name': rule.name, 'code': code,
                          'category_id': cls.category.id, 'amount': amount, 'quantity': 1.0,
                          'rate': 100.0, 'salary_rule_id': salary_rule.id,
                          'contract_id': contract.id, 'employee_id': person.id,
                          'pay_role': rule.net_role})
        cls.env['hr.payslip.line'].create(lines)
        slip.write({'state': 'done'})
        return slip


@tagged('post_install', '-at_install', 'pb_updates', 'wdgap_w2a')
class TestW2aUpdatesTaxYear(W2aFixture, TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._w2a_world()
        P = cls.people = {}
        P['AMY'] = cls._person('DEMO W2A Amy', 'W2AAMY', cls.team_apr, joined=date(2024, 3, 1))
        P['BOB'] = cls._person('DEMO W2A Bob', 'W2ABOB', cls.team_jan, joined=date(2024, 3, 1))
        P['CAT'] = cls._person('DEMO W2A Cat', 'W2ACAT', cls.team_apr, joined=date(2026, 5, 1))
        P['DAN'] = cls._person('DEMO W2A Dan', 'W2ADAN', cls.team_apr, joined=date(2026, 2, 1))
        # AMY / BOB: a whole run of months, Jan..Oct 2026, 100,000 a month.
        for code in ('AMY', 'BOB'):
            config = cls.april if code == 'AMY' else cls.jan
            for m in range(1, 11):
                cls._finished(P[code], config, date(2026, m, 1))
        # CAT joined 1 May 2026 (tax year 2026–27 on the April scheme).
        for m in range(5, 11):
            cls._finished(P['CAT'], cls.april, date(2026, m, 1), gross=50000.0, pit=-5000.0)
        # DAN joined 1 Feb 2026 — tax year 2025–26 on the April scheme.
        for m in range(2, 11):
            cls._finished(P['DAN'], cls.april, date(2026, m, 1), gross=70000.0, pit=-7000.0)
        cls.Upd.save_ytd_figure('gross', ['GROSS'])
        cls.Upd.save_ytd_figure('tax', ['PIT'])

    def setUp(self):
        super().setUp()
        patcher = patch.object(type(self.env['pb.records.apply']), '_records_now',
                               lambda _self: NOW)
        patcher.start()
        self.addCleanup(patcher.stop)

    def cols(self, used):
        return {'used': {str(k): v for k, v in used.items()}, 'identity': {'code': 1},
                'heads': {}}

    def load(self, rows, used, covers=COVERS, name='W2A figures'):
        answer = self.Upd.review(csv_b64(rows), 'w2a.csv', self.cols(used), kind='ytd',
                                 cutover=covers)
        self.assertTrue(answer['ok'], answer.get('msg'))
        res = self.Upd.apply(name, csv_b64(rows), 'w2a.csv', self.cols(used), answer['changes'],
                             {'rows': len(rows) - 1}, kind='ytd', cutover=covers)
        self.assertTrue(res['ok'], res.get('msg'))
        return answer, res

    def standard(self):
        """AMY and BOB: gross 300,000 and tax 30,000 before Payobook, up to 30 June."""
        return self.load([['Employee code', 'Gross', 'Tax'],
                          ['W2AAMY', '300000', '30000'], ['W2ABOB', '600000', '60000']],
                         {2: 'y:gross', 3: 'y:tax'})

    def mapping(self, config, code, figure, basis='before_period'):
        res = self.Upd.save_ytd_map(config.id, code, figure, basis)
        self.assertTrue(res['ok'], res.get('msg'))

    def rows_of(self, code):
        return self.Line.sudo().search([('employee_id', '=', self.people[code].id),
                                        ('state', '=', 'set')])

    # ------------------------------------------------------------------ U1
    def test_u1_rows_carry_their_tax_year(self):
        answer, res = self.standard()
        amy, bob = self.rows_of('AMY'), self.rows_of('BOB')
        self.assertEqual(set(amy.mapped('tax_year')), {2026})
        self.assertEqual(set(amy.mapped('tax_year_start_month')), {4})
        self.assertEqual(set(amy.mapped('tax_year_label')), {'2026–27'})
        self.assertEqual(set(bob.mapped('tax_year')), {2026})
        self.assertEqual(set(bob.mapped('tax_year_start_month')), {0})
        self.assertEqual(set(bob.mapped('tax_year_label')), {'2026'})
        # The company's schemes disagree, so the screens count "this tax year"
        # as the calendar year; each person's row follows their own scheme.
        self.assertEqual(self.Line._ty_desk_month(self.company.ids), 1)
        self.assertEqual((answer['tax_year'], answer['tax_year_label']), (2026, '2026'))
        self.assertEqual(res['tax_year'], 2026)
        # Past updates: the sheet's own rows decide (AMY 2026–27, BOB 2026 differ → company's).
        batch = amy.mapped('batch_id')[:1]
        self.assertEqual(self.Upd._ytd_tax_year_of(date(2026, 6, 30), batch.ytd_line_ids)['tax_year'],
                         2026)
        self.assertEqual(self.Upd._ytd_tax_year_of(date(2026, 6, 30), amy)['tax_year_label'],
                         '2026–27')
        # A figure dated February 2027 on the April scheme is still 2026–27.
        months = self.Line._ty_months_of([self.people['AMY'].id], date(2027, 2, 28))
        self.assertEqual(months[self.people['AMY'].id], 4)
        self.assertEqual(self.Line._ty_key(4, date(2027, 2, 28)), 2026)

    # ------------------------------------------------------------------ U2
    def test_u2_plan_under_april_start(self):
        self.standard()
        self.mapping(self.april, 'GROSSYTD', 'gross')
        self.mapping(self.april, 'TAXYTD', 'tax')
        plan = self.Line.sudo()._plan_for_slip(self.people['AMY'], self.april,
                                               '2026-11-01', '2026-11-30')
        # 300,000 before Payobook (Apr..Jun) + Jul..Oct 4 × 100,000.
        self.assertEqual(plan['GROSSYTD']['value'], 700000.0)
        self.assertEqual(plan['GROSSYTD']['gap'], [])
        # Tax: 30,000 + 4 × 10,000 (deductions counted as amounts).
        self.assertEqual(plan['TAXYTD']['value'], 70000.0)
        self.assertFalse(self.Line._plan_blocked(plan['GROSSYTD']))
        # The tax year's payslips only (none from Jan..Mar 2026, tax year 2025–26).
        slips = self.env['hr.payslip'].browse(plan['GROSSYTD']['slips'])
        self.assertTrue(slips)
        self.assertTrue(all(s.date_from >= date(2026, 7, 1) for s in slips))
        # A payslip of March 2027 is still tax year 2026–27 (same figures).
        plan = self.Line.sudo()._plan_for_slip(self.people['AMY'], self.april,
                                               '2027-03-01', '2027-03-31')
        self.assertEqual(plan['GROSSYTD']['before'], 300000.0)
        self.assertEqual(plan['GROSSYTD']['gap'], ['2026-11-01', '2026-12-01', '2027-01-01',
                                                   '2027-02-01'])
        # April 2027 starts a new tax year: those figures are last year's.
        self.assertEqual(self.Line.sudo()._plan_for_slip(self.people['AMY'], self.april,
                                                         '2027-04-01', '2027-04-30'), {})

    # ------------------------------------------------------------------ U3
    def test_u3_joined_this_tax_year(self):
        self.mapping(self.april, 'GROSSYTD', 'gross')
        L = self.Line.sudo()
        # CAT joined 1 May 2026: paid in Payobook alone, May..Oct.
        plan = L._plan_for_slip(self.people['CAT'], self.april, '2026-11-01', '2026-11-30')
        self.assertEqual(plan['GROSSYTD']['value'], 300000.0)
        self.assertEqual(plan['GROSSYTD']['joined'], '2026-05-01')
        # DAN joined 1 Feb 2026 — last tax year for an April scheme: nothing
        # (he needs figures before Payobook for Apr 2026 onwards... none).
        self.assertEqual(L._plan_for_slip(self.people['DAN'], self.april, '2026-11-01',
                                          '2026-11-30'), {})
        # ... while for March 2026 (tax year 2025–26) he IS a joiner: Feb only.
        plan = L._plan_for_slip(self.people['DAN'], self.april, '2026-03-01', '2026-03-31')
        self.assertEqual(plan['GROSSYTD']['value'], 70000.0)
        self.assertEqual(L._joined_in(self.people['DAN'], 2025, 4), date(2026, 2, 1))
        self.assertIsNone(L._joined_in(self.people['DAN'], 2026, 4))
        self.assertEqual(L._joined_in(self.people['DAN'], 2026, 1), date(2026, 2, 1))

    # ------------------------------------------------------------------ U4
    def test_u4_a_calendar_row_never_feeds_an_april_scheme(self):
        self.standard()
        bob_rows = self.rows_of('BOB')
        self.assertTrue(bob_rows)
        self.mapping(self.april, 'GROSSYTD', 'gross')
        # BOB's figures are calendar-year figures: on an April scheme they
        # are another tax year, so nothing is sent (not a wrong sum).
        self.assertEqual(self.Line.sudo()._plan_for_slip(self.people['BOB'], self.april,
                                                         '2026-11-01', '2026-11-30'), {})
        self.mapping(self.jan, 'GROSSYTD', 'gross')
        plan = self.Line.sudo()._plan_for_slip(self.people['BOB'], self.jan,
                                               '2026-11-01', '2026-11-30')
        self.assertEqual(plan['GROSSYTD']['value'], 1000000.0)    # 600,000 + Jul..Oct

    # ------------------------------------------------------------------ U5
    def test_u5_view_reads_each_persons_tax_year(self):
        self.standard()
        _figures, rows = self.Upd._ytd_rows(2026, [self.people['AMY'].id, self.people['BOB'].id,
                                                   self.people['CAT'].id])
        by = {r['emp_id']: r for r in rows}
        amy = by[self.people['AMY'].id]['cells']['gross']
        bob = by[self.people['BOB'].id]['cells']['gross']
        cat = by[self.people['CAT'].id]['cells']['gross']
        self.assertEqual((amy['before'], amy['paid'], amy['total']), (300000.0, 400000.0, 700000.0))
        self.assertEqual((bob['before'], bob['paid'], bob['total']), (600000.0, 400000.0, 1000000.0))
        # CAT: joined in the tax year, May..Oct, a year total.
        self.assertEqual(cat['paid'], 300000.0)
        self.assertTrue(cat['year_total'])

    # ------------------------------------------------------------------ U6
    def test_u6_r1_january_everywhere(self):
        # One company, January only (a world exactly as before W2-A).
        self.april.tax_year_start_month = '1'
        L = self.Line
        self.assertEqual(L._ty_months_in_use(self.company.ids), {1})
        self.assertEqual(L._ty_desk_month(self.company.ids), 1)
        home = self.Upd._ytd_home()
        self.assertEqual((home['this_year'], home['last_year']), (2026, 2025))
        self.assertEqual((home['min'], home['max']), ('2025-01-01', '2026-12-31'))
        self.assertEqual(home['default'], '2026-10-31')
        self.assertEqual(home['year_labels'], {'2026': '2026', '2025': '2025'})
        self.assertEqual(home['last_year_end'], '2025-12-31')
        # No scheme map look-up while everyone is on January.
        with patch.object(type(self.env['pb.scheme.map']), 'resolve_many',
                          side_effect=AssertionError('not asked')):
            months = L._ty_months_of([p.id for p in self.people.values()])
        self.assertEqual(set(months.values()), {1})
        self.standard()
        self.assertEqual(set(self.rows_of('AMY').mapped('tax_year_start_month')), {0})
        # The cover check says what it said before.
        _day, why = self.Upd._ytd_cover('2024-12-31')
        self.assertEqual(why, "Figures can be for this tax year (2026) or last year (2025). "
                              "31 Dec 2024 is outside both.")
        view = self.Upd.get_ytd_view(year=2026)
        self.assertEqual((view['year'], view['this_year'], view['year_label']), (2026, 2026, '2026'))
        # An old row (no month stored) keeps meaning the calendar year.
        row = self.rows_of('BOB')[:1]
        self.assertEqual((row.tax_year_start_month, row.tax_year_label), (0, '2026'))
        self.assertIn('2026', row._plan_row()['field_label'])

    # ------------------------------------------------------------------ U7 (data)
    def test_u7a_tax_sheet_year_bounds_follow_the_page(self):
        # The page's own tax year bounds reach the counted totals.
        qc = {'codes': ['GROSS'], 'rows': [], 'ytd': {'GROSS': 0.0}, 'ytd_year': 2026,
              'ytd_start_month': 4}
        self.assertEqual(self.Line._tax_summary_counted(self.people['AMY'], qc), qc)
        self.standard()
        qc = {'codes': ['GROSS', 'PIT'], 'rows': [], 'ytd': {'GROSS': 600000.0, 'PIT': -60000.0},
              'ytd_year': 2026, 'ytd_start_month': 4}
        self.Line._tax_summary_opening(self.people['AMY'], qc)
        self.assertEqual(qc['ytd']['GROSS'], 900000.0)
        # A January page never picks up AMY's April rows.
        qc = {'codes': ['GROSS'], 'rows': [], 'ytd': {'GROSS': 0.0}, 'ytd_year': 2026}
        self.Line._tax_summary_opening(self.people['AMY'], qc)
        self.assertNotIn('ytd_opening', qc)


@tagged('post_install', '-at_install', 'pb_updates', 'wdgap_w2a')
class TestW2aTaxSheetPage(W2aFixture, HttpCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._w2a_world()
        group = cls.env.ref('base.group_user')
        cls.users, cls.people = {}, {}
        for code, team, config in (('EVA', cls.team_apr, cls.april), ('FIN', cls.team_jan, cls.jan)):
            user = cls.env['res.users'].with_context(no_reset_password=True).create({
                'name': 'DEMO W2A %s' % code.title(), 'login': 'w2a_%s@example.com' % code.lower(),
                'password': PASSWORD, 'company_id': cls.company.id,
                'company_ids': [(6, 0, [cls.company.id])], 'group_ids': [(6, 0, [group.id])]})
            person = cls._person('DEMO W2A %s' % code.title(), 'W2A' + code, team,
                                 joined=date(2024, 3, 1), user=user)
            for m in range(1, 6):          # Jan..May 2026
                cls._finished(person, config, date(2026, m, 1), gross=1000.0 * m, pit=-10.0 * m)
            cls.users[code], cls.people[code] = user, person
        cls.env['ir.config_parameter'].sudo().set_param('pb_me_portal.tax_codes', 'GROSS,PIT')

    def page(self, code):
        self.authenticate(self.users[code].login, PASSWORD)
        res = self.url_open('/my/taxsheet', timeout=90)
        self.assertEqual(res.status_code, 200)
        return res.text

    @staticmethod
    def tiles(html):
        return [re.sub(r'\s+', ' ', t).strip()
                for t in re.findall(r'class="pbme-tile-y"[^>]*>(.*?)</div>', html, re.S)]

    def test_u7_april_tax_sheet(self):
        html = self.page('EVA')
        self.assertIn('Tax year 2026–27', self.tiles(html)[0])
        # Totals: April + May = 4,000 + 5,000 gross; never January..March.
        self.assertIn('9,000', html)
        self.assertNotIn('YTD 2026', html)
        self.assertNotIn('Odoo', html)

    def test_u7b_january_tax_sheet_as_before(self):
        html = self.page('FIN')
        self.assertEqual(self.tiles(html)[0], 'YTD 2026')
        # Jan..May = 15,000 gross — the old sum.
        self.assertIn('15,000', html)
        self.assertNotIn('Tax year 2026', html)
