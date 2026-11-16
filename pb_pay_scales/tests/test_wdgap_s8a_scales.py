# -*- coding: utf-8 -*-
"""WDGAP S8-A — pay scales (grades × steps, dated) and joiners on the scale.

Numbered as in the report (§3):

S1  model: versions never overlap; coefficient cells = coefficient × base
    rate, rounded to the scale's unit; steps bounded.
S2  RAIL: editing cells, making a version, placing / pinning people write NO
    `hr.contract`, NO pay line and NO payslip (SQL spy); people on the scale
    read Drifted after a cell edit.
S3  resolver: job → band link → grade → scale → version on the start date →
    step 1; company, money and "no version" refusals said plainly.
S4  People › Add a contract: the wage box opens filled; an EMPTY box is
    filled on create; the contract is On scale; the grade's allowances are
    written only for the person's scheme's items, each logged "From the pay
    scale" on the start date.
S5  a typed wage that is a step → On scale at that step; any other typed
    wage wins → Pinned with the reason sent (or "Typed when hired").
S6  Updates joiners sheet: a row with a job and no wage gets the scale's
    amount in the review grid; a typed wage is left alone.
S7  Hiring "joined": an offer with no monthly pay takes the scale amount and
    says so; an agreed wage is kept and pinned "Offer agreed".
S8  the screen: board, people, place-matching (placements only), pin,
    unpin; the contract drawer chip (stage door only when the wage shows).
S9  rights: a plain user reads nothing and writes nothing; a pay viewer
    reads but cannot write.
S10 golden: a payslip of a contract nobody placed computes byte-identical
    before and after every scale operation.
S11 white-label: no "Odoo" in any user-visible string of the module.
"""
import json
import os
import re
from contextlib import contextmanager
from unittest.mock import patch

from odoo import fields
from odoo.exceptions import AccessError, ValidationError
from odoo.sql_db import Cursor
from odoo.tests import TransactionCase, tagged

from odoo.addons.pb_people_advanced.models.newhire_approval import NEWHIRE_WRITE

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


@contextmanager
def spy_writes(tables):
    """Every INSERT/UPDATE/DELETE statement touching one of ``tables``."""
    seen = []
    real = Cursor.execute

    def execute(self, query, params=None, log_exceptions=True):
        text = str(query.code if hasattr(query, 'code') else query).lower()
        head = text.lstrip()[:7]
        if head.startswith(('insert', 'update', 'delete')):
            for table in tables:
                if re.search(r'\b%s\b' % re.escape(table), text):
                    seen.append(text[:120])
        return real(self, query, params, log_exceptions)

    with patch.object(Cursor, 'execute', execute):
        yield seen


@tagged('post_install', '-at_install')
class TestS8aScales(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Scales = cls.env['pb.pay.scales']
        cls.company = cls.env.company
        cls.country = (cls.company.country_id.code or 'VN').upper()
        if cls.country not in dict(cls.env['pb.pay.scale']._fields['country_code'].selection):
            cls.country = 'VN'
            cls.company.country_id = cls.env.ref('base.vn')
        cls.currency = cls.company.currency_id
        # The scheme that pays the people here has the meal item, not the phone one.
        cls.cfg = cls.env['hr.formula.config'].create({
            'name': 'S8A scheme', 'code': 'SEIGHTA', 'country_code': cls.country,
            'state': 'active', 'company_id': cls.company.id,
            'currency_id': cls.company.currency_id.id})
        Rule = cls.env['hr.formula.rule']
        basic = Rule.create({'config_id': cls.cfg.id, 'code': 'BASIC', 'name': 'Basic',
                             'column_type': 'input', 'sequence': 10, 'net_role': 'earning'})
        meal = Rule.create({'config_id': cls.cfg.id, 'code': 'SAMEAL', 'name': 'Meal',
                            'column_type': 'input', 'sequence': 20, 'net_role': 'earning'})
        Rule.create({'config_id': cls.cfg.id, 'code': 'NETPAY', 'name': 'Take-home',
                     'column_type': 'formula', 'sequence': 30, 'net_role': 'net',
                     'excel_formula': '=%s+%s' % (basic.column_letter, meal.column_letter)})
        # The scheme decides the person's money (SCHEMECTX): the scale follows it.
        cls.currency = cls.cfg.currency_id or cls.company.currency_id
        cls.family = cls.env['pb.pay.family'].create({'name': 'S8A Store family'})
        cls.band = cls.env['pb.pay.band'].create({
            'family_id': cls.family.id, 'level': 3, 'country_code': cls.country,
            'currency_id': cls.currency.id, 'min_amount': 1000, 'mid_amount': 5000,
            'max_amount': 20000000, 'date_from': '2020-01-01'})
        cls.job = cls.env['hr.job'].create({'name': 'S8A Store associate'})
        cls.other_job = cls.env['hr.job'].create({'name': 'S8A Driver'})
        cls.link = cls.env['pb.pay.band.job'].create({'band_id': cls.band.id, 'job_id': cls.job.id})
        cls.scale = cls.env['pb.pay.scale'].create({
            'name': 'S8A Retail store scale', 'country_code': cls.country,
            'currency_id': cls.currency.id, 'step_count': 3})
        cls.grade = cls.env['pb.pay.scale.grade'].create(
            {'scale_id': cls.scale.id, 'name': 'Store associate', 'sequence': 10})
        cls.grade2 = cls.env['pb.pay.scale.grade'].create(
            {'scale_id': cls.scale.id, 'name': 'Senior associate', 'sequence': 20})
        cls.version = cls.env['pb.pay.scale.version'].create(
            {'scale_id': cls.scale.id, 'date_from': '2020-01-01'})
        for grade, amounts in ((cls.grade, (5500000, 5800000, 6100000)),
                               (cls.grade2, (6900000, 7300000, 7700000))):
            for step, amount in enumerate(amounts, start=1):
                cls.env['pb.pay.scale.cell'].create({
                    'version_id': cls.version.id, 'grade_id': grade.id,
                    'step_no': step, 'amount': amount})
        cls.link.pb_scale_grade_id = cls.grade.id
        cls.template = cls.env['hr.contract.advantage.template'].search(
            [('code', '=', 'SAMEAL')], limit=1) or cls.env['hr.contract.advantage.template'].create(
            {'name': 'S8A Meal allowance', 'code': 'SAMEAL'})
        cls.template_off = cls.env['hr.contract.advantage.template'].search(
            [('code', '=', 'SAPHONE')], limit=1) or cls.env['hr.contract.advantage.template'].create(
            {'name': 'S8A Phone allowance', 'code': 'SAPHONE'})
        cls.env['pb.pay.scale.package'].create({
            'version_id': cls.version.id, 'grade_id': cls.grade.id,
            'template_id': cls.template.id, 'amount': 730000})
        cls.env['pb.pay.scale.package'].create({
            'version_id': cls.version.id, 'grade_id': cls.grade.id,
            'template_id': cls.template_off.id, 'amount': 200000})
        cls._n = 0

    # ------------------------------------------------------------ fixtures
    def _employee(self, job=None, paid=True):
        type(self)._n += 1
        emp = self.env['hr.employee'].create({
            'name': 'S8A Person %s' % self._n, 'company_id': self.company.id,
            'job_id': (job or self.job).id})
        if paid and 'pb_paid_by_id' in emp._fields:
            emp.sudo().write({'pb_paid_by_id': self.cfg.id})
            if 'pb_paid_by_stale' in emp._fields:
                emp.sudo().write({'pb_paid_by_stale': False})
        return emp

    def _contract(self, emp, wage, state='open'):
        return self.env['hr.contract'].create({
            'name': 'S8A contract %s' % emp.name, 'employee_id': emp.id, 'wage': wage,
            'state': state, 'date_start': '2026-01-01', 'company_id': self.company.id})

    def _wizard(self):
        return self.env['pb.people.contract.wizard'].with_context(**{NEWHIRE_WRITE: True})

    # =====================================================================
    # S1 — the model
    # =====================================================================
    def test_s1_versions_never_overlap(self):
        with self.assertRaises(ValidationError):
            with self.env.cr.savepoint():
                self.env['pb.pay.scale.version'].create(
                    {'scale_id': self.scale.id, 'date_from': '2024-01-01'})
        # A version from a later day, after the first one ends, is fine.
        self.version.date_to = '2026-12-31'
        later = self.env['pb.pay.scale.version'].create(
            {'scale_id': self.scale.id, 'date_from': '2027-01-01'})
        self.assertEqual(self.scale.version_on('2027-02-01'), later)
        self.assertEqual(self.scale.version_on('2026-06-01'), self.version)

    def test_s1b_coefficient_cells_and_rounding(self):
        scale = self.env['pb.pay.scale'].create({
            'name': 'S8A coefficient scale', 'country_code': self.country,
            'currency_id': self.currency.id, 'mode': 'coefficient', 'step_count': 2,
            'rounding': 10000})
        grade = self.env['pb.pay.scale.grade'].create({'scale_id': scale.id, 'name': 'G1'})
        version = self.env['pb.pay.scale.version'].create(
            {'scale_id': scale.id, 'date_from': '2026-01-01', 'base_rate': 2340000})
        cell = self.env['pb.pay.scale.cell'].create(
            {'version_id': version.id, 'grade_id': grade.id, 'step_no': 1, 'coefficient': 2.34})
        # 2.34 × 2,340,000 = 5,475,600 → nearest 10,000 = 5,480,000
        self.assertEqual(cell.value, 5480000.0)
        with self.assertRaises(ValidationError):
            with self.env.cr.savepoint():
                self.env['pb.pay.scale.cell'].create(
                    {'version_id': version.id, 'grade_id': grade.id, 'step_no': 3, 'amount': 1})

    # =====================================================================
    # S2 — the safety rail: the scale never writes a contract
    # =====================================================================
    def test_s2_scale_edits_write_no_contract_and_people_drift(self):
        emp = self._employee()
        contract = self._contract(emp, 5800000)
        self.env['pb.pay.scale.placement'].create(
            {'contract_id': contract.id, 'grade_id': self.grade.id, 'step_no': 2})
        self.env.flush_all()
        self.assertEqual(contract.pb_scale_state, 'on')
        before = (contract.wage, contract.write_date, len(contract.sudo().advantage_ids)
                  if 'advantage_ids' in contract._fields else 0)
        tables = ('hr_contract', 'hr_contract_advantage', 'hr_contract_advantage_change',
                  'hr_payslip', 'hr_payslip_line', 'hr_employee', 'hr_version')
        with spy_writes(tables) as seen:
            self.Scales.save_cells(self.version.id, [
                {'grade_id': self.grade.id, 'step': 2, 'amount': 6000000}])
            self.Scales.new_version(self.scale.id, '2027-01-01', 5)
            self.Scales.place_matching(self.scale.id)
            self.Scales.pin(contract.id, 'retention', 'kept')
            self.Scales.unpin(contract.id)
            self.Scales.get_scales(self.scale.id)
            self.Scales.people(self.scale.id, state='drifted')
            self.env.flush_all()
        self.assertFalse(seen, "the scale wrote payroll tables: %s" % seen)
        self.env.invalidate_all()
        after = (contract.wage, contract.write_date, len(contract.sudo().advantage_ids)
                 if 'advantage_ids' in contract._fields else 0)
        self.assertEqual(before, after)
        self.assertEqual(contract.pb_scale_state, 'drifted',
                         "the cell moved under them, nobody decided: Drifted")
        self.assertIn('Drifted', contract.pb_scale_label)

    def test_s2b_spy_sees_a_real_write(self):
        emp = self._employee()
        contract = self._contract(emp, 1)
        with spy_writes(('hr_contract',)) as seen:
            contract.write({'wage': 2})
            self.env.flush_all()
        self.assertTrue(seen)

    def test_s2c_ended_version_is_kept_as_it_was(self):
        self.version.date_to = '2021-01-01'
        self.env['pb.pay.scale.version'].create({'scale_id': self.scale.id, 'date_from': '2021-01-02'})
        with self.assertRaises(Exception):
            self.Scales.save_cells(self.version.id, [
                {'grade_id': self.grade.id, 'step': 1, 'amount': 1}])

    # =====================================================================
    # S3 — the resolver
    # =====================================================================
    def test_s3_resolver(self):
        answer = self.Scales.resolve(self.job, self.company, '2026-03-01')
        self.assertTrue(answer['found'], answer['why'])
        self.assertEqual(answer['amount'], 5500000.0)
        self.assertEqual(answer['grade'], self.grade)
        self.assertEqual(answer['step'], 1)
        self.assertEqual(len(answer['steps']), 3)
        self.assertIn('step 1', answer['sentence'])
        # a job on no grade
        answer = self.Scales.resolve(self.other_job, self.company, '2026-03-01')
        self.assertFalse(answer['found'])
        self.assertIn('S8A Driver', answer['why'])
        # before the scale had amounts
        answer = self.Scales.resolve(self.job, self.company, '2019-06-01')
        self.assertFalse(answer['found'])
        # a scale only for another company
        other = self.env['res.company'].create({'name': 'S8A Other company'})
        self.scale.company_ids = [(6, 0, [other.id])]
        self.assertFalse(self.Scales.resolve(self.job, self.company, '2026-03-01')['found'])

    def test_s3b_money_must_match(self):
        usd = self.env.ref('base.USD')
        if usd == self.currency:
            usd = self.env.ref('base.EUR')
        self.scale.currency_id = usd.id
        emp = self._employee()
        answer = self.Scales.resolve(self.job, self.company, '2026-03-01', emp)
        self.assertFalse(answer['found'])
        self.assertIn(usd.name, answer['why'])

    # =====================================================================
    # S4 / S5 — People › Add a contract
    # =====================================================================
    def test_s4_empty_wage_starts_on_the_scale(self):
        emp = self._employee()
        defaults = self._wizard().get_defaults(emp.id)
        self.assertEqual(defaults['prefill']['wage'], 5500000.0)
        self.assertTrue(defaults['scale_hint']['found'])
        res = self._wizard().create_contract({
            'employee_id': emp.id, 'wage': '', 'date_start': '2026-03-01', 'activate': True})
        self.assertTrue(res.get('applied'), res)
        contract = self.env['hr.contract'].browse(res['contract_id'])
        self.assertEqual(contract.wage, 5500000.0)
        self.assertEqual(contract.pb_scale_state, 'on')
        lines = self.env['hr.contract.advantage'].sudo().search([('contract_id', '=', contract.id)])
        codes = {l.advantage_template_id.code: l.amount for l in lines}
        if 'pb_paid_by_id' in emp._fields:
            self.assertEqual(codes.get('SAMEAL'), 730000.0)
            self.assertNotIn('SAPHONE', codes, "never another scheme's pay item (SCHEMECTX)")
            change = self.env['hr.contract.advantage.change'].sudo().search(
                [('contract_id', '=', contract.id), ('advantage_template_code', '=', 'SAMEAL')])
            self.assertEqual(len(change), 1)
            self.assertEqual(change.change_source, 'pay_scale')
            self.assertEqual(fields.Date.to_string(change.effective_date), '2026-03-01')

    def test_s5_typed_wage(self):
        emp = self._employee()
        res = self._wizard().create_contract({
            'employee_id': emp.id, 'wage': 5800000, 'date_start': '2026-03-01'})
        contract = self.env['hr.contract'].browse(res['contract_id'])
        placement = self.env['pb.pay.scale.placement'].search([('contract_id', '=', contract.id)])
        self.assertEqual((placement.step_no, placement.state), (2, 'on'))
        emp2 = self._employee()
        res = self._wizard().create_contract({
            'employee_id': emp2.id, 'wage': 6400000, 'date_start': '2026-03-01',
            'pb_scale_pin_reason': 'offer_match'})
        contract = self.env['hr.contract'].browse(res['contract_id'])
        self.assertEqual(contract.wage, 6400000.0, "a typed wage always wins")
        placement = self.env['pb.pay.scale.placement'].search([('contract_id', '=', contract.id)])
        self.assertEqual((placement.state, placement.pin_reason), ('pinned', 'offer_match'))
        self.assertFalse(self.env['hr.contract.advantage'].sudo().search(
            [('contract_id', '=', contract.id), ('advantage_template_id', '=', self.template.id)]),
            "a pinned joiner gets no grade allowances")
        emp3 = self._employee()
        res = self._wizard().create_contract({
            'employee_id': emp3.id, 'wage': 1, 'date_start': '2026-03-01'})
        placement = self.env['pb.pay.scale.placement'].search(
            [('contract_id', '=', res['contract_id'])])
        self.assertEqual(placement.pin_reason, 'typed')
        # a person whose job is on no scale: nothing at all
        emp4 = self._employee(self.other_job)
        res = self._wizard().create_contract({
            'employee_id': emp4.id, 'wage': '', 'date_start': '2026-03-01'})
        contract = self.env['hr.contract'].browse(res['contract_id'])
        self.assertEqual(contract.wage, 0.0)
        self.assertFalse(contract.pb_scale_state)

    def test_s5b_suggest_reads_the_typed_wage(self):
        emp = self._employee()
        hint = self.Scales.joiner_suggest(employee_id=emp.id, wage=6100000)
        self.assertEqual(hint['typed_step'], 3)
        self.assertFalse(hint['typed_off'])
        hint = self.Scales.joiner_suggest(job_id=self.job.id, wage=6000000)
        self.assertTrue(hint['typed_off'])
        self.assertTrue(any(r['value'] == 'retention' for r in hint['reasons']))

    def test_s5c_onboard_passes_the_reason(self):
        seen = {}
        Wizard = type(self.env['pb.people.contract.wizard'])
        real = Wizard.create_contract

        def spy(this, vals):
            seen['reason'] = this.env.context.get('pb_scale_pin_reason')
            return real(this, vals)
        with patch.object(Wizard, 'create_contract', spy):
            self.env['pb.people.onboard.wizard'].with_context(**{NEWHIRE_WRITE: True}).create_employee({
                'name': 'S8A Onboard', 'job_id': self.job.id, 'with_contract': True,
                'wage': 6000000, 'date_start': '2026-03-01', 'pb_scale_pin_reason': 'retention'})
        self.assertEqual(seen.get('reason'), 'retention')

    # =====================================================================
    # S6 — Updates joiners sheet
    # =====================================================================
    def test_s6_joiner_sheet_fills_an_empty_wage(self):
        from odoo.addons.pb_updates.models.updates_joiners import WAGE
        desk = self.env['pb.updates.desk']
        j = {'vals': {'name': 'X', 'job_id': self.job.id, 'date_start': '2026-03-01'},
             'cells': {}, 'quick': False}
        desk._pbs_fill_wage(j)
        self.assertEqual(j['vals']['wage'], 5500000.0)
        self.assertEqual(j['cells'][WAGE]['status'], 'ok')
        self.assertIn('step 1', j['cells'][WAGE]['new'])
        typed = {'vals': {'name': 'Y', 'job_id': self.job.id, 'wage': 123.0}, 'cells': {}}
        desk._pbs_fill_wage(typed)
        self.assertEqual(typed['vals']['wage'], 123.0)
        self.assertNotIn(WAGE, typed['cells'])
        nojob = {'vals': {'name': 'Z'}, 'cells': {}}
        desk._pbs_fill_wage(nojob)
        self.assertNotIn('wage', nojob['vals'])

    # =====================================================================
    # S7 — Hiring "joined"
    # =====================================================================
    def test_s7_offer_with_no_pay_takes_the_scale(self):
        Offer = self.env['pb.hiring.offer']
        posts = []
        with patch.object(type(Offer), 'message_post', lambda this, **kw: posts.append(kw)):
            emp = self._employee()
            contract = self._contract(emp, 0.0, state='draft')
            Offer.browse()._pbs_after_contract(contract)
            self.assertEqual(contract.wage, 5500000.0)
            self.assertEqual(contract.pb_scale_state, 'on')
            self.assertTrue(posts and 'pay scale' in str(posts[0].get('body')))
            emp2 = self._employee()
            agreed = self._contract(emp2, 6250000.0, state='draft')
            Offer.browse()._pbs_after_contract(agreed)
            self.assertEqual(agreed.wage, 6250000.0)
            placement = self.env['pb.pay.scale.placement'].search([('contract_id', '=', agreed.id)])
            self.assertEqual(placement.pin_reason, 'offer')

    # =====================================================================
    # S8 — the screen, the drawer chip
    # =====================================================================
    def test_s8_board_people_and_placing(self):
        emp = self._employee()
        on_step = self._contract(emp, 6100000)          # exactly step 3
        emp2 = self._employee()
        off_step = self._contract(emp2, 6000000)        # no step
        board = self.Scales.get_scales(self.scale.id)
        self.assertTrue(board['allowed'])
        detail = board['scale']
        self.assertEqual(detail['health']['unplaced'], 2)
        self.assertEqual(detail['health']['match'], 1)
        self.assertEqual([c['value'] for c in detail['grades'][0]['cells']],
                         [5500000.0, 5800000.0, 6100000.0])
        out = self.Scales.place_matching(self.scale.id)
        self.assertEqual(out['placed'], 1)
        self.env.invalidate_all()
        self.assertEqual(on_step.pb_scale_state, 'on')
        self.assertFalse(off_step.pb_scale_state)
        people = self.Scales.people(self.scale.id, self.grade.id, 3)
        self.assertEqual([r['contract_id'] for r in people['rows']], [on_step.id])
        self.Scales.place(off_step.id, self.grade.id, 2)
        self.env.invalidate_all()
        self.assertEqual(off_step.pb_scale_state, 'drifted')
        chip = self.Scales.contract_chip(off_step.id)
        # WDGAP S8-D (ruling SC2): 6,000,000 on step 2 (5,800,000) is ABOVE the
        # step — kept, never offered a way down.
        self.assertNotIn('stage_wage', chip)
        self.assertIn('Above step', chip['label'])
        self.assertEqual(chip['tone'], 'warn')
        self.Scales.place(off_step.id, self.grade.id, 3)
        self.env.invalidate_all()
        chip = self.Scales.contract_chip(off_step.id)
        self.assertEqual(chip['stage_wage'], 6100000.0, "below the step: Bring to step")
        self.Scales.pin(off_step.id, 'retention')
        self.env.invalidate_all()
        self.assertEqual(off_step.pb_scale_state, 'pinned')
        self.assertIn('retain', off_step.pb_scale_label)
        self.Scales.unpin(off_step.id)
        self.env.invalidate_all()
        self.assertEqual(off_step.pb_scale_state, 'drifted')
        self.assertTrue(self.Scales.employee_chip(emp2.id)['found'])

    def test_s8b_drawer_header_carries_the_chip(self):
        emp = self._employee()
        contract = self._contract(emp, 5000000)
        Contracts = self.env['pb.contracts']
        header = Contracts._cd_header(contract, '₫', True)
        chips = header.get('extra_chips') or []
        self.assertEqual(len(chips), 1)
        self.assertIn('Not on the scale yet', chips[0]['label'])
        self.assertEqual(chips[0]['stage_wage'], 5500000.0)
        masked = Contracts._cd_header(contract, '₫', False)
        self.assertNotIn('stage_wage', masked['extra_chips'][0], "a masked wage stays masked")

    def test_s8c_grades_jobs_versions_packages(self):
        out = self.Scales.save_grade(self.scale.id, 0, {'name': 'Shift lead'})
        grade = self.env['pb.pay.scale.grade'].browse(out['grade_id'])
        self.assertEqual(grade.sequence, 30)
        rows = self.Scales.jobs_for_grade(grade.id)
        self.assertIn(self.link.id, [r['link_id'] for r in rows])
        self.Scales.link_job(grade.id, self.link.id)
        self.assertEqual(self.link.pb_scale_grade_id, grade)
        self.Scales.unlink_job(self.link.id)
        self.assertFalse(self.link.pb_scale_grade_id)
        self.Scales.move_grade(grade.id, 'up')
        self.assertLess(grade.sequence, self.grade2.sequence)
        res = self.Scales.new_version(self.scale.id, '2030-01-01', 10)
        new = self.env['pb.pay.scale.version'].browse(res['version_id'])
        self.assertEqual(new.value_of(self.grade, 1), 6050000.0)
        self.assertEqual(fields.Date.to_string(self.version.date_to), '2029-12-31')
        self.assertEqual(len(new.package_ids), 2, "allowances carried into the new version")
        self.Scales.save_package(new.id, self.grade.id, [{'template_id': self.template.id, 'amount': 800000}])
        self.assertEqual(new.package_ids.filtered(lambda p: p.grade_id == self.grade).mapped('amount'), [800000.0])
        self.Scales.remove_version(new.id)
        self.assertFalse(self.version.date_to, "the previous version is open-ended again")
        made = self.Scales.save_scale(0, {'name': 'S8A new', 'country_code': self.country,
                                          'step_count': 2, 'grades': ['A', 'B']})
        scale = self.env['pb.pay.scale'].browse(made['scale_id'])
        self.assertEqual(scale.grade_ids.mapped('name'), ['A', 'B'])
        self.assertEqual(len(scale.version_ids), 1)

    def test_s8d_start_from_what_you_pay(self):
        for wage in (5000000, 5400000, 6000000, 6600000, 7000000):
            self._contract(self._employee(), wage)
        out = self.Scales.propose_from_wages(self.scale.id)
        self.assertTrue(out['ok'])
        cells = {c['step']: c['amount'] for c in out['cells'] if c['grade_id'] == self.grade.id}
        self.assertEqual(sorted(cells), [1, 2, 3])
        self.assertLess(cells[1], cells[3])
        self.assertEqual(self.version.value_of(self.grade, 1), 5500000.0, "nothing saved")

    # =====================================================================
    # S9 — rights
    # =====================================================================
    def _user(self, login, groups):
        return self.env['res.users'].with_context(no_reset_password=True).create({
            'name': login, 'login': login, 'company_id': self.company.id,
            'company_ids': [(6, 0, [self.company.id])],
            'group_ids': [(6, 0, [self.env.ref(g).id for g in groups])]})

    def test_s9_rights(self):
        plain = self._user('s8a_plain', ['base.group_user'])
        viewer = self._user('s8a_viewer', ['base.group_user', 'pb_pay.group_pay_viewer'])
        self.env.flush_all()
        self.env.invalidate_all()
        board = self.Scales.with_user(plain).get_scales()
        self.assertFalse(board['allowed'])
        self.assertFalse(board['scales'])
        with self.assertRaises(AccessError):
            self.Scales.with_user(plain).save_cells(self.version.id, [])
        with self.assertRaises(AccessError):
            self.Scales.with_user(plain).people(self.scale.id)
        self.assertIsNone(self.Scales.with_user(plain).contract_chip(0))
        board = self.Scales.with_user(viewer).get_scales()
        self.assertTrue(board['allowed'])
        self.assertFalse(board['can_write'])
        with self.assertRaises(AccessError):
            self.Scales.with_user(viewer).save_cells(self.version.id, [])
        with self.assertRaises(AccessError):
            self.env['pb.pay.scale'].with_user(plain).search([])

    # =====================================================================
    # S10 — golden: an untouched contract's payslip computes the same
    # =====================================================================
    def test_s10_golden_payslip_untouched(self):
        emp = self._employee(self.other_job)
        contract = self._contract(emp, 9000000)
        slip = self.env['hr.payslip'].create({
            'employee_id': emp.id, 'contract_id': contract.id, 'name': 'S8A golden',
            'formula_config_id': self.cfg.id, 'company_id': self.company.id,
            'date_from': '2026-06-01', 'date_to': '2026-06-30',
            'formula_input_values': json.dumps({'SAMEAL': 100000})})

        def snapshot():
            slip.compute_sheet()
            self.env.flush_all()
            slip.invalidate_recordset()
            return json.dumps(sorted((l.code, l.amount, l.total) for l in slip.line_ids))
        before = snapshot()
        other = self._contract(self._employee(), 5500000)
        self.Scales.place(other.id, self.grade.id, 1)
        self.Scales.save_cells(self.version.id, [{'grade_id': self.grade.id, 'step': 1, 'amount': 5600000}])
        self.Scales.new_version(self.scale.id, '2026-06-15', 3)
        self._wizard().create_contract({'employee_id': self._employee().id, 'wage': '',
                                        'date_start': '2026-06-01'})
        self.assertEqual(snapshot(), before)

    # =====================================================================
    # S11 — white-label
    # =====================================================================
    def test_s11_no_product_name_on_screen(self):
        bad = []
        for root, _dirs, files in os.walk(HERE):
            if '/tests' in root or '/i18n' in root:
                continue
            for name in files:
                if not name.endswith(('.py', '.js', '.xml')):
                    continue
                with open(os.path.join(root, name), encoding='utf-8') as fh:
                    text = fh.read()
                visible = re.findall(r'_t\("([^"]+)"', text) + re.findall(r'_\(\s*"([^"]+)"', text) \
                    + re.findall(r">([^<>{}]+)<", text) + re.findall(r"string='([^']+)'", text)
                bad += ['%s: %s' % (name, v) for v in visible if 'odoo' in v.lower()]
        self.assertFalse(bad)
