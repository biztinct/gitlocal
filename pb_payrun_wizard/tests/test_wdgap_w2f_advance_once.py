# -*- coding: utf-8 -*-
"""WDGAP W2-F (F-1) — an Extra run never takes the mid-month advance twice.
Handover `docs/handovers/wdgap/WDGAP_W2_F_HANDOVER.md` §F-1.

Fixture: PR-E's (one live end-of-month scheme, four people, a pay data file
for Ann, Bob, Cat and a stranger) plus the scheme's carry-over setting — an
"Advance paid" input that receives the mid-month "Advance" — and Ann's
posted ₫3,000,000 advance for August.

  A1  taken before: the regular run took Ann's advance; an Extra run for Ann
      feeds 0, records where it was taken, says so before computing and on
      the result step, and the review carries a note — not the old flag;
  A2  not taken before: the Extra run takes it (unchanged, PR-E's flag);
  A3  could not decide: the regular payslip is not worked out yet — the
      Extra run takes it and the flag says why;
  A4  taken twice the other way round (Extra first, regular after): flagged;
  A5  a scheme with no carry-over setting: nothing changes, nothing recorded;
  A6  recalculating is idempotent (Extra and regular);
  A7  GOLDEN: regular and top-up runs on the advance fixture are
      byte-identical to the code before W2-F (recorded on origin/19.1).
"""
import json
import logging
import os

from odoo.tests import tagged

from .test_wdgap_pre_extra_file import _ExtraFileFixture

_logger = logging.getLogger(__name__)

KEPT = 'Advance not taken again (already in August regular)'
OLD = 'This file also takes the mid-month advance; check it has not been taken already'


class _AdvanceFixture(_ExtraFileFixture):

    def setUp(self):
        super().setUp()
        category = self.env['hr.salary.rule.category'].search([], limit=1)
        self.advpay = self.env['hr.formula.rule'].create({
            'config_id': self.config.id, 'code': 'ADVPAY',
            'name': 'Advance paid', 'column_type': 'input', 'sequence': 2,
            'default_value': 0.0, 'appears_on_payslip': True,
            'category_id': category.id})
        self.mid = self.env['hr.formula.config'].create({
            'name': 'Extra File Mid-Month', 'code': 'XFILEMID',
            'country_code': 'VN', 'cycle_type': 'mid_cycle',
            'company_id': self.company.id})
        self.mid_adv = self.env['hr.formula.rule'].create({
            'config_id': self.mid.id, 'code': 'ADVPAY', 'name': 'Advance',
            'column_type': 'input', 'sequence': 1, 'default_value': 0.0,
            'category_id': category.id})
        self.mapping = self.env['hr.payroll.cycle.component.mapping'].create({
            'mid_cycle_config_id': self.mid.id,
            'end_cycle_config_id': self.config.id,
            'mid_component_id': self.mid_adv.id,
            'end_component_id': self.advpay.id})
        mid_batch = self.Batch.create({
            'name': 'August mid-month', 'source_type': 'excel',
            'formula_config_id': self.mid.id, 'payroll_period': 'custom',
            'date_from': '2026-08-01', 'date_to': '2026-08-15'})
        mid_batch.write({'state': 'done'})
        self.env['hr.payroll.cycle.carryover'].create({
            'employee_id': self.ann.id, 'formula_config_id': self.mid.id,
            'source_component_id': self.mid_adv.id, 'amount': 3000000.0,
            'company_id': self.company.id,
            'date_from': '2026-08-01', 'date_to': '2026-08-15',
            'import_batch_id': mid_batch.id, 'state': 'posted'})

    @staticmethod
    def _advance(slip):
        """The advance fed to a payslip. The fixture's file has no advance
        column, so the importer's loose column binding hands the input the
        person's name when nothing else writes it (ledger PRB-W3) — the raw
        value is returned then."""
        raw = json.loads(slip.formula_input_values or '{}').get('ADVPAY')
        try:
            return float(raw or 0.0)
        except (TypeError, ValueError):
            return raw

    def _ann(self, prep):
        run = self.Run.browse(prep['run_id'])
        return run, run.slip_ids.filtered(lambda s: s.employee_id == self.ann)

    def _regular_took_it(self):
        prep = self._prepare('regular')
        res = self._attach(prep)
        self.assertTrue(res['ok'], res.get('msg'))
        run, slip = self._ann(prep)
        self.assertEqual(self._advance(slip), 3000000.0)
        self.assertTrue(slip.line_ids, 'the regular payslip was not worked out')
        return run, slip


@tagged('post_install', '-at_install', 'wdgap_w2f')
class TestAdvanceOnce(_AdvanceFixture):

    # ============================================================ A1
    def test_a1_taken_before_is_not_taken_again(self):
        regular_run, regular = self._regular_took_it()
        # before computing: the pay-data step's own check says it
        pre = self.Wizard.preflight_spreadsheet(
            self.config.id, self._file(), 'august.xlsx', [self.ann.id],
            '2026-08-01', '2026-08-31')
        self.assertTrue(pre['ok'], pre.get('msg'))
        self.assertEqual(pre['extra']['advance_kept'], 1)
        self.assertEqual(
            pre['extra']['advance_kept_sentence'],
            'The mid-month advance was already taken in August regular for the '
            'person picked. This extra run will not take it again.')
        # the extra run feeds 0 and records where it was taken
        prep = self._prepare('extra', [self.ann])
        res = self._attach(prep)
        self.assertTrue(res['ok'], res.get('msg'))
        run, slip = self._ann(prep)
        self.assertEqual(self._advance(slip), 0.0)
        self.assertIn('ADVPAY', json.loads(slip.formula_input_values))
        self.assertEqual(slip.pb_advance_taken_in_id, regular)
        self.assertEqual(self._meal(slip), 100000.0, 'the file still feeds the rest')
        # the result step
        extra = res['extra']
        self.assertEqual(extra['advance'], 0)
        self.assertFalse(extra['advance_sentence'])
        self.assertEqual(extra['advance_kept'], 1)
        self.assertIn('already taken in August regular', extra['advance_kept_sentence'])
        # the review: a note, never the old warning
        row = run.pb_review_flags()[slip.id]
        self.assertFalse(row['flag'])
        self.assertEqual(row['note'], KEPT)
        self.assertNotIn('mid-month advance', row.get('reason') or '')
        self.assertTrue(row.get('advance_kept_out'))
        summary = self.Wizard.get_summary(run.id)
        mine = [r for r in summary['rows'] if r['id'] == slip.id][0]
        self.assertEqual((mine['flag'], mine['note']), (False, KEPT))
        self.assertEqual(summary['flagged'], 0)
        # the regular run is untouched
        self.assertEqual(self._advance(regular), 3000000.0)
        self.assertFalse(regular.pb_advance_taken_in_id)
        self.assertFalse(regular_run.pb_review_flags()[regular.id].get('note'))

    def test_a1b_three_picked_two_kept_out(self):
        # Bob also had an advance; the regular run took Ann's and Bob's
        self.env['hr.payroll.cycle.carryover'].create({
            'employee_id': self.bob.id, 'formula_config_id': self.mid.id,
            'source_component_id': self.mid_adv.id, 'amount': 2000000.0,
            'company_id': self.company.id,
            'date_from': '2026-08-01', 'date_to': '2026-08-15',
            'import_batch_id': self.env['hr.payroll.cycle.carryover'].search(
                [('employee_id', '=', self.ann.id)]).import_batch_id.id,
            'state': 'posted'})
        self._regular_took_it()
        prep = self._prepare('extra', [self.ann, self.bob, self.cat])
        res = self._attach(prep)
        self.assertEqual(res['extra']['advance_kept'], 2)
        self.assertEqual(
            res['extra']['advance_kept_sentence'],
            'The mid-month advance was already taken in August regular for 2 of '
            'the people picked. This extra run will not take it again.')
        run = self.Run.browse(prep['run_id'])
        flags = run.pb_review_flags()
        notes = {s.employee_id.name: flags[s.id].get('note') for s in run.slip_ids}
        self.assertEqual(notes, {'XF Ann': KEPT, 'XF Bob': KEPT, 'XF Cat': None})

    # ============================================================ A2
    def test_a2_not_taken_before_is_unchanged(self):
        prep = self._prepare('extra', [self.ann])
        pre = self.Wizard.preflight_spreadsheet(
            self.config.id, self._file(), 'august.xlsx', [self.ann.id],
            '2026-08-01', '2026-08-31')
        self.assertNotIn('advance_kept', pre['extra'])
        res = self._attach(prep)
        run, slip = self._ann(prep)
        # the Extra run may be the one that takes it — PR-E behaviour
        self.assertEqual(self._advance(slip), 3000000.0)
        self.assertFalse(slip.pb_advance_taken_in_id)
        self.assertEqual(res['extra']['advance'], 1)
        self.assertFalse(res['extra']['advance_kept'])
        row = run.pb_review_flags()[slip.id]
        self.assertTrue(row['flag'])
        self.assertIn(OLD, row['reason'])
        self.assertFalse(row.get('note'))

    # ============================================================ A3
    def test_a3_regular_not_worked_out_yet_says_why(self):
        regular_prep = self._prepare('regular')
        regular_run = self.Run.browse(regular_prep['run_id'])
        self.Slip.create({
            'name': 'Ann August', 'employee_id': self.ann.id,
            'company_id': self.company.id,
            'contract_id': self.env['hr.contract'].search(
                [('employee_id', '=', self.ann.id)], limit=1).id,
            'date_from': '2026-08-01', 'date_to': '2026-08-31',
            'formula_config_id': self.config.id,
            'payslip_run_id': regular_run.id})
        prep = self._prepare('extra', [self.ann])
        res = self._attach(prep)
        run, slip = self._ann(prep)
        self.assertEqual(self._advance(slip), 3000000.0, 'unchanged: it takes it')
        self.assertIn('not worked out yet', res['extra']['advance_sentence'])
        row = run.pb_review_flags()[slip.id]
        self.assertTrue(row['flag'])
        self.assertIn('Takes the mid-month advance: August regular is not worked '
                      'out yet', row['reason'])

    # ============================================================ A4
    def test_a4_extra_first_then_regular_is_flagged_twice(self):
        prep = self._prepare('extra', [self.ann])
        self._attach(prep)
        run, slip = self._ann(prep)
        self.assertEqual(self._advance(slip), 3000000.0)
        self._regular_took_it()     # regular runs are unchanged: it takes it too
        row = run.pb_review_flags()[slip.id]
        self.assertTrue(row['flag'])
        self.assertIn('August regular took it too', row['reason'])

    # ============================================================ A5
    def test_a5_no_carry_over_setting_changes_nothing(self):
        self.mapping.active = False
        self.assertFalse(self.config._pb_advance_input_codes())
        regular_prep = self._prepare('regular')
        self._attach(regular_prep)
        _rr, regular = self._ann(regular_prep)
        self.assertEqual(self.config._pb_advance_verdicts(
            self.ann, self.vals['date_start'], self.vals['date_end']), {})
        prep = self._prepare('extra', [self.ann])
        res = self._attach(prep)
        run, slip = self._ann(prep)
        self.assertFalse(slip.pb_advance_taken_in_id)
        # exactly what the regular run was fed from the same file: unchanged
        self.assertEqual(self._advance(slip), self._advance(regular))
        self.assertNotEqual(self._advance(slip), 3000000.0, 'nothing carried')
        self.assertFalse(res['extra']['advance'])
        self.assertFalse(res['extra']['advance_kept'])
        row = run.pb_review_flags()[slip.id]
        self.assertFalse(row.get('note'))
        self.assertNotIn('mid-month advance', row.get('reason') or '')

    # ============================================================ A6
    def test_a6_recalculating_is_idempotent(self):
        _regular_run, regular = self._regular_took_it()
        prep = self._prepare('extra', [self.ann])
        self._attach(prep)
        _run, slip = self._ann(prep)

        def sig(s):
            s.invalidate_recordset()
            return (s.formula_input_values, s.formula_input_sources,
                    s.pb_advance_taken_in_id.id,
                    sorted((l.code, l.total) for l in s.line_ids))
        before, reg_before = sig(slip), sig(regular)
        for _i in range(2):
            slip.action_recompute_formula_lines()
            self.assertEqual(sig(slip), before)
        self.assertEqual(self._advance(slip), 0.0)
        self.assertEqual(slip.pb_advance_taken_in_id, regular)
        regular.action_recompute_formula_lines()
        self.assertEqual(sig(regular), reg_before)
        self.assertFalse(regular.pb_advance_taken_in_id)

    # ============================================================ A7
    def _golden_signature(self, kind):
        prep = self._prepare(kind)
        res = self._attach(prep)
        run = self.Run.browse(prep['run_id'])
        slips = []
        for s in run.slip_ids.sorted(lambda x: x.employee_id.name):
            slips.append({
                'emp': s.employee_id.name,
                'inputs': json.loads(s.formula_input_values or '{}'),
                'sources': json.loads(s.formula_input_sources or '{}'),
                'lines': sorted([l.code, l.total] for l in s.line_ids),
                'flag': run.pb_review_flags()[s.id].get('flag'),
                'reason': run.pb_review_flags()[s.id].get('reason'),
            })
        return {'ok': res['ok'], 'created': res['created'],
                'keys': sorted(res), 'slips': slips}

    def test_a7_regular_and_topup_golden(self):
        sig = {'regular': self._golden_signature('regular')}
        sig['topup'] = self._golden_signature('topup')
        sig = json.loads(json.dumps(sig, default=str))
        if os.environ.get('W2F_GOLDEN_RECORD'):
            _logger.warning('W2F_A7_GOLDEN=%s', json.dumps(sig, sort_keys=True))
            return
        self.assertEqual(sig, json.loads(GOLDEN_A7))


#: Recorded on origin/19.1 (7f0fa3aad, before W2-F), same fixture, with
#: W2F_GOLDEN_RECORD=1.
GOLDEN_A7 = """
{
 "regular": {
  "created": 3,
  "keys": [
   "batch_id",
   "created",
   "created_employees",
   "errors",
   "fed_components",
   "filename",
   "matched",
   "ok",
   "one_time",
   "pending",
   "request_id",
   "rows",
   "run_id",
   "unmatched",
   "unmatched_count",
   "with_whom"
  ],
  "ok": true,
  "slips": [
   {
    "emp": "XF Ann",
    "flag": false,
    "inputs": {
     "ADVPAY": 3000000.0,
     "MEALALLOW": 100000.0
    },
    "lines": [
     [
      "ADVPAY",
      3000000.0
     ],
     [
      "MEALALLOW",
      100000.0
     ]
    ],
    "reason": "",
    "sources": {
     "ADVPAY": {
      "adj": [
       "carryover"
      ],
      "key": "B",
      "src": "excel",
      "via": "column_letter"
     },
     "MEALALLOW": {
      "key": "Meal Allowance",
      "src": "excel",
      "via": "binding"
     }
    }
   },
   {
    "emp": "XF Bob",
    "flag": false,
    "inputs": {
     "ADVPAY": "XF Bob",
     "MEALALLOW": 200000.0
    },
    "lines": [
     [
      "ADVPAY",
      0.0
     ],
     [
      "MEALALLOW",
      200000.0
     ]
    ],
    "reason": "",
    "sources": {
     "ADVPAY": {
      "key": "B",
      "src": "excel",
      "via": "column_letter"
     },
     "MEALALLOW": {
      "key": "Meal Allowance",
      "src": "excel",
      "via": "binding"
     }
    }
   },
   {
    "emp": "XF Cat",
    "flag": false,
    "inputs": {
     "ADVPAY": "XF Cat",
     "MEALALLOW": 300000.0
    },
    "lines": [
     [
      "ADVPAY",
      0.0
     ],
     [
      "MEALALLOW",
      300000.0
     ]
    ],
    "reason": "",
    "sources": {
     "ADVPAY": {
      "key": "B",
      "src": "excel",
      "via": "column_letter"
     },
     "MEALALLOW": {
      "key": "Meal Allowance",
      "src": "excel",
      "via": "binding"
     }
    }
   }
  ]
 },
 "topup": {
  "created": 3,
  "keys": [
   "batch_id",
   "created",
   "created_employees",
   "errors",
   "fed_components",
   "filename",
   "matched",
   "ok",
   "one_time",
   "pending",
   "request_id",
   "rows",
   "run_id",
   "unmatched",
   "unmatched_count",
   "with_whom"
  ],
  "ok": true,
  "slips": [
   {
    "emp": "XF Ann",
    "flag": false,
    "inputs": {
     "ADVPAY": 3000000.0,
     "MEALALLOW": 100000.0
    },
    "lines": [
     [
      "ADVPAY",
      3000000.0
     ],
     [
      "MEALALLOW",
      100000.0
     ]
    ],
    "reason": "",
    "sources": {
     "ADVPAY": {
      "adj": [
       "carryover"
      ],
      "key": "B",
      "src": "excel",
      "via": "column_letter"
     },
     "MEALALLOW": {
      "key": "Meal Allowance",
      "src": "excel",
      "via": "binding"
     }
    }
   },
   {
    "emp": "XF Bob",
    "flag": false,
    "inputs": {
     "ADVPAY": "XF Bob",
     "MEALALLOW": 200000.0
    },
    "lines": [
     [
      "ADVPAY",
      0.0
     ],
     [
      "MEALALLOW",
      200000.0
     ]
    ],
    "reason": "",
    "sources": {
     "ADVPAY": {
      "key": "B",
      "src": "excel",
      "via": "column_letter"
     },
     "MEALALLOW": {
      "key": "Meal Allowance",
      "src": "excel",
      "via": "binding"
     }
    }
   },
   {
    "emp": "XF Cat",
    "flag": false,
    "inputs": {
     "ADVPAY": "XF Cat",
     "MEALALLOW": 300000.0
    },
    "lines": [
     [
      "ADVPAY",
      0.0
     ],
     [
      "MEALALLOW",
      300000.0
     ]
    ],
    "reason": "",
    "sources": {
     "ADVPAY": {
      "key": "B",
      "src": "excel",
      "via": "column_letter"
     },
     "MEALALLOW": {
      "key": "Meal Allowance",
      "src": "excel",
      "via": "binding"
     }
    }
   }
  ]
 }
}
"""
