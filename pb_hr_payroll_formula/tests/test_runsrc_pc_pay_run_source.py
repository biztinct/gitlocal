# -*- coding: utf-8 -*-
"""RUNSRC Phase C — "From this pay run" is a source you can wire.

Phase B made the run ANSWER six things, but `fill_period_inputs` matches on the
component's CODE, and on a real scheme the standard-working-days component is
coded in the customer's own language (`NGAYCONGCHUAN`). Renaming it would
rewrite every formula that references it, so the run's numbers were unreachable
to exactly the schemes that needed them. Phase C lets a person draw the wire
instead.

The two assertions that matter most in this file:

  * **case 6** — the `_config_kind_rank` trap. The rank is built out of the
    scheme's ENABLED LANES, so a kind belonging to no lane is dropped before
    anything reads it. Without the `payrun` lane every wire this phase lets
    somebody draw would save, show a chip on the board, and be silently
    discarded at resolve time.
  * **case 8** — the file still wins. The run is the last rung; it replaces the
    value that was MISSING, never the value somebody stated. That is what makes
    "nothing changes on any existing database until a person draws a wire" true.

Test numbers are the handover's numbers
(docs/handovers/RUNSRC_PC_FROM_THIS_PAY_RUN.md §7).
"""
import json

from odoo.exceptions import ValidationError
from odoo.tests import TransactionCase, tagged

from odoo.addons.pb_hr_payroll_formula.models import pay_period


@tagged('post_install', '-at_install')
class TestRunsrcPcPayRunSource(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Config = cls.env['hr.formula.config']
        cls.Rule = cls.env['hr.formula.rule']
        cls.Batch = cls.env['hr.payroll.import.batch']
        cls.Line = cls.env['hr.payroll.import.line']

    # ------------------------------------------------------------- fixtures
    def _config(self, code, **vals):
        return self.Config.create(dict({
            'name': 'RUNSRC C %s' % code, 'code': code,
            'country_code': 'VN', 'state': 'active'}, **vals))

    def _rule(self, cfg, code, name='Standard working days', **vals):
        return self.Rule.create(dict({
            'config_id': cfg.id, 'name': name, 'code': code,
            'column_type': 'input'}, **vals))

    def _aug_batch(self, cfg, name='RUNSRC C · August 2026'):
        """A load over 1–31 August 2026 — the month the handover names, whose
        Mon–Fri count is 21 (1 August 2026 is a Saturday)."""
        return self.Batch.create({
            'name': name, 'formula_config_id': cfg.id, 'source_type': 'excel',
            'date_from': '2026-08-01', 'date_to': '2026-08-31'})

    def _people(self, tag):
        employee = self.env['hr.employee'].create({'name': 'RUNSRC C %s' % tag})
        contract = self.env['hr.contract'].create({
            'name': 'RUNSRC C c %s' % tag, 'employee_id': employee.id,
            'wage': 10000000.0, 'date_start': '2026-01-01'})
        return employee, contract

    def _resolve(self, batch, raw, employee, contract):
        prov = {}
        values = batch._transform_data_to_formula_inputs(
            raw, contract=contract, employee=employee, provenance=prov)
        return values, prov

    # =====================================================================
    # 1 — the Selection is the six codes
    # =====================================================================
    def test_01_selection_is_exactly_the_six_period_codes(self):
        """Test 1 — `period_key`'s values are `PERIOD_CODES`, in that order."""
        codes = [c for c, _label in self.Rule._period_key_selection()]
        self.assertEqual(tuple(codes), pay_period.PERIOD_CODES,
                         "the Selection is BUILT from PERIOD_CODES so a "
                         "seventh code can never exist in one place only")
        labels = [label for _c, label in self.Rule._period_key_selection()]
        self.assertTrue(all(labels), "every code carries a plain-words name")
        self.assertNotIn('Odoo', ' '.join(labels))

    # =====================================================================
    # 2 — declared_sources() lists it last
    # =====================================================================
    def test_02_declared_sources_lists_the_pay_run_last(self):
        """Test 2 — feed + column + contract component + pay run = four, run last."""
        cfg = self._config('RCDS')
        rule = self._rule(cfg, 'RCDSPAY', is_contract_component=True)
        rule.set_source_binding('feed', 'Base_Salary')
        rule.set_source_binding('excel', 'Basic salary')
        rule.set_source_binding('pay_run', 'STDDAYS')
        kinds = [d['kind'] for d in rule.declared_sources()]
        self.assertEqual(kinds, ['feed', 'excel', 'contract_component',
                                 'pay_run'],
                         "the run is the LAST rung, below the contract "
                         "component — it replaces the value that was missing")
        self.assertEqual(rule.declared_sources()[-1]['key'], 'STDDAYS')

    # =====================================================================
    # 3 — the Selection is written, and no source row is created
    # =====================================================================
    def test_03_set_source_binding_writes_the_selection_only(self):
        """Test 3 — `set_source_binding('pay_run', …)` makes no source row."""
        cfg = self._config('RCSET')
        rule = self._rule(cfg, 'RCSETPAY')
        before = len(rule.source_ids)
        rule.set_source_binding('pay_run', 'STDDAYS', origin='board')
        self.assertEqual(rule.period_key, 'STDDAYS')
        self.assertEqual(len(rule.source_ids), before,
                         "the run's period is a fact ABOUT the run, not a "
                         "payload it carries — there must never be a fourth "
                         "kind on hr.formula.rule.source")
        self.assertFalse(rule.source_binding,
                         "and the legacy winner badge is untouched")

    # =====================================================================
    # 4 — a bad key is refused
    # =====================================================================
    def test_04_a_key_the_run_cannot_answer_is_refused(self):
        """Test 4 — `set_source_binding('pay_run', 'BANANAS')` writes nothing."""
        cfg = self._config('RCBAD')
        rule = self._rule(cfg, 'RCBADPAY')
        with self.assertRaises(ValidationError):
            rule.set_source_binding('pay_run', 'BANANAS')
        rule.invalidate_recordset()
        self.assertFalse(rule.period_key)

    # =====================================================================
    # 5 — clearing empties it, from both doors
    # =====================================================================
    def test_05_clearing_empties_it_from_both_doors(self):
        """Test 5 — `clear_source_binding('pay_run')` and the board's delete."""
        cfg = self._config('RCCLR')
        rule = self._rule(cfg, 'RCCLRPAY')
        rule.set_source_binding('pay_run', 'STDDAYS')
        rule.clear_source_binding('pay_run')
        self.assertFalse(rule.period_key)
        # and "stop reading anything" takes it too
        rule.set_source_binding('pay_run', 'PAYMONTH')
        rule.set_source_binding('excel', 'Month')
        rule.clear_source_binding()
        self.assertFalse(rule.period_key)
        self.assertFalse(rule.source_ids)

    # =====================================================================
    # 6 — THE LANE TRAP: an untouched scheme still honours the wire
    # =====================================================================
    def test_06_an_untouched_scheme_honours_the_wire(self):
        """Test 6 — the `_config_kind_rank` trap (§4.4). The value lands."""
        cfg = self._config('RCLANE')            # never reconfigured
        self.assertEqual(cfg.source_priority, 'api,excel,records',
                         "fixture check: this scheme predates the payrun lane")
        rank = cfg._source_kind_rank()
        self.assertIn('pay_run', rank,
                      "a kind that belongs to no lane is DROPPED before "
                      "anything reads it — every wire would save, show a chip "
                      "and never deliver a number")
        self.assertEqual(rank[-1], 'pay_run', "and it is last")
        rule = self._rule(cfg, 'NGAYCONGCHUAN')
        rule.set_source_binding('pay_run', 'STDDAYS')
        self.assertEqual(rule.pay_run_wires(), [('NGAYCONGCHUAN', 'STDDAYS')])
        batch = self._aug_batch(cfg)
        employee, contract = self._people('lane')
        values, prov = self._resolve(batch, {'Employee code': 'E1'},
                                     employee, contract)
        self.assertEqual(values.get('NGAYCONGCHUAN'), 21.0)
        self.assertEqual(prov['NGAYCONGCHUAN']['src'], 'period')

    # =====================================================================
    # 7 — a wired component whose code the run has never heard of
    # =====================================================================
    def test_07_a_non_matching_code_still_gets_the_value(self):
        """Test 7 — `NGAYCONGCHUAN` wired to STDDAYS over August 2026 → 21."""
        cfg = self._config('RCWIRE')
        rule = self._rule(cfg, 'NGAYCONGCHUAN')
        rule.set_source_binding('pay_run', 'STDDAYS', origin='board')
        batch = self._aug_batch(cfg)
        employee, contract = self._people('wire')
        values, prov = self._resolve(batch, {'Employee code': 'E1'},
                                     employee, contract)
        self.assertEqual(values.get('NGAYCONGCHUAN'), 21.0,
                         "this is the whole phase: the code is Vietnamese and "
                         "`fill_period_inputs` could never reach it")
        self.assertEqual(prov['NGAYCONGCHUAN']['src'], 'period')
        self.assertEqual(prov['NGAYCONGCHUAN']['via'], pay_period.PERIOD_VIA)
        self.assertEqual(prov['NGAYCONGCHUAN']['key'], 'STDDAYS',
                         "the provenance names what was read, not the code "
                         "that was written into")
        # And the payslip resolver answers identically.
        slip = self.env['hr.payslip'].create({
            'employee_id': employee.id, 'name': 'RUNSRC C slip',
            'date_from': '2026-08-01', 'date_to': '2026-08-31',
            'formula_config_id': cfg.id})
        prov2 = {}
        slip_values = slip._get_formula_input_values(cfg, provenance=prov2)
        self.assertEqual(slip_values.get('NGAYCONGCHUAN'), 21.0)
        self.assertEqual(prov2['NGAYCONGCHUAN']['src'], 'period')

    # =====================================================================
    # 8 — the file still wins
    # =====================================================================
    def test_08_the_spreadsheet_still_wins(self):
        """Test 8 — a column that has a value beats the wire, and says so."""
        cfg = self._config('RCFILE')
        rule = self._rule(cfg, 'NGAYCONGCHUAN')
        rule.set_source_binding('excel', 'Standard working days')
        rule.set_source_binding('pay_run', 'STDDAYS')
        batch = self._aug_batch(cfg)
        employee, contract = self._people('file')
        values, prov = self._resolve(
            batch, {'Employee code': 'E1', 'Standard working days': 18.0},
            employee, contract)
        self.assertEqual(values.get('NGAYCONGCHUAN'), 18.0,
                         "the run replaces the value that was MISSING, never "
                         "the value somebody stated")
        self.assertEqual(prov['NGAYCONGCHUAN']['src'], 'excel')

    # =====================================================================
    # 9 — a feed that answered is untouched
    # =====================================================================
    def test_09_a_feed_that_answered_is_untouched(self):
        """Test 9 — a wired component already resolved by a feed keeps the feed."""
        cfg = self._config('RCFEED')
        rule = self._rule(cfg, 'NGAYCONGCHUAN')
        rule.set_source_binding('feed', 'std_days')
        rule.set_source_binding('pay_run', 'STDDAYS')
        batch = self._aug_batch(cfg)
        employee, contract = self._people('feed')
        hits = batch._declared_source_walk(
            rule, {'excel': {}, 'feed': {'std_days': 19.0}},
            contract=contract, employee=employee)
        self.assertTrue(hits, "the feed answers and the walk says so")
        self.assertEqual(hits[0]['kind'], 'feed')
        self.assertEqual(hits[0]['value'], 19.0)
        # and the pay-run rung, offered the same component, declines it
        values = {'NGAYCONGCHUAN': 19.0}
        filled = pay_period.fill_wired_inputs(
            values, set(), rule.pay_run_wires(), '2026-08-01', '2026-08-31')
        self.assertEqual(filled, [],
                         "only an UNRESOLVED code is ever written")
        self.assertEqual(values['NGAYCONGCHUAN'], 19.0)

    # =====================================================================
    # 10 — pay-neutrality: nothing changes until somebody draws a wire
    # =====================================================================
    def test_10_no_wire_no_change(self):
        """Test 10 — with no wire drawn, every value is what it was.

        The live half of this case (real payslips on `payobook`, recomputed
        before and after the upgrade) is in the phase report; this is the
        mechanical half, and it is the one that can regress silently.
        """
        cfg = self._config('RCNEU')
        rule = self._rule(cfg, 'NGAYCONGCHUAN')
        self.assertFalse(rule.period_key, "nothing is written on create")
        self.assertEqual(rule.pay_run_wires(), [])
        batch = self._aug_batch(cfg)
        employee, contract = self._people('neutral')
        values, prov = self._resolve(batch, {'Employee code': 'E1'},
                                     employee, contract)
        self.assertEqual(values.get('NGAYCONGCHUAN'), rule.default_value,
                         "an unwired component falls to its default exactly "
                         "as it always has")
        self.assertNotEqual(prov['NGAYCONGCHUAN']['src'], 'period')
        # the declared list is byte-for-byte what it was
        self.assertEqual(rule.declared_sources(), [])

    # =====================================================================
    # 14 (engine half) — two sources do not raise, and both are declared
    # =====================================================================
    def test_14_two_sources_two_declarations(self):
        """Test 14 — a column AND the run is the ordinary two-source case."""
        cfg = self._config('RCTWO')
        rule = self._rule(cfg, 'NGAYCONGCHUAN')
        rule.set_source_binding('excel', 'Standard working days')
        rule.set_source_binding('pay_run', 'STDDAYS')
        specs = rule.declared_sources()
        self.assertEqual([d['kind'] for d in specs], ['excel', 'pay_run'])
        # and a scheme reconfigured after the wire was drawn still renders
        cfg.source_priority = 'records,excel,api'
        self.assertEqual([d['kind'] for d in rule.declared_sources()][-1],
                         'pay_run')
        cfg.source_excel_enabled = False
        self.assertEqual([d['kind'] for d in rule.declared_sources()],
                         ['pay_run'],
                         "a disabled lane drops its rows; the run has no "
                         "switch and stays")

    # =====================================================================
    # 16 — the lane order tolerates an old scheme
    # =====================================================================
    def test_16_lane_order_tolerates_a_stored_string_that_predates_it(self):
        """Test 16 — `payrun` appends last however the priority was stored."""
        for n, stored in enumerate(('api,excel,records', 'records,api,excel',
                                    'excel', '', False)):
            cfg = self._config('RCLO%d' % n)
            cfg.source_priority = stored
            order = cfg._source_lane_order()
            self.assertIn('payrun', order,
                          "a missing token appends in default order — this "
                          "phase is the first thing to depend on that promise")
            self.assertEqual(order[-1], 'payrun',
                             "and it is pinned last: a stored order is data "
                             "somebody can edit, the ruling is not")
            self.assertEqual(cfg._source_kind_rank()[-1], 'pay_run')
        # a person still cannot rank the run above the file
        cfg = self._config('RCLOBAD')
        with self.assertRaises(ValidationError):
            cfg.source_priority = 'payrun,api,excel,records'

    # =====================================================================
    # Rails — nothing here may raise inside a payroll computation
    # =====================================================================
    def test_17_the_rung_never_raises(self):
        """Rail — a broken period, a missing key and junk wires all degrade."""
        values = {'X': 1.0}
        self.assertEqual(
            pay_period.fill_wired_inputs(values, {'X'}, [('X', 'STDDAYS')],
                                         None, None), [])
        self.assertEqual(values['X'], 1.0, "no dates, nothing written")
        self.assertEqual(
            pay_period.fill_wired_inputs(values, {'X'}, [None, (), ('X',)],
                                         '2026-08-01', '2026-08-31'), [])
        self.assertEqual(
            pay_period.fill_wired_inputs(values, {'X'}, [('X', 'NOPE')],
                                         '2026-08-01', '2026-08-31'), [])
        self.assertEqual(
            pay_period.fill_wired_inputs(values, {'X'}, [('MISSING', 'STDDAYS')],
                                         '2026-08-01', '2026-08-31'), [],
            "a code the scheme does not have is never invented")

    def test_18_a_wire_beats_a_code_that_merely_spells_the_same_thing(self):
        """Rail — a component CODED STDDAYS but WIRED to PAYMONTH gets the month.

        The only ordering question the two rungs can disagree on. What a person
        stated beats what a code happens to spell.
        """
        cfg = self._config('RCSPELL')
        rule = self._rule(cfg, 'STDDAYS')
        rule.set_source_binding('pay_run', 'PAYMONTH')
        batch = self._aug_batch(cfg)
        employee, contract = self._people('spell')
        values, prov = self._resolve(batch, {'Employee code': 'E1'},
                                     employee, contract)
        self.assertEqual(values.get('STDDAYS'), 8.0,
                         "August is month 8 — the wire, not the spelling")
        self.assertEqual(prov['STDDAYS']['key'], 'PAYMONTH')
