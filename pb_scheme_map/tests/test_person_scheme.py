# -*- coding: utf-8 -*-
"""PSCHEME P1 — the pay scheme belongs to the person.

T1  no rows anywhere: every answer identical with and without the new rung
T2  a person row beats team / division / rule; a work segment beats the row
T3  ledger A4: the joiner counted backwards; an earlier row keeps its month
T4  ledger A3 / R7: no advance from the team for a person with their own row
T5  own main + own advance; 'any' never answers the advance
T6  a final settlement falls through to the ladder
T7  an ended row with no successor answers nobody (not the team)
T8  the four constraints, each with its sentence
T9  `pb_scheme_skip_person` restores the old answer
T10 `resolve_for_draft` with a scheme equals `resolve` for a real person
T11 stale marks; the recompute writes own scheme, advance, `pb_paid_by_own`
T12 the boundary job marks exactly the right people
T13 the three advance allow-lists agree; an advance row reaches the pay items
T15 two people of one team, two own schemes, two runs; "paid elsewhere"
T16 R6: a change dated the 15th — old scheme that month, new one the next
T17 the payslip's own map lookup is judged on its first day
T18 `person_set` fast lane rows, idempotent
T19 second-approver route: written on approval, refused when rows moved
T20 rights
T21 every refusal of ledger D.2 says why
"""

import ast
import inspect
import re
from datetime import date, timedelta
from unittest.mock import patch

from odoo import fields
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests.common import TransactionCase, new_test_user, tagged

from odoo.addons.pb_scheme_map.models import pb_scheme_map as map_module
from odoo.addons.pb_scheme_map.models.pb_scheme_map import (
    ADVANCE_RUNGS, RUNGS, SKIP_PERSON,
)

D = fields.Date.to_date


@tagged('post_install', '-at_install', 'pscheme')
class TestPersonScheme(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        cls.Map = env['pb.scheme.map']
        cls.Board = env['pb.scheme.board']
        cls.Row = env['pb.person.scheme']
        cls.Assign = env['hr.formula.scheme.assignment']
        vnd = env.ref('base.VND').sudo()
        if not vnd.active:
            vnd.active = True
        cls.company = env['res.company'].create({'name': 'DEMO PS Company',
                                                 'currency_id': vnd.id})
        cls.other = env['res.company'].create({'name': 'DEMO PS Other',
                                               'currency_id': vnd.id})
        env.user.company_ids = [(4, cls.company.id), (4, cls.other.id)]
        cls.fast(cls.company)
        cls.fast(cls.other)
        cls.fast(env.company)
        Dept = env['hr.department']
        cls.top = Dept.create({'name': 'DEMO PS Top', 'company_id': cls.company.id})
        cls.team = Dept.create({'name': 'DEMO PS Team', 'parent_id': cls.top.id,
                                'company_id': cls.company.id})
        cls.loose = Dept.create({'name': 'DEMO PS Loose', 'company_id': cls.company.id})
        cls.vn_end = cls._config('DEMO PS Vietnam monthly', 'DEMOPSVNE', 'end_cycle', 'VN')
        cls.vn_mid = cls._config('DEMO PS Vietnam advance', 'DEMOPSVNM', 'mid_cycle', 'VN')
        cls.id_end = cls._config('DEMO PS Indonesia monthly', 'DEMOPSIDE', 'end_cycle', 'ID')
        cls.id_mid = cls._config('DEMO PS Indonesia advance', 'DEMOPSIDM', 'mid_cycle', 'ID')
        cls.vn_reg = cls._config('DEMO PS Vietnam regular', 'DEMOPSVNR', 'regular', 'VN')
        cls.ff = cls._config('DEMO PS Final', 'DEMOPSFF', 'full_final', 'VN')
        cls.foreign = cls._config('DEMO PS Other monthly', 'DEMOPSOTH', 'end_cycle', 'VN',
                                  company=cls.other)
        cls.a = cls._person('DEMO PS Ana', cls.team, 'VN')
        cls.b = cls._person('DEMO PS Budi', cls.team, 'ID')
        cls.c = cls._person('DEMO PS Chi', cls.loose, 'VN')
        cls.d1 = date(2026, 12, 1)
        cls.d15 = date(2026, 12, 15)
        cls.j1 = date(2027, 1, 1)

    # -------------------------------------------------------------- fixtures
    @classmethod
    def fast(cls, company):
        try:
            cls.env['biz.approval.seed'].sudo().set_no_approval_needed(
                company, 'schememap', reason='PSCHEME suite')
        except Exception:   # noqa: BLE001
            pass

    @classmethod
    def _config(cls, name, code, cycle, country, company=None):
        return cls.env['hr.formula.config'].create({
            'name': name, 'code': code, 'cycle_type': cycle, 'country_code': country,
            'company_id': (company or cls.company).id, 'state': 'active'})

    @classmethod
    def _person(cls, name, team, country, company=None):
        company = company or cls.company
        employee = cls.env['hr.employee'].create({
            'name': name, 'company_id': company.id, 'payroll_country': country})
        version = employee.current_version_id
        if version and 'department_id' in version._fields:
            version.department_id = team.id
        else:
            employee.department_id = team.id
        return employee

    def _contract(self, employee):
        calendar = self.company.resource_calendar_id or self.env['resource.calendar'].create(
            {'name': 'DEMO PS Hours', 'company_id': self.company.id})
        kind = self.env['hr.contract.type'].search([], limit=1) or self.env[
            'hr.contract.type'].create({'name': 'DEMO PS Kind'})
        return self.env['hr.contract'].create({
            'name': 'DEMO PS contract %s' % employee.id, 'employee_id': employee.id,
            'company_id': self.company.id, 'wage': 1000000.0, 'state': 'open',
            'date_start': '2020-01-01', 'resource_calendar_id': calendar.id,
            'type_id': kind.id})

    def row(self, employee, config, date_from, date_to=False, source='hand'):
        return self.Row.sudo().create({'employee_id': employee.id, 'config_id': config.id,
                                       'date_from': date_from, 'date_to': date_to,
                                       'source': source})

    def line(self, config, cycle='any', team=None, **kw):
        values = {'config_id': config.id, 'cycle_type': cycle, 'company_id': self.company.id}
        if team:
            values['department_id'] = team.id
        values.update(kw)
        return self.Assign.create(values)

    def ask(self, employee, cycle='any', day=None):
        return self.Map.resolve_many([employee.id], cycle, on_date=day)[employee.id]

    # ==================================================================== T1
    def test_t1_no_rows_changes_no_answer(self):
        self.assertEqual(RUNGS, ('segment', 'person', 'department', 'division',
                                 'rule', 'only', 'none'))
        people = self.a | self.b | self.c
        Skip = self.Map.with_context(**{SKIP_PERSON: True})

        def same(label):
            for cycle in ('any', 'end_cycle', 'mid_cycle', 'regular', 'full_final'):
                new = self.Map.resolve_many(people.ids, cycle)
                old = Skip.resolve_many(people.ids, cycle)
                self.assertEqual(new, old, '%s / %s' % (label, cycle))
        same('none')
        for config in (self.vn_mid, self.id_end, self.id_mid, self.vn_reg, self.ff):
            config.state = 'draft'
        same('only')
        for config in (self.vn_mid, self.id_end, self.id_mid, self.vn_reg, self.ff):
            config.state = 'active'
        rule = self.line(self.id_end, domain="[('name', '=', 'DEMO PS Budi')]")
        same('rule')
        division = self.env['pb.division'].create({'name': 'DEMO PS Division'})
        self.env['pb.division.link'].create({'division_id': division.id,
                                             'department_id': self.top.id,
                                             'date_from': date(2020, 1, 1)})
        self.line(self.vn_reg, division_id=division.id)
        same('division')
        self.line(self.vn_end, team=self.team)
        same('team')
        rule.unlink()
        self.assertFalse(self.Row.sudo().search_count([('employee_id', 'in', people.ids)]))

    # ==================================================================== T2
    def test_t2_person_beats_team_division_rule_segment_beats_person(self):
        self.line(self.vn_end, team=self.team)
        self.line(self.vn_end, domain="[('name', '=', 'DEMO PS Ana')]")
        division = self.env['pb.division'].create({'name': 'DEMO PS Div2'})
        self.env['pb.division.link'].create({'division_id': division.id,
                                             'department_id': self.top.id,
                                             'date_from': date(2020, 1, 1)})
        self.line(self.vn_reg, division_id=division.id)
        self.assertEqual(self.ask(self.a)['rung'], 'department')
        self.row(self.a, self.id_end, date(2026, 1, 1))
        answer = self.ask(self.a, 'end_cycle')
        self.assertEqual((answer['rung'], answer['config_id']), ('person', self.id_end.id))
        self.assertIn('their own pay scheme', answer['via'])
        segment = {'config_id': self.vn_reg.id, 'config_name': 'x', 'rung': 'segment', 'via': 'x'}
        with patch.object(type(self.Map), '_segment_schemes',
                          lambda self_, ids, on_date=None: {self.a.id: dict(segment)}):
            self.assertEqual(self.ask(self.a)['rung'], 'segment')

    # ==================================================================== T3
    def test_t3_joiner_counts_backwards_earlier_row_keeps_its_month(self):
        self.line(self.vn_end, team=self.team)
        self.row(self.b, self.id_end, self.d15)
        answer = self.ask(self.b, 'end_cycle', self.d1)
        self.assertEqual((answer['rung'], answer['config_id']), ('person', self.id_end.id))
        # an earlier row of the same kind: it pays December, the new one January
        self.Row.sudo().search([('employee_id', '=', self.b.id)]).unlink()
        self.row(self.b, self.vn_end, date(2026, 1, 1), self.d15 - timedelta(days=1))
        self.row(self.b, self.id_end, self.d15)
        self.assertEqual(self.ask(self.b, 'end_cycle', self.d1)['config_id'], self.vn_end.id)
        self.assertEqual(self.ask(self.b, 'end_cycle', self.j1)['config_id'], self.id_end.id)

    # ==================================================================== T4
    def test_t4_no_advance_from_the_team(self):
        self.line(self.vn_end, 'end_cycle', team=self.team)
        self.line(self.vn_mid, 'mid_cycle', team=self.team)
        other = self._person('DEMO PS Dewi', self.team, 'VN')
        self.row(self.a, self.vn_end, date(2026, 1, 1))
        answer = self.ask(self.a, 'mid_cycle')
        self.assertEqual((answer['rung'], answer['config_id']), ('none', 0))
        self.assertIn('no mid-month advance', answer['via'])
        self.assertEqual(self.ask(other, 'mid_cycle')['config_id'], self.vn_mid.id)

    # ==================================================================== T5
    def test_t5_own_main_and_own_advance(self):
        self.row(self.b, self.id_end, date(2026, 1, 1))
        self.row(self.b, self.id_mid, date(2026, 1, 1))
        self.assertEqual(self.ask(self.b, 'end_cycle')['config_id'], self.id_end.id)
        self.assertEqual(self.ask(self.b, 'mid_cycle')['config_id'], self.id_mid.id)
        self.assertEqual(self.ask(self.b, 'any')['config_id'], self.id_end.id)
        # (a person with ONLY an advance row cannot be made: `person_set`
        # always needs the main pay scheme — ledger A5's `_pick` order stands)

    def test_t5b_main_question_takes_the_other_main_kind(self):
        """The company runs end of month, the person's own scheme is a regular
        one: "Paid by" names it; an end-of-month pay run still does not take
        them."""
        self.line(self.vn_end, team=self.team)
        self.row(self.a, self.vn_reg, date(2026, 1, 1))
        self.assertEqual(self.env['hr.employee']._pb_main_cycle(self.company.id), 'end_cycle')
        self.env['hr.employee'].sudo()._pb_recompute_paid_by(employee_ids=self.a.ids)
        self.assertEqual(self.a.pb_paid_by_id, self.vn_reg)
        self.assertTrue(self.a.pb_paid_by_own)
        self.assertEqual(self.ask(self.a, 'end_cycle')['config_id'], 0)
        self.assertEqual(self.Board.paid_by(self.a.id)['config_id'], self.vn_reg.id)
        self.assertEqual(self.Board.person_scheme(self.a.id)['main']['id'], self.vn_reg.id)

    # ==================================================================== T6
    def test_t6_final_settlement_falls_through(self):
        self.line(self.ff, 'full_final', team=self.team)
        self.row(self.a, self.vn_end, date(2026, 1, 1))
        answer = self.ask(self.a, 'full_final')
        self.assertEqual((answer['rung'], answer['config_id']), ('department', self.ff.id))

    # ==================================================================== T7
    def test_t7_ended_row_answers_nobody(self):
        self.line(self.vn_end, team=self.team)
        self.row(self.a, self.id_end, date(2026, 1, 1), date(2026, 10, 31))
        answer = self.ask(self.a, 'end_cycle', self.d1)
        self.assertEqual((answer['rung'], answer['config_id']), ('none', 0))
        self.assertIn('ended', answer['via'])
        if 'pb.payrun.wizard' in self.env:
            self._contract(self.a)
            wizard = self.env['pb.payrun.wizard'].with_company(self.company)
            covered, missed = wizard._scheme_population(self.vn_end.id, self.a.ids, on_date=self.d1)
            self.assertNotIn(self.a.id, covered)
            self.assertIn(self.a.id, [m['employee_id'] for m in missed])

    # ==================================================================== T8
    def test_t8_constraints_each_say_why(self):
        self.row(self.a, self.vn_end, date(2026, 1, 1))
        with self.assertRaisesRegex(ValidationError, 'one pay scheme of each kind'):
            self.row(self.a, self.id_end, date(2026, 6, 1))
        with self.assertRaisesRegex(ValidationError, 'belongs to DEMO PS Other'):
            self.row(self.b, self.foreign, date(2026, 1, 1))
        with self.assertRaisesRegex(ValidationError, 'final settlement'):
            self.row(self.b, self.ff, date(2026, 1, 1))
        with self.assertRaisesRegex(ValidationError, 'end date is before'):
            self.row(self.b, self.id_end, date(2026, 6, 1), date(2026, 5, 1))
        # two kinds side by side are fine
        self.row(self.a, self.vn_mid, date(2026, 1, 1))

    # ==================================================================== T9
    def test_t9_skip_key_restores_the_old_answer(self):
        self.line(self.vn_end, team=self.team)
        before = self.ask(self.a, 'end_cycle')
        self.row(self.a, self.id_end, date(2026, 1, 1))
        self.assertEqual(self.ask(self.a, 'end_cycle')['rung'], 'person')
        skipped = self.Map.with_context(**{SKIP_PERSON: True}).resolve_many(
            self.a.ids, 'end_cycle')[self.a.id]
        self.assertEqual(skipped, before)

    # =================================================================== T10
    def test_t10_draft_equals_a_real_person(self):
        self.line(self.vn_end, 'end_cycle', team=self.team)
        self.line(self.vn_mid, 'mid_cycle', team=self.team)
        for main, advance in ((self.id_end, None), (self.id_end, self.id_mid),
                              (self.vn_end, None), (self.vn_reg, self.vn_mid)):
            self.Row.sudo().search([('employee_id', '=', self.a.id)]).unlink()
            self.row(self.a, main, date(2026, 1, 1))
            if advance:
                self.row(self.a, advance, date(2026, 1, 1))
            values = {'payroll_country': 'VN', 'scheme_id': main.id,
                      'advance_scheme_id': advance.id if advance else False}
            for cycle in ('any', 'end_cycle', 'regular', 'mid_cycle', 'full_final'):
                real = self.ask(self.a, cycle)
                draft = self.Map.resolve_for_draft(self.team.id, values, self.company.id, cycle)
                self.assertEqual((draft['config_id'], draft['rung']),
                                 (real['config_id'], real['rung']),
                                 '%s/%s/%s' % (main.name, advance and advance.name, cycle))
        # without a scheme: unchanged
        self.Row.sudo().search([('employee_id', '=', self.a.id)]).unlink()
        draft = self.Map.resolve_for_draft(self.team.id, {'payroll_country': 'VN'},
                                           self.company.id, 'end_cycle')
        self.assertEqual((draft['config_id'], draft['rung']), (self.vn_end.id, 'department'))

    # =================================================================== T11
    def test_t11_stale_marks_and_recompute(self):
        Employee = self.env['hr.employee'].sudo()
        people = self.a | self.b | self.c
        Employee._pb_recompute_paid_by(employee_ids=people.ids)
        self.assertFalse(any(people.mapped('pb_paid_by_stale')))
        row = self.row(self.a, self.id_end, date(2026, 1, 1))
        self.env.invalidate_all()
        self.assertEqual(people.mapped('pb_paid_by_stale'), [True, False, False])
        Employee._pb_recompute_paid_by(employee_ids=people.ids)
        self.row(self.a, self.id_mid, date(2026, 1, 1))
        Employee._pb_recompute_paid_by(employee_ids=people.ids)
        self.assertEqual((self.a.pb_paid_by_id, self.a.pb_paid_by_advance_id,
                          self.a.pb_paid_by_own), (self.id_end, self.id_mid, True))
        self.assertFalse(self.b.pb_paid_by_own)
        row.write({'date_to': date(2026, 12, 31)})
        self.env.invalidate_all()
        self.assertTrue(self.a.pb_paid_by_stale)
        Employee._pb_recompute_paid_by(employee_ids=people.ids)
        row.unlink()
        self.env.invalidate_all()
        self.assertEqual(people.mapped('pb_paid_by_stale'), [True, False, False])
        Employee._pb_recompute_paid_by(employee_ids=people.ids)
        self.b.payroll_country = 'VN'
        self.env.invalidate_all()
        self.assertEqual(people.mapped('pb_paid_by_stale'), [False, True, False])
        # A7: the server never changes a scheme because a country changed
        self.assertFalse(self.Row.sudo().search_count([('employee_id', '=', self.b.id)]))

    # =================================================================== T12
    def test_t12_boundary_job(self):
        today = fields.Date.context_today(self.Row)
        dewi = self._person('DEMO PS Dewi', self.team, 'VN')
        self.row(self.a, self.id_end, today)
        self.row(self.b, self.id_end, today - timedelta(days=40), today - timedelta(days=1))
        self.row(self.c, self.vn_end, today - timedelta(days=40))
        self.row(dewi, self.vn_end, today - timedelta(days=40), today)
        Employee = self.env['hr.employee'].sudo()
        everyone = Employee.search([('company_id', '=', self.company.id)])
        Employee._pb_recompute_paid_by(employee_ids=everyone.ids)
        self.assertEqual(self.Row._cron_mark_boundaries() >= 2, True)
        self.env.invalidate_all()
        stale = everyone.filtered('pb_paid_by_stale')
        self.assertEqual(stale, self.a | self.b)
        cron = self.env.ref('pb_scheme_map.cron_person_scheme_boundaries')
        self.assertTrue(cron.active)

    # =================================================================== T13
    def test_t13_advance_lists_agree(self):
        from odoo.addons.pb_hr_payroll_formula.models import scheme_component_scope
        text = inspect.getsource(scheme_component_scope)
        found = re.search(r"second\.get\('rung'\) in (\([^)]*\))", text)
        self.assertTrue(found)
        self.assertEqual(ast.literal_eval(found.group(1)), ADVANCE_RUNGS)
        self.assertEqual(ADVANCE_RUNGS, ('person', 'department', 'division', 'rule'))
        from odoo.addons.pb_scheme_map.models import hr_employee, pb_scheme_board
        for module in (hr_employee, pb_scheme_board):
            self.assertIs(module.ADVANCE_RUNGS, map_module.ADVANCE_RUNGS)
        self.row(self.b, self.id_end, date(2026, 1, 1))
        self.row(self.b, self.id_mid, date(2026, 1, 1))
        schemes = self.env['hr.formula.config'].schemes_for_employee(self.b)
        self.assertEqual(schemes, self.id_end | self.id_mid)
        chip = self.Board.paid_by(self.b.id)
        self.assertEqual(chip['advance'], self.id_mid.name)

    # =================================================================== T15
    def test_t15_one_team_two_schemes_two_runs(self):
        if 'pb.payrun.wizard' not in self.env:
            self.skipTest('no pay run wizard')
        self.line(self.vn_end, team=self.team)
        for person in (self.a, self.b):
            self._contract(person)
        self.row(self.a, self.vn_end, date(2026, 1, 1))
        self.row(self.b, self.id_end, date(2026, 1, 1))
        wizard = self.env['pb.payrun.wizard'].with_company(self.company)
        people = (self.a | self.b).ids

        def run(config):
            return set(wizard._eligible_employees(employee_ids=people, formula_config_id=config.id,
                                                  date_start='2026-12-01', date_end='2026-12-31'))
        self.assertEqual(run(self.vn_end), {self.a.id})
        self.assertEqual(run(self.id_end), {self.b.id})
        elsewhere = wizard._scheme_elsewhere(self.vn_end.id, people, [self.a.id], on_date='2026-12-01')
        self.assertEqual([e['employee_id'] for e in elsewhere], [self.b.id])
        self.assertIn(self.id_end.name, elsewhere[0]['why'])
        self.assertFalse(wizard._scheme_elsewhere(self.id_end.id, people, [self.b.id],
                                                  on_date='2026-12-01'))
        # a REGULAR team run: a person whose own scheme is end of month is paid
        # elsewhere, and never also listed as "not covered"
        self.line(self.vn_reg, team=self.loose)
        self._contract(self.c)
        self.row(self.c, self.vn_end, date(2026, 1, 1))
        preview = wizard.scheme_preview({'employee_ids': self.c.ids, 'formula_config_id': self.vn_reg.id,
                                         'date_start': '2026-12-01', 'date_end': '2026-12-31'})
        self.assertEqual(preview['elsewhere'], 1)
        self.assertEqual(preview['not_covered'], 0)
        self.assertIn(self.vn_end.name, preview['elsewhere_people'][0]['why'])
        # someone whose own scheme is regular, in an end-of-month run their team
        # would not have put them in either: in neither list
        dewi = self._person('DEMO PS Dewi', self.loose, 'VN')
        self._contract(dewi)
        self.row(dewi, self.vn_reg, date(2026, 1, 1))
        preview = wizard.scheme_preview({'employee_ids': dewi.ids, 'formula_config_id': self.vn_end.id,
                                         'date_start': '2026-12-01', 'date_end': '2026-12-31'})
        self.assertEqual((preview['covered'], preview['not_covered'], preview['elsewhere']), (0, 0, 0))

    # =================================================================== T16
    def test_t16_change_mid_month_one_payslip_per_period(self):
        if 'pb.payrun.wizard' not in self.env:
            self.skipTest('no pay run wizard')
        self._contract(self.a)
        self.row(self.a, self.vn_end, date(2026, 1, 1))
        self.Board.with_context(allowed_company_ids=[self.company.id]).person_set(
            self.a.ids, self.id_end.id, False, '2026-12-15')
        wizard = self.env['pb.payrun.wizard'].with_company(self.company)
        for start, end, payer in (('2026-12-01', '2026-12-31', self.vn_end),
                                  ('2027-01-01', '2027-01-31', self.id_end)):
            found = [c for c in (self.vn_end, self.id_end)
                     if self.a.id in wizard._eligible_employees(
                         employee_ids=self.a.ids, formula_config_id=c.id,
                         date_start=start, date_end=end)]
            self.assertEqual(found, [payer], start)

    def test_t16b_a_new_kind_never_counts_backwards(self):
        """Regular from 1 Dec, end of month from 15 Jan: December and January
        are the regular scheme's, February the end-of-month one's — never both
        in one month (R6, ledger PS4). An advance added later does not count
        backwards either; one hired with the person does."""
        self.row(self.a, self.vn_reg, self.d1, date(2027, 1, 14))
        self.row(self.a, self.vn_end, date(2027, 1, 15))
        self.row(self.a, self.vn_mid, date(2027, 1, 15))
        for day, kinds in ((self.d1, {'regular'}), (self.j1, {'regular'}),
                           (date(2027, 2, 1), {'end_cycle', 'mid_cycle'})):
            found = {k for k in ('regular', 'end_cycle', 'mid_cycle')
                     if self.ask(self.a, k, day)['config_id']}
            self.assertEqual(found, kinds, day)
        # a joiner hired on the 15th with an advance: both count on the 1st
        self.row(self.b, self.id_end, self.d15)
        self.row(self.b, self.id_mid, self.d15)
        self.assertEqual(self.ask(self.b, 'end_cycle', self.d1)['config_id'], self.id_end.id)
        self.assertEqual(self.ask(self.b, 'mid_cycle', self.d1)['config_id'], self.id_mid.id)

    # =================================================================== T17
    def test_t17_payslip_lookup_uses_its_first_day(self):
        self.row(self.a, self.vn_end, date(2026, 1, 1), date(2026, 12, 31))
        self.row(self.a, self.id_end, self.j1)
        Slip = self.env['hr.payslip']
        found = []
        original = type(self.Map).resolve

        def spy(self_, employee, cycle_type='any', on_date=None):
            found.append(on_date)
            return original(self_, employee, cycle_type, on_date)
        with patch.object(type(self.Map), 'resolve', spy):
            slip = Slip.new({'employee_id': self.a.id, 'date_from': self.j1,
                             'date_to': date(2027, 1, 31), 'company_id': self.company.id})
            config = slip._find_formula_config()
        self.assertIn(self.j1, found)
        self.assertEqual(config, self.id_end)

    # =================================================================== T18
    def test_t18_person_set_fast_lane(self):
        Board = self.Board.with_context(allowed_company_ids=[self.company.id])
        out = Board.person_set(self.a.ids, self.vn_end.id, self.vn_mid.id, '2026-11-01')
        self.assertTrue(out.get('applied') or out.get('saved'), out)

        def rows():
            return [(r.config_id, r.date_from, r.date_to) for r in self.Row.sudo().search(
                [('employee_id', '=', self.a.id)], order='date_from, cycle_type, id')]
        self.assertEqual(sorted(rows(), key=lambda r: r[0].id),
                         sorted([(self.vn_end, date(2026, 11, 1), False),
                                 (self.vn_mid, date(2026, 11, 1), False)], key=lambda r: r[0].id))
        # same scheme already in force: nothing written; idempotent second call
        Board.person_set(self.a.ids, self.vn_end.id, 'keep', '2026-12-01')
        Board.person_set(self.a.ids, self.vn_end.id, 'keep', '2026-12-01')
        self.assertEqual(len(rows()), 2)
        # another scheme: the old one ends the day before
        Board.person_set(self.a.ids, self.id_end.id, 'keep', '2027-01-01')
        self.assertIn((self.vn_end, date(2026, 11, 1), date(2026, 12, 31)), rows())
        self.assertIn((self.id_end, self.j1, False), rows())
        # a row that never took effect is removed
        Board.person_set(self.a.ids, self.vn_end.id, 'keep', '2027-01-01')
        self.assertNotIn(self.id_end, [r[0] for r in rows()])
        # advance removed (R7), then the main kind switches to regular
        Board.person_set(self.a.ids, self.vn_end.id, False, '2027-02-01')
        self.assertIn((self.vn_mid, date(2026, 11, 1), date(2027, 1, 31)), rows())
        Board.person_set(self.a.ids, self.vn_reg.id, 'keep', '2027-03-01')
        live = self.Map.resolve_many(self.a.ids, 'end_cycle', date(2027, 3, 1))[self.a.id]
        self.assertEqual(live['config_id'], 0)
        self.assertEqual(self.ask(self.a, 'regular', date(2027, 3, 1))['config_id'], self.vn_reg.id)
        before = rows()
        Board.person_set(self.a.ids, self.vn_reg.id, False, '2027-03-01')
        self.assertEqual(rows(), before)

    # =================================================================== T19
    def test_t19_second_approver_route(self):
        company = self.env['res.company'].create({'name': 'DEMO PS Routed',
                                                  'currency_id': self.company.currency_id.id})
        self.env['pb.schememap.proposal']._approval_seed_default(company)
        co = {'company_id': company.id, 'company_ids': [(6, 0, [company.id])]}
        hr = new_test_user(self.env, login='ps_hr', groups='base.group_user,hr.group_hr_user',
                           name='DEMO PS HR', **co)
        boss = new_test_user(self.env, login='ps_boss', name='DEMO PS Payroll manager',
                             groups='base.group_user,hr.group_hr_user,'
                                    'pb_hr_payroll_formula.group_formula_manager', **co)
        role = self.env['biz.approval.role'].sudo().search([('key', '=', 'payroll_mgr')], limit=1)
        Resp = self.env['biz.approval.responsibility'].sudo()
        held = Resp.with_context(active_test=False).search([
            ('company_id', '=', company.id), ('role_id', '=', role.id), ('scope_key', '=', '')], limit=1)
        if held:
            held.write({'user_id': boss.id, 'active': True, 'backup_user_id': False})
        else:
            Resp.create({'company_id': company.id, 'role_id': role.id, 'scope_key': '',
                         'scope_label': company.name, 'user_id': boss.id,
                         'date_from': date(2020, 1, 1)})
        team = self.env['hr.department'].create({'name': 'DEMO PS R team', 'company_id': company.id})
        person = self._person('DEMO PS Eka', team, 'ID', company=company)
        main = self._config('DEMO PS R monthly', 'DEMOPSRM', 'end_cycle', 'ID', company=company)
        other = self._config('DEMO PS R other', 'DEMOPSRO', 'end_cycle', 'ID', company=company)
        Board = self.Board.with_user(hr).with_context(allowed_company_ids=[company.id])
        self.assertEqual(Board.person_scheme(person.id)['lane'], 'route')
        out = Board.person_set(person.ids, main.id, False, '2026-12-01')
        self.assertTrue(out['pending'], out)
        self.assertFalse(self.Row.sudo().search_count([('employee_id', '=', person.id)]))
        self.assertTrue(Board.person_scheme(person.id)['waiting'])
        request = self.env['biz.approval.request'].sudo().browse(out['request_id'])
        step = request.step_ids.filtered(lambda s: s.status == 'active')[:1]
        Engine = self.env['biz.approval.engine']
        audits = self.env['biz.audit.entry'].sudo().search_count([]) \
            if 'biz.audit.entry' in self.env else 0
        Engine.with_user(boss).with_context(allowed_company_ids=[company.id]).decide(
            request.id, step.key, 'approve', 'ok')
        self.env.invalidate_all()
        self.assertEqual(self.Row.sudo().search([('employee_id', '=', person.id)]).config_id, main)
        if 'biz.audit.entry' in self.env:
            self.assertGreater(self.env['biz.audit.entry'].sudo().search_count([]), audits)
        # rows moved in between: refused in a plain sentence naming the person
        out = Board.person_set(person.ids, other.id, 'keep', '2027-01-01')
        self.Row.sudo().search([('employee_id', '=', person.id)]).date_to = date(2026, 12, 31)
        request = self.env['biz.approval.request'].sudo().browse(out['request_id'])
        step = request.step_ids.filtered(lambda s: s.status == 'active')[:1]
        Engine.with_user(boss).with_context(allowed_company_ids=[company.id]).decide(
            request.id, step.key, 'approve', 'ok')
        self.env.invalidate_all()
        self.assertFalse(self.Row.sudo().search_count([('employee_id', '=', person.id),
                                                       ('config_id', '=', other.id)]))
        reason = request.block_reason or ''
        self.assertIn('DEMO PS Eka', reason)
        self.assertNotRegex(reason, r'\[\d|\b%d\b' % person.id)

    # =================================================================== T20
    def test_t20_rights(self):
        co = {'company_id': self.company.id, 'company_ids': [(6, 0, [self.company.id])]}
        hr = new_test_user(self.env, login='ps_hr2', groups='base.group_user,hr.group_hr_user',
                           name='DEMO PS HR two', **co)
        worker = new_test_user(self.env, login='ps_worker', groups='base.group_portal',
                               name='DEMO PS Worker', **co)
        RowAs = self.Row.with_user(hr)
        with self.assertRaises(AccessError):
            RowAs.create({'employee_id': self.a.id, 'config_id': self.vn_end.id,
                          'date_from': '2026-12-01'})
        Board = self.Board.with_user(hr).with_context(allowed_company_ids=[self.company.id])
        panel = Board.person_scheme(self.a.id)
        self.assertTrue(panel['can_propose'])
        # fast lane here, and the HR officer may not carry it out: said up front
        self.assertFalse(panel['can_carry_out'])
        self.assertTrue(panel['blocked'])
        with self.assertRaisesRegex(UserError, 'payroll manager'):
            Board.person_set(self.a.ids, self.vn_end.id, False, '2026-12-01')
        self.assertEqual(self.env['pb.schememap.proposal']._proposal_gate_groups,
                         ('pb_hr_payroll_formula.group_formula_manager',))
        for call in (lambda b: b.person_scheme(self.a.id),
                     lambda b: b.person_set(self.a.ids, self.vn_end.id, False, '2026-12-01')):
            with self.assertRaises(AccessError):
                call(self.Board.with_user(worker))

    # =================================================================== T21
    def test_t21_every_refusal_says_why(self):
        Board = self.Board.with_context(allowed_company_ids=[self.company.id])
        self.vn_reg.state = 'draft'
        cases = (
            ((self.a.ids, self.vn_reg.id, False), 'not switched on'),
            ((self.a.ids, self.foreign.id, False), 'belongs to DEMO PS Other'),
            ((self.a.ids, self.ff.id, False), 'final settlement'),
            ((self.a.ids, self.vn_end.id, self.id_end.id), 'not a mid-month advance'),
            ((self.a.ids, self.vn_mid.id, False), 'is a mid-month advance'),
        )
        for args, words in cases:
            with self.assertRaisesRegex(UserError, words):
                Board.person_set(*args, date_from='2026-12-01')
        self.vn_reg.state = 'active'
        self.c.active = False
        with self.assertRaisesRegex(UserError, 'archived'):
            Board.person_set(self.c.ids, self.vn_end.id, False, '2026-12-01')

    # ========================================================== the panel
    def test_panel_payload(self):
        self.line(self.vn_end, team=self.team)
        panel = self.Board.person_scheme(self.a.id)
        self.assertEqual(panel['main']['id'], self.vn_end.id)
        self.assertFalse(panel['main']['own'])
        self.assertIn('DEMO PS Team', panel['main']['from_words'])
        self.assertIn(self.vn_end.id, [c['id'] for c in panel['choices']])
        self.assertNotIn(self.id_end.id, [c['id'] for c in panel['choices']])
        self.assertIn(self.id_end.id, [c['id'] for c in panel['others']])
        self.assertEqual(panel['default_date'][-2:], '01')
        self.row(self.a, self.id_end, date(2026, 1, 1))
        panel = self.Board.person_scheme(self.a.id)
        self.assertTrue(panel['main']['own'])
        self.assertTrue(panel['history'])
        details = self.env['pb.people']._e360_details(self.a, True)
        keys = [g['key'] for g in details['pay']]
        self.assertIn('pb_scheme', keys)
        for group in details['pay']:
            if group['key'] == 'setup':
                labels = [r['label'] for r in group['rows']]
                self.assertNotIn('Payroll country', labels)
                self.assertNotIn('Paid by', labels)
