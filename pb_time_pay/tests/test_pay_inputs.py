# Part of Payobook. See LICENSE file for full copyright and licensing details.
"""S5-B T20–T27: what reaches a payslip.

T20 is the golden rail of the phase: with no new data (no time off given, no
minutes confirmed) every payslip — no run, Regular, Top-up, Extra — computes
byte-identically with and without this module's rung, down to the stored
input values, their recorded sources, the computed values and every line.
"""

import copy
import json
from datetime import date, timedelta
from unittest.mock import patch

from odoo.tests import tagged

from odoo.addons.pb_time_pay.models.hr_payslip import HrPayslipTimePay

from .common import TimePayCase

D_FROM = date(2026, 6, 1)
D_TO = date(2026, 6, 30)


def _passthrough(self, config, provenance=None):
    """This module's rung, removed: straight to the rungs below it."""
    return super(HrPayslipTimePay, self)._get_formula_input_values(
        config, provenance=provenance)


@tagged('post_install', '-at_install', 'wdgap_s5b')
class TestPayInputs(TimePayCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Run = cls.env['hr.payslip.run']
        cls.category = cls.env['hr.salary.rule.category'].search([], limit=1)
        cls.config = cls._scheme('S5B Monthly', 'S5BMONTH')
        cls.contract = cls.env['hr.contract'].sudo().create({
            'name': 'S5B contract', 'employee_id': cls.shifty.id,
            'company_id': cls.company.id, 'wage': 10_000_000.0,
            'state': 'open', 'date_start': '2026-01-01'})

    @classmethod
    def _scheme(cls, name, code, late=True):
        cfg = cls.env['hr.formula.config'].sudo().create({
            'name': name, 'code': code, 'cycle_type': 'end_cycle',
            'country_code': 'VN', 'company_id': cls.company.id,
            'state': 'active'})
        seq = 1
        inputs = [('Basic', 'BASIC'), ('OT weekday', 'OTHRS150'),
                  ('OT rest day', 'OTHRS200'), ('Bonus hours', 'BONHRS')]
        if late:
            inputs += [('Late minutes', 'LATEMIN'), ('Early minutes', 'EARLYMIN')]
        for label, rcode in inputs:
            cls._rule(cfg, label, rcode, seq, 'earning')
            seq += 1
        formulas = [('OT pay', 'TPOTPAY', '=OTHRS150*1000+OTHRS200*2000+BONHRS*500', 'earning')]
        if late:
            formulas.append(('Late deduction', 'TPLATEDED',
                             '=-(LATEMIN+EARLYMIN)*100', 'deduction'))
            formulas.append(('Net', 'TPNETPAY', '=BASIC+TPOTPAY+TPLATEDED', 'net'))
        else:
            formulas.append(('Net', 'TPNETPAY', '=BASIC+TPOTPAY', 'net'))
        for label, rcode, formula, role in formulas:
            cls._rule(cfg, label, rcode, 10 + seq, role, 'formula', formula)
            seq += 1
        return cfg

    @classmethod
    def _rule(cls, cfg, name, code, seq, role, column_type='input', formula=None):
        vals = {'config_id': cfg.id, 'name': name, 'code': code,
                'column_type': column_type, 'sequence': seq,
                'default_value': 0.0, 'value_kind': 'money',
                'net_role': role, 'appears_on_payslip': True,
                'category_id': cls.category.id}
        if formula:
            vals['excel_formula'] = formula
        return cls.env['hr.formula.rule'].sudo().create(vals)

    def _slip(self, kind=None, cfg=None):
        run = False
        if kind:
            vals = {'name': 'S5B %s' % kind, 'date_start': D_FROM,
                    'date_end': D_TO}
            if 'pb_run_kind' in self.Run._fields:
                if kind not in dict(self.Run._fields['pb_run_kind'].selection):
                    self.skipTest('no %s run on this build' % kind)
                vals['pb_run_kind'] = kind
            if 'company_id' in self.Run._fields:
                vals['company_id'] = self.company.id
            run = self.Run.sudo().create(vals)
        return self.env['hr.payslip'].sudo().create({
            'name': 'S5B slip', 'employee_id': self.shifty.id,
            'contract_id': self.contract.id,
            'payslip_run_id': run.id if run else False,
            'date_from': D_FROM, 'date_to': D_TO,
            'company_id': self.company.id,
            'formula_config_id': (cfg or self.config).id,
            'calculation_method': 'formula'})

    def _snapshot(self, slip):
        slip.invalidate_recordset()
        return {
            'inputs': json.loads(slip.formula_input_values or '{}'),
            'sources': json.loads(slip.formula_input_sources or '{}'),
            'computed': json.loads(slip.formula_computed_values or '{}'),
            'lines': sorted((l.code, l.amount) for l in slip.line_ids),
        }

    def _late_row(self, day, minutes, kind='late', state='confirmed'):
        return self.Late.sudo().create({
            'employee_id': self.shifty.id, 'company_id': self.company.id,
            'date': day, 'kind': kind, 'minutes': minutes, 'state': state})

    # ================================================================ T20
    def test_t20_golden_no_new_data_is_byte_identical(self):
        self._approved(self.shifty, date(2026, 6, 10), 5.0, bonus=1.5)
        self._approved(self.shifty, date(2026, 6, 13), 4.0, kind='weekend')
        # a confirmed minute OUTSIDE the period and an EXCUSED one inside it
        # are not new data for June
        self._late_row(date(2026, 5, 29), 20)
        self._late_row(date(2026, 6, 3), 40, state='excused')
        for kind in (None, 'regular', 'topup', 'extra'):
            with self.subTest(run=kind):
                slip = self._slip(kind)
                slip.compute_sheet()
                with_rung = self._snapshot(slip)
                with patch.object(HrPayslipTimePay, '_get_formula_input_values',
                                  _passthrough):
                    slip.compute_sheet()
                without = self._snapshot(slip)
                fed = kind in (None, 'regular')
                self.assertEqual(with_rung['inputs'].get('OTHRS150'),
                                 5.0 if fed else 0.0,
                                 'the fixture really carries overtime')
                self.assertEqual(with_rung, without)
                self.assertEqual(
                    json.dumps(with_rung, sort_keys=True),
                    json.dumps(without, sort_keys=True))
                self.assertFalse(self.Late.sudo().search(
                    [('payslip_id', '=', slip.id)]),
                    'nothing is held when nothing is confirmed in the period')

    def test_t20b_a_scheme_without_the_items_is_byte_identical(self):
        plain = self._scheme('S5B Plain', 'S5BPLAIN', late=False)
        self._late_row(date(2026, 6, 3), 40)
        slip = self._slip('regular', cfg=plain)
        prov_with, prov_without = {}, {}
        got = slip._get_formula_input_values(plain, provenance=prov_with)
        base = _passthrough(slip, plain, provenance=prov_without)
        self.assertEqual(got, base)
        self.assertEqual(prov_with, prov_without)

    # ================================================================ T21
    def test_t21_time_off_is_not_also_paid_bridge(self):
        self._approved(self.shifty, date(2026, 6, 10), 5.0, bonus=1.5,
                       choice='time_off')
        self._approved(self.shifty, date(2026, 6, 11), 3.0)
        self._approved(self.shifty, date(2026, 6, 13), 4.0, kind='weekend',
                       choice='time_off')
        slip = self._slip('regular')
        got = slip._get_formula_input_values(self.config)
        base = _passthrough(slip, self.config)
        self.assertEqual(base['OTHRS150'], 8.0)
        self.assertEqual(base['BONHRS'], 1.5)
        self.assertEqual(got['OTHRS150'], 3.0, 'only the paid hours are paid')
        self.assertEqual(got['OTHRS200'], 0.0)
        self.assertEqual(got['BONHRS'], 0.0)

    def test_t21b_a_topup_was_never_fed_so_nothing_is_taken(self):
        self._approved(self.shifty, date(2026, 6, 10), 5.0, choice='time_off')
        slip = self._slip('topup')
        self.assertEqual(slip._get_formula_input_values(self.config),
                         _passthrough(slip, self.config))

    def test_t22_time_off_is_not_also_paid_approved_weeks(self):
        from odoo.addons.pb_timesheet_approval.models.timesheet_packet import (
            _TS_CHAIN_KEY, _TS_CHAIN_TOKEN)
        monday = date(2026, 6, 1)
        self.company.sudo().pb_timesheet_payroll = True
        for i in range(5):
            day = monday + timedelta(days=i)
            self._punch(self.shifty, day, 8, 16, source='grid')
        self._approved(self.shifty, monday, 2.0, choice='time_off')
        self._approved(self.shifty, monday + timedelta(days=1), 3.0)
        Packet = self.env['pb.timesheet.packet'].sudo()
        packet = Packet.packet_for(self.shifty, monday)
        packet._write_snapshot()
        packet.with_context(**{_TS_CHAIN_KEY: _TS_CHAIN_TOKEN}).write(
            {'state': 'approved'})
        slip = self._slip('regular')
        base = _passthrough(slip, self.config)
        got = slip._get_formula_input_values(self.config)
        self.assertEqual(base['OTHRS150'], 5.0, 'the week answered')
        self.assertEqual(got['OTHRS150'], 3.0)

    def test_t23_application_facts_take_time_off_out(self):
        paid = self._approved(self.shifty, date(2026, 6, 10), 3.0)
        off = self._approved(self.shifty, date(2026, 6, 11), 2.0, bonus=1.0,
                             choice='time_off')
        src = [['hr.overtime.request', paid.id, 'x'],
               ['hr.overtime.request', off.id, 'x']]
        facts = {
            'period.ot.weekday.approved_hours': {
                'value': 5.0, 'status': 'resolved', 'reason': '',
                'source_ids': src, 'evidence': {}},
            'period.approved_bonus_hours': {
                'value': 1.0, 'status': 'resolved', 'reason': '',
                'source_ids': src, 'evidence': {}},
            'period.ot.weekend.approved_hours': {
                'value': 0.0, 'status': 'resolved', 'reason': '',
                'source_ids': src, 'evidence': {}},
        }
        before = copy.deepcopy(facts)
        self.config._pb_tp_take_back_facts(facts)
        self.assertEqual(facts['period.ot.weekday.approved_hours']['value'], 3.0)
        self.assertEqual(facts['period.approved_bonus_hours']['value'], 0.0)
        self.assertEqual(
            facts['period.ot.weekday.approved_hours']['evidence'],
            {'time_off_in_lieu_hours': 2.0})
        self.assertEqual(facts['period.ot.weekend.approved_hours'],
                         before['period.ot.weekend.approved_hours'],
                         'a fact with nothing taken out is untouched (W2A-2)')
        # no time-off request among a fact's sources: exactly as it was
        facts2 = copy.deepcopy(before)
        facts2['period.ot.weekday.approved_hours']['source_ids'] = [src[0]]
        facts2['period.approved_bonus_hours']['source_ids'] = [src[0]]
        snapshot = copy.deepcopy(facts2)
        self.config._pb_tp_take_back_facts(facts2)
        self.assertEqual(facts2, snapshot)

    # ================================================================ T24
    def test_t24_confirmed_minutes_are_paid_once(self):
        a = self._late_row(date(2026, 6, 3), 16)
        b = self._late_row(date(2026, 6, 4), 30)
        e = self._late_row(date(2026, 6, 4), 20, kind='early')
        self._late_row(date(2026, 6, 5), 45, state='excused')
        slip = self._slip('regular')
        prov = {}
        values = slip._get_formula_input_values(self.config, provenance=prov)
        self.assertEqual(values['LATEMIN'], 46.0)
        self.assertEqual(values['EARLYMIN'], 20.0)
        self.assertEqual(prov['LATEMIN']['via'], 'late_minutes')
        self.assertEqual((a | b | e).mapped('payslip_id'), slip)
        # recalculating is idempotent
        again = slip._get_formula_input_values(self.config)
        self.assertEqual((again['LATEMIN'], again['EARLYMIN']), (46.0, 20.0))
        # a second regular payslip for the same month takes nothing
        other = self._slip('regular')
        other_values = other._get_formula_input_values(self.config)
        self.assertEqual(other_values, _passthrough(other, self.config))
        self.assertEqual((a | b | e).mapped('payslip_id'), slip)
        # a top-up never takes minutes
        topup = self._slip('topup')
        self.assertEqual(topup._get_formula_input_values(self.config),
                         _passthrough(topup, self.config))

    def test_t24b_letting_go(self):
        a = self._late_row(date(2026, 6, 3), 16)
        slip = self._slip('regular')
        slip._get_formula_input_values(self.config)
        self.assertEqual(a.payslip_id, slip)
        # excused after it was taken: the payslip lets go on its next pass
        a.sudo().write({'state': 'excused'})
        values = slip._get_formula_input_values(self.config)
        self.assertNotEqual(values.get('LATEMIN'), 16.0)
        a.invalidate_recordset()
        self.assertFalse(a.payslip_id)
        # a deleted payslip lets go too
        a.sudo().write({'state': 'confirmed'})
        slip._get_formula_input_values(self.config)
        self.assertEqual(a.payslip_id, slip)
        slip.sudo().unlink()
        a.invalidate_recordset()
        self.assertFalse(a.payslip_id)
        # and a cancelled payslip's minutes may be taken by the next one
        slip2 = self._slip('regular')
        slip2._get_formula_input_values(self.config)
        slip2.sudo().write({'state': 'cancel'})
        slip3 = self._slip('regular')
        self.assertEqual(slip3._get_formula_input_values(self.config)['LATEMIN'],
                         16.0)
        self.assertEqual(a.payslip_id, slip3)

    def test_t24c_full_compute_pays_the_minutes_through_the_formula(self):
        self._late_row(date(2026, 6, 3), 30)
        slip = self._slip('regular')
        slip.compute_sheet()
        snap = self._snapshot(slip)
        self.assertEqual(snap['inputs'].get('LATEMIN'), 30.0)
        lines = dict(snap['lines'])
        self.assertEqual(lines.get('TPLATEDED'), -3000.0)

    def test_t25_application_source_answers_free_and_own_rows(self):
        self.env['hr.formula.rule'].sudo().search([
            ('config_id', '=', self.config.id), ('code', '=', 'LATEMIN')]).write(
            {'application_source_key': 'time.late_minutes'})
        a = self._late_row(date(2026, 6, 3), 16)
        b = self._late_row(date(2026, 6, 4), 30)
        holder = self._slip('regular')
        b.sudo().write({'payslip_id': holder.id})
        facts = self.config.with_context(
            pb_application_payslip_id=False)._application_domain_values(
            self.shifty, self.contract, D_FROM, D_TO)
        fact = facts['time.late_minutes']
        self.assertEqual(fact['status'], 'resolved')
        self.assertEqual(fact['value'], 16.0, 'a row held elsewhere is not offered')
        self.assertEqual(fact['evidence']['pb_late_ids'], [a.id])
        facts = self.config.with_context(
            pb_application_payslip_id=holder.id)._application_domain_values(
            self.shifty, self.contract, D_FROM, D_TO)
        self.assertEqual(facts['time.late_minutes']['value'], 46.0)
        self.assertIn('time.late_minutes',
                      self.config._application_source_catalogue())
