# -*- coding: utf-8 -*-
"""WDGAP W2-D1 — past-month re-work: the numbered cases of the handover §4.

T1   no overlay -> the stored lines come back (fixture via the payslip's own
     line maker), and on the genuine compute path (contract wage -> BASIC)
T2   a contract change effective two months back: per-month differences equal
     a hand-computed forward evaluation (progressive tax, insurance ceiling,
     proration of the first month); a change known when the payslip was
     computed and a change left out are not applied
T3   a what-if value
T4   baseline drift is labelled and differences are net of it; T4b the scheme
     changed since -> "today's version" flag
T5   a formula that raises is isolated: that payslip names the pay item, the
     rest continue (R6)
T6   R1 read-only: no row outside the re-work's own tables is written; counts
     and stamps of payslips, lines, inputs, loan instalments, one-offs, retro
     rows and contract changes unchanged; a loan instalment is fed as stored;
     T6b the spy is live
T7   an Extra-run payslip is listed as not re-worked
T8   two currencies: SGD cents, per-currency roll-up and board rows (R4)
T9   rights and companies
T10  deterministic (R3)
T11  caps (months, people)
T12  Excel export, one block per currency
T13  silent install: empty board, one palette entry, no job, no "Odoo"
T14  a change already paid back by the existing retro flow is not counted again
T15  chunks: the same result in chunks of 2; ids outside the re-work are ignored
T16  timing per 40 payslips (logged)
"""
import base64
import io
import json
import logging
import os
import re
import time
from contextlib import contextmanager
from datetime import date, timedelta
from unittest.mock import patch

from odoo import fields
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.sql_db import Cursor
from odoo.tests import TransactionCase, tagged

from odoo.addons.pb_hr_payroll_formula.formula_engine.excel_semantics import excel_round
from odoo.addons.pb_retro.models import retro_review

_logger = logging.getLogger(__name__)

AUG = (date(2026, 8, 1), date(2026, 8, 31))
SEP = (date(2026, 9, 1), date(2026, 9, 30))
OCT = (date(2026, 10, 1), date(2026, 10, 31))
CAP = 46_800_000


def hand(basic):
    """The progressive scheme, worked by hand (the forward evaluation)."""
    si = min(basic, CAP) * 0.105
    t = max(basic - si - 11_000_000, 0)
    if t <= 5_000_000:
        pit = t * 0.05
    elif t <= 10_000_000:
        pit = 250_000 + (t - 5_000_000) * 0.1
    elif t <= 18_000_000:
        pit = 750_000 + (t - 10_000_000) * 0.15
    else:
        pit = 1_950_000 + (t - 18_000_000) * 0.2
    return {'SIEMP': si, 'PITAX': pit, 'NETPAY': basic - si - pit, 'BASICPAY': basic,
            'SICOMP': min(basic, CAP) * 0.175}


@tagged('post_install', '-at_install')
class TestW2d1Retro(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.vnd = cls.env.ref('base.VND')
        cls.vnd.active = True
        cls.sgd = cls.env.ref('base.SGD')
        cls.sgd.active = True
        cls.company = cls.env['res.company'].create({'name': 'W2D1 Co', 'currency_id': cls.vnd.id})
        cls.env.user.company_ids = [(4, cls.company.id)]
        cls.env.user.company_id = cls.company
        cls.env = cls.env(context=dict(cls.env.context, allowed_company_ids=[cls.company.id],
                                       tracking_disable=True, mail_notrack=True))
        cls.Review = cls.env['pb.retro.review']
        cls.Board = cls.env['pb.retro.board']
        cls.cat = {
            'earning': cls.env.ref('om_hr_payroll.BASIC'),
            'deduction': cls.env.ref('om_hr_payroll.DED'),
            'net': cls.env.ref('om_hr_payroll.NET'),
            'employer_cost': cls.env.ref('om_hr_payroll.COMP'),
        }
        cls.calendar = cls.company.resource_calendar_id or cls.env['resource.calendar'].create(
            {'name': 'W2D1 Hours', 'company_id': cls.company.id})
        cls._seq = 0

    # ------------------------------------------------------------ fixtures
    def _scheme(self, country='VN', company=None, state='active'):
        company = company or self.company
        type(self)._seq += 1
        return self.env['hr.formula.config'].create({
            'name': 'W2D1 Scheme %s' % self._seq, 'code': 'WTWODONE%s' % self._seq,
            'country_code': country, 'state': state, 'company_id': company.id,
            'cycle_type': 'end_cycle',
        })

    def _rule(self, cfg, code, name, kind, formula=None, role=False, seq=10, on_slip=True,
              default=0.0, **extra):
        vals = {'config_id': cfg.id, 'code': code, 'name': name, 'column_type': kind,
                'sequence': seq, 'appears_on_payslip': on_slip, 'net_role': role,
                'default_value': default, 'value_kind': 'money'}
        if role in self.cat:
            vals['category_id'] = self.cat[role].id
        if formula:
            vals['excel_formula'] = formula
        vals.update(extra)
        return self.env['hr.formula.rule'].create(vals)

    def _progressive(self, **kw):
        """Insurance on a capped base, a marginal tax ladder, a loan line."""
        cfg = self._scheme(**kw)
        b = self._rule(cfg, 'BASICPAY', 'Basic pay', 'input', role='earning', seq=10).column_letter
        loan = self._rule(cfg, 'LOANINST', 'Loan instalment', 'input', role='deduction',
                          seq=15).column_letter
        base = self._rule(cfg, 'INSBASE', 'Insurance base', 'formula', '=MIN(%s,%s)' % (b, CAP),
                          role='info', seq=20, on_slip=False).column_letter
        si = self._rule(cfg, 'SIEMP', 'Social insurance', 'formula', '=%s*0.105' % base,
                        role='deduction', seq=30).column_letter
        t = self._rule(cfg, 'TAXABLE', 'Taxable income', 'formula',
                       '=MAX(%s-%s-11000000,0)' % (b, si), role='info', seq=40,
                       on_slip=False).column_letter
        pit = self._rule(
            cfg, 'PITAX', 'Income tax', 'formula',
            '=IF(%(t)s<=5000000,%(t)s*0.05,IF(%(t)s<=10000000,250000+(%(t)s-5000000)*0.1,'
            'IF(%(t)s<=18000000,750000+(%(t)s-10000000)*0.15,1950000+(%(t)s-18000000)*0.2)))'
            % {'t': t}, role='deduction', seq=50).column_letter
        self._rule(cfg, 'NETPAY', 'Take-home', 'formula', '=%s-%s-%s-%s' % (b, si, pit, loan),
                   role='net', seq=60)
        self._rule(cfg, 'SICOMP', 'Social insurance (employer)', 'formula',
                   '=%s*0.175' % base, role='employer_cost', seq=70)
        return cfg

    def _person(self, name=None, company=None, wage=1000.0):
        company = company or self.company
        type(self)._seq += 1
        emp = self.env['hr.employee'].create({
            'name': name or 'W2D1 Person %s' % self._seq, 'company_id': company.id})
        contract = self.env['hr.contract'].create({
            'name': 'W2D1 contract %s' % self._seq, 'employee_id': emp.id, 'wage': wage,
            'state': 'open', 'date_start': '2026-01-01', 'company_id': company.id,
            'resource_calendar_id': self.calendar.id})
        return emp, contract

    def _run(self, cfg, period, kind='regular', company=None):
        Run = self.env['hr.payslip.run']
        type(self)._seq += 1
        vals = {'name': 'W2D1 run %s' % self._seq, 'date_start': period[0],
                'date_end': period[1]}
        if 'pb_formula_config_id' in Run._fields:
            vals['pb_formula_config_id'] = cfg.id
        if 'company_id' in Run._fields:
            vals['company_id'] = (company or self.company).id
        if 'pb_run_kind' in Run._fields:
            vals['pb_run_kind'] = kind
        return Run.create(vals)

    def _slip(self, cfg, emp, contract, period, inputs, run=None, kind='regular', company=None):
        """A finished payslip worked out the way the payslip path stores one:
        the real evaluator and the real line maker, then Done."""
        company = company or self.company
        run = run or self._run(cfg, period, kind, company)
        slip = self.env['hr.payslip'].create({
            'name': 'W2D1 slip %s %s' % (emp.name, period[0]), 'employee_id': emp.id,
            'contract_id': contract.id, 'payslip_run_id': run.id,
            'date_from': period[0], 'date_to': period[1], 'company_id': company.id,
            'formula_config_id': cfg.id,
        })
        rules = cfg.rule_ids.sorted(lambda r: r.sequence)
        computed, _log = slip._evaluate_rules_with_dependencies(rules, dict(inputs))
        slip.formula_input_values = json.dumps(inputs)
        slip.formula_computed_values = json.dumps(computed, default=str)
        slip._create_payslip_lines_from_formulas(rules, computed)
        slip._pb_stamp_scheme_content(cfg)
        slip.write({'state': 'done'})
        return slip

    def _change(self, contract, code, old, new, effective, entered_days=1, source='manual'):
        template = self.env['hr.contract.advantage.template'].search(
            [('code', '=', code)], limit=1) or self.env['hr.contract.advantage.template'].create(
            {'name': code, 'code': code})
        return self.env['hr.contract.advantage.change'].create({
            'contract_id': contract.id, 'advantage_template_id': template.id,
            'old_amount': old, 'new_amount': new, 'effective_date': effective,
            'change_source': source,
            'changed_at': fields.Datetime.now() + timedelta(days=entered_days),
        })

    def _review(self, cfg, first, last, **kw):
        vals = {'config_id': cfg.id, 'company_id': cfg.company_id.id or self.company.id,
                'month_from': first, 'month_to': last, 'reason': 'W2D1 test'}
        vals.update(kw)
        return self.Review.create(vals)

    def _lines(self, review):
        return [(l.slip_row_id.payslip_id.id, l.code, l.was, l.baseline, l.would_be, l.diff,
                 l.cause) for l in review.line_ids.sorted(
                     lambda l: (l.slip_row_id.payslip_id.id, l.sequence))]

    def _row(self, review, slip):
        return review.slip_ids.filtered(lambda s: s.payslip_id == slip)

    def _diffs(self, review, slip):
        return {l.code: l.diff for l in self._row(review, slip).line_ids}

    def _three_months(self, basic=44_000_000, loan=0.0):
        cfg = self._progressive()
        emp, contract = self._person()
        slips = [self._slip(cfg, emp, contract, p, {'BASICPAY': basic, 'LOANINST': loan})
                 for p in (AUG, SEP, OCT)]
        return cfg, emp, contract, slips

    # =====================================================================
    # T1 — no overlay gives the stored lines back
    # =====================================================================
    def test_01_no_overlay_reproduces_the_stored_lines(self):
        cfg, emp, _c, slips = self._three_months()
        review = self._review(cfg, AUG[0], OCT[0])
        review.action_work_out()
        self.assertEqual(review.state, 'done')
        self.assertEqual(sorted(review.slip_ids.mapped('status')), ['same'] * 3)
        self.assertFalse(review.line_ids)
        self.assertFalse(any(review.slip_ids.mapped('drift_json')))
        self.assertFalse(any(review.slip_ids.mapped('scheme_changed')))
        row = self._row(review, slips[0])
        self.assertAlmostEqual(row.was_net, excel_round(hand(44_000_000)['NETPAY']), places=2)

    def test_01b_genuine_compute_path_reproduces(self):
        cfg = self._scheme()
        b = self._rule(cfg, 'BASIC', 'Basic salary', 'input', role='earning').column_letter
        tax = self._rule(cfg, 'PITAX', 'Income tax', 'formula', '=ROUND(%s*0.1,0)' % b,
                         role='deduction', seq=20).column_letter
        self._rule(cfg, 'NETPAY', 'Take-home', 'formula', '=%s-%s' % (b, tax), role='net',
                   seq=30)
        emp, contract = self._person(wage=12_345_678)
        run = self._run(cfg, SEP)
        slip = self.env['hr.payslip'].create({
            'name': 'W2D1 genuine', 'employee_id': emp.id, 'contract_id': contract.id,
            'payslip_run_id': run.id, 'date_from': SEP[0], 'date_to': SEP[1],
            'company_id': self.company.id, 'formula_config_id': cfg.id})
        slip.compute_sheet_with_formulas()
        self.assertEqual(json.loads(slip.formula_input_values).get('BASIC'), 12_345_678)
        slip.write({'state': 'done'})
        review = self._review(cfg, SEP[0], SEP[0])
        review.action_work_out()
        self.assertEqual(review.slip_ids.status, 'same', review.slip_ids.drift_json)

    # =====================================================================
    # T2 — a contract change effective two months back, by hand
    # =====================================================================
    def test_02_contract_change_two_months_back_matches_the_hand(self):
        cfg, emp, contract, slips = self._three_months(basic=44_000_000)
        self._change(contract, 'BASICPAY', 44_000_000, 50_000_000, date(2026, 8, 16))
        # known when the payslips were computed: never applied
        self._change(contract, 'BASICPAY', 44_000_000, 44_500_000, date(2026, 7, 1),
                     entered_days=-1)
        review = self._review(cfg, AUG[0], OCT[0])
        review.action_work_out()
        # August: 16 of 31 days at the new amount (proration places: 2)
        aug_basic = 44_000_000 + excel_round(6_000_000 * 16 / 31, 2)
        self.assertGreater(aug_basic, CAP, "the fixture must cross the insurance cap")
        expected = {slips[0]: aug_basic, slips[1]: 50_000_000, slips[2]: 50_000_000}
        old = hand(44_000_000)
        for slip, basic in expected.items():
            new = hand(basic)
            diffs = self._diffs(review, slip)
            row = self._row(review, slip)
            self.assertEqual(row.status, 'changed')
            for code in ('BASICPAY', 'SIEMP', 'PITAX', 'NETPAY', 'SICOMP'):
                self.assertAlmostEqual(diffs.get(code, 0.0), excel_round(new[code] - old[code]),
                                       places=6, msg='%s %s' % (slip.date_from, code))
            self.assertAlmostEqual(row.diff_net, excel_round(new['NETPAY'] - old['NETPAY']),
                                   places=6)
            self.assertAlmostEqual(row.diff_employer_cost,
                                   excel_round(new['SICOMP'] - old['SICOMP']), places=6)
            # insurance stops at the cap: September and October are equal
        self.assertEqual(self._diffs(review, slips[1]), self._diffs(review, slips[2]))
        # the cause of every line is the one change that was applied
        overlay = json.loads(self._row(review, slips[0]).overlay_json)
        applied = [o for o in overlay if o.get('applied')]
        self.assertEqual(len(applied), 1)
        self.assertEqual(applied[0]['covered'], 16.0)
        self.assertEqual(applied[0]['period'], 31.0)
        cause = json.loads(self._row(review, slips[0]).line_ids.filtered(
            lambda l: l.code == 'PITAX').cause)
        self.assertEqual(cause, [{'code': 'BASICPAY', 'id': applied[0]['change_id'],
                                  'kind': 'contract'}])
        # the board's roll-up and its sentence
        data = self.Board.get_review(review.id)
        self.assertEqual(data['strips'][0]['people'], 1)
        self.assertTrue(data['strips'][0]['net'].startswith('+'))
        self.assertEqual(len(data['changes']), 1)      # the one known in time is not listed
        self.assertEqual(data['changes'][0]['months_label'], 'Aug 2026, Sep 2026, Oct 2026')
        people = self.Board.get_people(review.id)
        self.assertEqual(people['total'], 1)
        self.assertEqual(len(people['people'][0]['months']), 3)

    def test_02b_a_change_left_out_is_not_applied(self):
        cfg, emp, contract, slips = self._three_months()
        change = self._change(contract, 'BASICPAY', 44_000_000, 50_000_000, date(2026, 8, 16))
        review = self._review(cfg, AUG[0], OCT[0], excluded_change_ids=[(6, 0, change.ids)])
        review.action_work_out()
        self.assertFalse(review.line_ids)
        self.assertEqual(set(review.slip_ids.mapped('status')), {'same'})
        preview = self.Board.scope_preview({'config_id': cfg.id, 'month_from': AUG[0],
                                            'month_to': OCT[0]})
        self.assertEqual(preview['payslips'], 3)
        self.assertEqual(len(preview['changes']), 1)
        self.assertEqual(preview['changes'][0]['months'], ['Aug 2026', 'Sep 2026', 'Oct 2026'])

    # =====================================================================
    # T3 — a what-if value
    # =====================================================================
    def test_03_whatif_value(self):
        cfg, emp, contract, slips = self._three_months()
        res = self.Board.save_review({
            'config_id': cfg.id, 'month_from': SEP[0], 'month_to': SEP[0], 'reason': 'try 30M',
            'whatifs': [{'payslip_id': slips[1].id, 'code': 'BASICPAY', 'value': 30_000_000,
                         'note': 'agreed figure'}]})
        review = self.Review.browse(res['id'])
        review.action_work_out()
        self.assertEqual(len(review.slip_ids), 1)
        diffs = self._diffs(review, slips[1])
        self.assertAlmostEqual(diffs['NETPAY'], excel_round(hand(30_000_000)['NETPAY']
                                                            - hand(44_000_000)['NETPAY']))
        self.assertAlmostEqual(diffs['BASICPAY'], -14_000_000)
        # a what-if needs a note, a covered payslip and a pay item
        with self.assertRaises(UserError):
            self.Board.save_review({'config_id': cfg.id, 'month_from': SEP[0], 'month_to': SEP[0],
                                    'reason': 'x', 'whatifs': [{'payslip_id': slips[1].id,
                                                                'code': 'BASICPAY', 'value': 1,
                                                                'note': ''}]})
        with self.assertRaises(UserError):
            self.Board.save_review({'config_id': cfg.id, 'month_from': SEP[0], 'month_to': SEP[0],
                                    'reason': 'x', 'whatifs': [{'payslip_id': slips[0].id,
                                                                'code': 'BASICPAY', 'value': 1,
                                                                'note': 'n'}]})
        with self.assertRaises(UserError):
            self.Board.save_review({'config_id': cfg.id, 'month_from': SEP[0], 'month_to': SEP[0],
                                    'reason': 'x', 'whatifs': [{'payslip_id': slips[1].id,
                                                                'code': 'NETPAY', 'value': 1,
                                                                'note': 'n'}]})

    def test_03b_whatif_replaces_a_contract_change_of_the_same_item(self):
        cfg, emp, contract, slips = self._three_months()
        self._change(contract, 'BASICPAY', 44_000_000, 50_000_000, date(2026, 8, 16))
        review = self._review(cfg, SEP[0], SEP[0], whatif_ids=[(0, 0, {
            'payslip_id': slips[1].id, 'code': 'BASICPAY', 'value': 40_000_000, 'note': 'n'})])
        review.action_work_out()
        self.assertAlmostEqual(self._diffs(review, slips[1])['BASICPAY'], -4_000_000)
        overlay = json.loads(self._row(review, slips[1]).overlay_json)
        contract_rows = [o for o in overlay if o['kind'] == 'contract']
        self.assertEqual([o['applied'] for o in contract_rows], [False])
        changes = self.Board.get_review(review.id)['changes']
        self.assertTrue(any(c['replaced'] for c in changes if c['kind'] == 'contract'))

    # =====================================================================
    # T4 — baseline drift
    # =====================================================================
    def test_04_baseline_drift_is_labelled_and_netted(self):
        cfg, emp, contract, slips = self._three_months()
        # the stored take-home no longer matches what the payslip's own inputs give
        net_line = slips[1].line_ids.filtered(lambda l: l.code == 'NETPAY')
        self.env.flush_all()
        self.env.cr.execute("UPDATE hr_payslip_line SET amount = amount + 1000, "
                            "total = total + 1000 WHERE id = %s", (net_line.id,))
        self.env.invalidate_all()
        review = self._review(cfg, AUG[0], OCT[0], whatif_ids=[(0, 0, {
            'payslip_id': slips[1].id, 'code': 'BASICPAY', 'value': 30_000_000, 'note': 'n'})])
        review.action_work_out()
        row = self._row(review, slips[1])
        self.assertEqual(row.status, 'drift')
        drift = json.loads(row.drift_json)
        self.assertEqual([d['code'] for d in drift], ['NETPAY'])
        self.assertEqual(drift[0]['stored'] - drift[0]['today'], 1000)
        # the difference is measured against the re-worked baseline, not the stored line
        expected = excel_round(hand(30_000_000)['NETPAY'] - hand(44_000_000)['NETPAY'])
        line = row.line_ids.filtered(lambda l: l.code == 'NETPAY')
        self.assertAlmostEqual(line.diff, expected)
        self.assertAlmostEqual(line.was, line.baseline + 1000)
        self.assertAlmostEqual(line.would_be, line.was + line.diff)
        # the other months are untouched and exact
        self.assertEqual(self._row(review, slips[0]).status, 'same')
        data = self.Board.get_review(review.id)
        self.assertEqual(data['status']['drift'], 1)
        self.assertEqual(data['issues']['drift'][0]['drift'][0]['name'], 'Take-home')
        months = self.Board.get_people(review.id, show='all')['people'][0]['months']
        self.assertTrue([m for m in months if m['approx']])

    def test_04b_scheme_changed_since_is_flagged(self):
        cfg = self._progressive(state='draft')
        emp, contract = self._person()
        slip = self._slip(cfg, emp, contract, SEP, {'BASICPAY': 20_000_000, 'LOANINST': 0})
        cfg.rule_ids.filtered(lambda r: r.code == 'SIEMP').write(
            {'excel_formula': '=%s*0.11' % cfg.rule_ids.filtered(
                lambda r: r.code == 'INSBASE').column_letter})
        review = self._review(cfg, SEP[0], SEP[0])
        review.action_work_out()
        row = review.slip_ids
        self.assertTrue(row.scheme_changed)
        self.assertEqual(row.status, 'drift')    # today's scheme gives other figures
        self.assertTrue(self.Board.get_review(review.id)['scheme_banner']['today'])
        # a payslip with no stamp at all is "unknown"
        slip.sudo().write({'formula_content_hash': False})
        review.action_work_out()
        self.assertTrue(review.slip_ids.scheme_unknown)

    # =====================================================================
    # T5 — a formula that raises is isolated (R6)
    # =====================================================================
    def test_05_errored_formula_is_isolated(self):
        cfg = self._scheme()
        b = self._rule(cfg, 'BASICPAY', 'Basic pay', 'input', role='earning').column_letter
        h = self._rule(cfg, 'STDHRS', 'Standard hours', 'input', role='info', seq=11,
                       on_slip=False).column_letter
        self._rule(cfg, 'HOURLY', 'Hourly rate', 'formula', '=%s/%s' % (b, h), role='info',
                   seq=20)
        tax = self._rule(cfg, 'PITAX', 'Income tax', 'formula', '=%s*0.1' % b,
                         role='deduction', seq=30).column_letter
        self._rule(cfg, 'NETPAY', 'Take-home', 'formula', '=%s-%s' % (b, tax), role='net', seq=40)
        bad_emp, bad_c = self._person('W2D1 Zero Hours')
        ok_emp, ok_c = self._person('W2D1 Fine')
        bad = self._slip(cfg, bad_emp, bad_c, SEP, {'BASICPAY': 10_000_000, 'STDHRS': 0})
        ok = self._slip(cfg, ok_emp, ok_c, SEP, {'BASICPAY': 10_000_000, 'STDHRS': 160})
        review = self._review(cfg, SEP[0], SEP[0], whatif_ids=[
            (0, 0, {'payslip_id': bad.id, 'code': 'BASICPAY', 'value': 12_000_000, 'note': 'n'}),
            (0, 0, {'payslip_id': ok.id, 'code': 'BASICPAY', 'value': 12_000_000, 'note': 'n'})])
        review.action_work_out()
        self.assertEqual(self._row(review, bad).status, 'error')
        self.assertEqual(self._row(review, bad).error_item, 'Hourly rate')
        self.assertEqual(self._row(review, bad).error_why, 'zero')
        self.assertFalse(self._row(review, bad).line_ids)
        self.assertEqual(self._row(review, ok).status, 'changed')
        self.assertAlmostEqual(self._diffs(review, ok)['NETPAY'], 1_800_000)
        issue = self.Board.get_review(review.id)['issues']['error'][0]
        self.assertEqual(issue['error_item'], 'Hourly rate')
        self.assertEqual(issue['error_why'], 'it divides by zero')

    # =====================================================================
    # T6 — R1: nothing that pays people is written
    # =====================================================================
    @contextmanager
    def _writes(self):
        seen = []
        real = Cursor.execute

        def spy(cr, query, params=None, log_exceptions=True):
            text = query.code if hasattr(query, 'code') else str(query)
            m = re.match(r'\s*(INSERT\s+INTO|UPDATE|DELETE\s+FROM)\s+"?(\w+)', text, re.I)
            if m:
                seen.append(m.group(2))
            return real(cr, query, params, log_exceptions)

        self.env.flush_all()
        with patch.object(Cursor, 'execute', spy):
            yield seen
            self.env.flush_all()

    def _payroll_stamps(self):
        out = {}
        for model in ('hr.payslip', 'hr.payslip.line', 'hr.payslip.run', 'hr.payroll.period.input',
                      'pb.loan', 'pb.loan.repayment', 'pb.updates.oneoff',
                      'hr.payroll.retro.adjustment', 'hr.contract.advantage.change',
                      'hr.contract', 'hr.formula.rule', 'hr.formula.config'):
            if model not in self.env:
                continue
            Model = self.env[model].sudo().with_context(active_test=False)
            recs = Model.search([])
            out[model] = (len(recs), max(recs.mapped('write_date')) if recs else None)
        return out

    def test_06_r1_read_only_towards_payroll(self):
        cfg, emp, contract, slips = self._three_months(loan=1_500_000)
        self._change(contract, 'BASICPAY', 44_000_000, 50_000_000, date(2026, 8, 16))
        review = self._review(cfg, AUG[0], OCT[0], whatif_ids=[(0, 0, {
            'payslip_id': slips[2].id, 'code': 'BASICPAY', 'value': 55_000_000, 'note': 'n'})])
        self.env.flush_all()
        before = self._payroll_stamps()
        inputs = [s.formula_input_values for s in slips]
        with self._writes() as seen:
            review.action_work_out()
            self.Board.get_review(review.id)
            self.Board.get_people(review.id, show='all')
            self.Board.export_xlsx(review.id)
        foreign = sorted({t for t in seen if not t.startswith('pb_retro_')})
        self.assertEqual(foreign, [], "R1: only the re-work's own tables may be written")
        self.assertTrue(seen, "the re-work's own rows must have been written")
        for s in slips:
            s.invalidate_recordset()
        self.assertEqual(before, self._payroll_stamps())
        self.assertEqual(inputs, [s.formula_input_values for s in slips])
        # the loan instalment is fed exactly as stored: no loan line moves
        self.assertFalse(review.line_ids.filtered(lambda l: l.code == 'LOANINST'))
        self.assertTrue(review.line_ids.filtered(lambda l: l.code == 'NETPAY'))

    def test_06b_the_write_spy_is_live(self):
        cfg, emp, contract, slips = self._three_months()
        with self._writes() as seen:
            slips[0].sudo().write({'name': 'W2D1 renamed'})
        self.assertIn('hr_payslip', seen)

    # =====================================================================
    # T7 — an Extra-run payslip is listed, not re-worked
    # =====================================================================
    def test_07_extra_run_payslip_is_not_reworked(self):
        cfg, emp, contract, slips = self._three_months()
        extra = self._slip(cfg, emp, contract, SEP, {'BASICPAY': 5_000_000, 'LOANINST': 0},
                           kind='extra')
        self._change(contract, 'BASICPAY', 44_000_000, 50_000_000, date(2026, 8, 16))
        review = self._review(cfg, SEP[0], SEP[0])
        review.action_work_out()
        row = self._row(review, extra)
        self.assertEqual(row.status, 'skipped')
        self.assertEqual(row.skip_reason, 'extra')
        self.assertFalse(row.line_ids)
        self.assertEqual(self._row(review, slips[1]).status, 'changed')
        data = self.Board.get_review(review.id)
        self.assertEqual(data['status']['skipped'], 1)
        self.assertEqual(data['issues']['skipped'][0]['skip'], 'Extra run')
        preview = self.Board.scope_preview({'config_id': cfg.id, 'month_from': SEP[0],
                                            'month_to': SEP[0]})
        self.assertEqual((preview['payslips'], preview['other']), (1, 1))

    # =====================================================================
    # T8 — two currencies (R4)
    # =====================================================================
    def _sg_scheme(self):
        cfg = self._scheme('SG')
        b = self._rule(cfg, 'BASICPAY', 'Basic pay', 'input', role='earning').column_letter
        cpf = self._rule(cfg, 'CPFEMP', 'Fund', 'formula', '=%s*0.0765' % b,
                         role='deduction', seq=20).column_letter
        self._rule(cfg, 'NETPAY', 'Take-home', 'formula', '=%s-%s' % (b, cpf), role='net', seq=30)
        return cfg

    def test_08_two_currencies_never_add(self):
        sg = self._sg_scheme()
        self.assertEqual(sg.scheme_currency()['decimals'], 2)
        emp, contract = self._person('W2D1 Singapore')
        slip = self._slip(sg, emp, contract, SEP, {'BASICPAY': 1000})
        sg_review = self._review(sg, SEP[0], SEP[0], whatif_ids=[(0, 0, {
            'payslip_id': slip.id, 'code': 'BASICPAY', 'value': 1001.33, 'note': 'n'})])
        sg_review.action_work_out()
        diffs = self._diffs(sg_review, slip)
        self.assertAlmostEqual(diffs['CPFEMP'], excel_round(1.33 * 0.0765, 2))
        self.assertAlmostEqual(diffs['NETPAY'], excel_round(1.33 - 1.33 * 0.0765, 2))
        self.assertNotEqual(diffs['NETPAY'], round(diffs['NETPAY']))
        vn, emp2, contract2, slips = self._three_months()
        vn_review = self._review(vn, SEP[0], SEP[0], whatif_ids=[(0, 0, {
            'payslip_id': slips[1].id, 'code': 'BASICPAY', 'value': 45_000_000, 'note': 'n'})])
        vn_review.action_work_out()
        self.assertEqual(sg_review.currency_id, self.sgd)
        self.assertEqual(vn_review.currency_id, self.vnd)
        roll = sg_review._pb_rollup()
        self.assertEqual(list(roll), [self.sgd.id])
        rows = {r['id']: r for r in self.Board.get_page()['rows']}
        self.assertEqual(rows[sg_review.id]['currency'], 'SGD')
        self.assertEqual(rows[vn_review.id]['currency'], 'VND')
        self.assertIn('.', rows[sg_review.id]['net_label'])       # cents on the board
        strips = self.Board.get_review(sg_review.id)['strips']
        self.assertEqual([s['currency'] for s in strips], ['SGD'])

    # =====================================================================
    # T9 — rights and companies
    # =====================================================================
    def _user(self, groups, company):
        type(self)._seq += 1
        return self.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'W2D1 user %s' % self._seq, 'login': 'w2d1.user.%s' % self._seq,
            'company_id': company.id, 'company_ids': [(6, 0, company.ids)],
            'group_ids': [(6, 0, [self.env.ref(g).id for g in groups])],
        })

    def test_09_rights_and_companies(self):
        cfg, emp, contract, slips = self._three_months()
        review = self._review(cfg, SEP[0], SEP[0])
        officer = self._user(['base.group_user', 'om_hr_payroll.group_hr_payroll_user'],
                             self.company)
        board = self.Board.with_user(officer).with_context(allowed_company_ids=[self.company.id])
        self.assertFalse(board.get_board()['allowed'])
        self.assertEqual(board.get_page()['rows'], [])
        self.assertIn('refused', board.pbf_layout())
        for call in (lambda: board.get_review(review.id),
                     lambda: board.scope_preview({'config_id': cfg.id, 'month_from': SEP[0]}),
                     lambda: board.new_options()):
            with self.assertRaises(AccessError):
                call()
        with self.assertRaises(AccessError):
            self.Review.with_user(officer).with_context(
                allowed_company_ids=[self.company.id]).create({
                    'config_id': cfg.id, 'month_from': SEP[0], 'month_to': SEP[0],
                    'reason': 'x', 'company_id': self.company.id})
        # a payroll manager of ANOTHER company sees nothing of this one
        other = self.env['res.company'].create({'name': 'W2D1 Other Co'})
        manager = self._user(['base.group_user', 'om_hr_payroll.group_hr_payroll_manager'],
                             other)
        mboard = self.Board.with_user(manager).with_context(allowed_company_ids=[other.id])
        self.env.flush_all()
        self.env.invalidate_all()
        self.assertTrue(mboard.get_board()['allowed'])
        self.assertEqual(mboard.get_page()['total'], 0)
        with self.assertRaises(UserError):
            mboard.get_review(review.id)
        with self.assertRaises(UserError):
            mboard.scope_preview({'config_id': cfg.id, 'month_from': SEP[0]})
        self.assertNotIn(cfg.id, [s['id'] for s in mboard.new_options()['schemes']])
        # and a manager of this company is served
        mine = self._user(['base.group_user', 'om_hr_payroll.group_hr_payroll_manager'],
                          self.company)
        self.env.flush_all()
        self.env.invalidate_all()
        mine_board = self.Board.with_user(mine).with_context(allowed_company_ids=[self.company.id])
        self.assertEqual(mine_board.get_review(review.id)['id'], review.id)
        self.assertIn(cfg.id, [s['id'] for s in mine_board.new_options()['schemes']])
        # ... and can do the whole thing without any formula rights (W2B-2 family:
        # contract changes and scheme rules are read under sudo after the gate)
        self.assertFalse(mine.has_group('pb_hr_payroll_formula.group_formula_user'))
        self._change(contract, 'BASICPAY', 44_000_000, 50_000_000, date(2026, 8, 16))
        change_id = mine_board.scope_preview({'config_id': cfg.id, 'month_from': AUG[0],
                                              'month_to': OCT[0]})['changes'][0]['id']
        saved = mine_board.save_review({'config_id': cfg.id, 'month_from': AUG[0],
                                        'month_to': OCT[0], 'reason': 'manager',
                                        'excluded_change_ids': []})
        plan = mine_board.work_start(saved['id'])
        mine_board.work_chunk(saved['id'], plan['slip_ids'])
        mine_board.work_finish(saved['id'], 5)
        data = mine_board.get_review(saved['id'])
        self.assertEqual(data['status']['changed'], 3)
        self.assertTrue(mine_board.get_people(saved['id'])['people'])
        self.assertTrue(mine_board.export_xlsx(saved['id'])['ok'])
        # leaving the change out sends it back to draft and the next working-out has none
        mine_board.save_review({'id': saved['id'], 'config_id': cfg.id, 'month_from': AUG[0],
                                'month_to': OCT[0], 'reason': 'manager',
                                'excluded_change_ids': [change_id]})
        self.assertEqual(mine_board.get_review(saved['id'])['state'], 'draft')
        plan = mine_board.work_start(saved['id'])
        mine_board.work_chunk(saved['id'], plan['slip_ids'])
        self.assertEqual(mine_board.get_review(saved['id'])['status']['same'], 3)

    # =====================================================================
    # T10 — deterministic (R3)
    # =====================================================================
    def test_10_working_out_twice_gives_identical_lines(self):
        cfg, emp, contract, slips = self._three_months()
        self._change(contract, 'BASICPAY', 44_000_000, 50_000_000, date(2026, 8, 16))
        review = self._review(cfg, AUG[0], OCT[0], whatif_ids=[(0, 0, {
            'payslip_id': slips[2].id, 'code': 'LOANINST', 'value': 250_000, 'note': 'n'})])
        review.action_work_out()
        first = (self._lines(review), sorted((s.payslip_id.id, s.status, s.overlay_json,
                                              s.diff_net) for s in review.slip_ids))
        review.action_work_out()
        second = (self._lines(review), sorted((s.payslip_id.id, s.status, s.overlay_json,
                                               s.diff_net) for s in review.slip_ids))
        self.assertTrue(first[0])
        self.assertEqual(first, second)

    # =====================================================================
    # T11 — caps
    # =====================================================================
    def test_11_caps(self):
        cfg, emp, contract, slips = self._three_months()
        with self.assertRaises(ValidationError):
            self._review(cfg, date(2025, 8, 1), date(2026, 8, 1))     # 13 months
        self._review(cfg, date(2025, 9, 1), date(2026, 8, 1))         # 12 is fine
        other_emp, other_c = self._person()
        self._slip(cfg, other_emp, other_c, SEP, {'BASICPAY': 1, 'LOANINST': 0})
        review = self._review(cfg, SEP[0], SEP[0])
        with patch.object(retro_review, 'PEOPLE_CAP', 1):
            with self.assertRaises(UserError):
                review.action_work_out()
        review.action_work_out()
        self.assertEqual(len(review.slip_ids), 2)
        with self.assertRaises(ValidationError):
            self._review(cfg, SEP[0], AUG[0])                         # last before first
        with self.assertRaises(ValidationError):
            self._review(cfg, SEP[0], SEP[0], reason='  ')

    # =====================================================================
    # T12 — Excel export
    # =====================================================================
    def test_12_export(self):
        from openpyxl import load_workbook
        cfg, emp, contract, slips = self._three_months()
        self._change(contract, 'BASICPAY', 44_000_000, 50_000_000, date(2026, 8, 16))
        review = self._review(cfg, AUG[0], OCT[0])
        review.action_work_out()
        res = self.Board.export_xlsx(review.id)
        self.assertTrue(res['ok'])
        self.assertEqual(res['rows'], len(review.line_ids))
        wb = load_workbook(io.BytesIO(base64.b64decode(res['file_b64'])))
        cells = [c.value for row in wb.worksheets[0].iter_rows() for c in row if c.value]
        self.assertIn('Amounts in VND', cells)
        self.assertEqual(cells.count('Amounts in VND'), 1)
        self.assertIn('Take-home', cells)
        self.assertEqual(wb.worksheets[1].max_row, 1 + len(review.slip_ids))
        self.assertFalse([c for c in cells if isinstance(c, str) and 'odoo' in c.lower()])

    # =====================================================================
    # T13 — silent install
    # =====================================================================
    def test_13_silent_install(self):
        self.assertFalse(self.env['ir.cron'].sudo().with_context(active_test=False).search(
            [('model_id.model', 'like', 'pb.retro.%')]))
        board = self.Board.get_board()
        self.assertTrue(board['allowed'])
        self.assertEqual(board['total'], 0)
        self.assertEqual(self.Board.get_page()['rows'], [])
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        palette = open(os.path.join(root, 'static/src/js/retro_palette.js')).read()
        self.assertEqual(palette.count('registry.category("pb_hub_palette").add('), 1)
        self.assertEqual(palette.count('registry.category(PAY_LENSES).add('), 1)
        # white-label: no vendor name in anything a person reads
        for rel in ('static/src/xml/retro_board.xml', 'static/src/js/retro_board.js',
                    'static/src/js/retro_palette.js', 'views/retro_views.xml'):
            text = open(os.path.join(root, rel)).read()
            visible = re.sub(r'@odoo-module|@odoo/owl|<odoo>|</odoo>|odoo-[a-z]+', '', text)
            self.assertNotIn('odoo', visible.lower(), rel)
        for rel in ('models/retro_board.py', 'models/retro_review.py'):
            text = open(os.path.join(root, rel)).read()
            for literal in re.findall(r'_\(\s*((?:"[^"]*"\s*)+|(?:\'[^\']*\'\s*)+)', text):
                self.assertNotIn('odoo', literal.lower(), rel)

    # =====================================================================
    # T14 — already paid back by the existing retro flow
    # =====================================================================
    def test_14_a_change_already_paid_back_is_not_counted_again(self):
        cfg, emp, contract, slips = self._three_months()
        change = self._change(contract, 'BASICPAY', 44_000_000, 50_000_000, date(2026, 8, 16))
        rule = cfg.rule_ids.filtered(lambda r: r.code == 'BASICPAY')
        self.env['hr.payroll.retro.adjustment'].sudo().create({
            'formula_config_id': cfg.id, 'employee_id': emp.id, 'contract_id': contract.id,
            'component_id': rule.id, 'advantage_change_id': change.id,
            'change_effective_date': change.effective_date, 'period_from': SEP[0],
            'period_to': SEP[1], 'old_amount': 44_000_000, 'new_amount': 50_000_000,
            'delta_amount': 6_000_000, 'original_payslip_id': slips[1].id, 'state': 'posted'})
        review = self._review(cfg, AUG[0], OCT[0])
        review.action_work_out()
        self.assertEqual(self._row(review, slips[1]).status, 'same')
        self.assertEqual(self._row(review, slips[2]).status, 'changed')
        overlay = json.loads(self._row(review, slips[1]).overlay_json)
        self.assertTrue(overlay[0]['paid_back'])
        self.assertFalse(overlay[0]['applied'])

    # =====================================================================
    # T15 — chunks
    # =====================================================================
    def test_15_chunks_give_the_same_result(self):
        cfg = self._progressive()
        slips = []
        for i in range(5):
            emp, contract = self._person()
            slips.append(self._slip(cfg, emp, contract, SEP,
                                    {'BASICPAY': 20_000_000 + i * 1_000_000, 'LOANINST': 0}))
            self._change(contract, 'BASICPAY', 20_000_000 + i * 1_000_000, 30_000_000,
                         date(2026, 9, 1))
        review = self._review(cfg, SEP[0], SEP[0])
        review.action_work_out()
        whole = self._lines(review)
        with patch.object(retro_review, 'CHUNK', 2):
            review.action_work_out()
        self.assertEqual(whole, self._lines(review))
        # a chunk only ever takes payslips the re-work covers, once each
        stranger_cfg, s_emp, s_c, s_slips = self._three_months()
        review.pb_work_start()
        self.assertEqual(review.pb_work_chunk([s_slips[1].id])['done'], 0)
        self.assertEqual(review.pb_work_chunk([slips[0].id])['done'], 1)
        self.assertEqual(review.pb_work_chunk([slips[0].id])['done'], 0)

    # =====================================================================
    # T16 — timing per 40 payslips
    # =====================================================================
    def test_16_timing_per_40_payslips(self):
        cfg = self._progressive()
        emps = []
        for i in range(40):
            emp, contract = self._person()
            self._slip(cfg, emp, contract, SEP, {'BASICPAY': 15_000_000 + i * 500_000,
                                                 'LOANINST': 0})
            self._change(contract, 'BASICPAY', 15_000_000 + i * 500_000, 40_000_000,
                         date(2026, 9, 10))
            emps.append(emp)
        review = self._review(cfg, SEP[0], SEP[0])
        self.env.flush_all()
        plan = review.pb_work_start()
        started = time.monotonic()
        review.pb_work_chunk(plan['slip_ids'])
        ms = int((time.monotonic() - started) * 1000)
        _logger.info('W2D1 timing: one chunk of %s payslips in %s ms', len(plan['slip_ids']), ms)
        self.assertEqual(len(review.slip_ids), 40)
        self.assertEqual(set(review.slip_ids.mapped('status')), {'changed'})
        self.assertLess(ms, 60_000)
