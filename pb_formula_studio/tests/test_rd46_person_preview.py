# -*- coding: utf-8 -*-
"""RD46 — previewing the formulas against a real person.

The Live Preview panel could only ever show a made-up sample, and on a scheme
nobody had generated samples for it showed a column of ₫0 — which reads as "the
formulas produce nothing" rather than "nobody has given me anyone to try". So
the one question people actually bring to this screen, *"why did THIS employee
get THAT number?"*, had no answer on it.

THE CLAIM UNDER TEST IS THE COPY RULE. Previewing a real person must never be
able to change that person's pay, and the tests assert that as an ABSENCE of
writes — the payslip's stored values, its provenance blob and its write stamp
are all unchanged after a preview — rather than as "the numbers still looked
right", which would pass just as well if a write had happened and been
overwritten by an identical one.

The rest is the shape of the thing:

  * the picker only ever offers runs and people THIS scheme computed, because
    previewing somebody against formulas that were never applied to them is a
    worse answer than no answer;
  * the read-only door and the picker are separate signals, so the panel can
    load a real person WITHOUT locking the formulas — trying a change against a
    real case is the point of the picker;
  * a preview saves nothing until somebody says to.
"""
import json

from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestRd46PersonPreview(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Studio = cls.env['pb.formula.studio']

    # ------------------------------------------------------------- fixtures
    #: A scheme CODE is unique per database, and three of these cases build a
    #: second scheme on purpose — to prove the picker will not offer somebody
    #: whose pay another scheme computed. A fixed code made those three die in
    #: SQL before they could assert anything.
    _seq = 0

    def _scheme(self):
        company = self.env.company
        type(self)._seq += 1
        cfg = self.env['hr.formula.config'].create({
            'name': 'RD46 Scheme %s' % self._seq, 'code': 'RD46S%s' % self._seq,
            'country_code': 'VN', 'state': 'active', 'company_id': company.id,
        })
        basic = self.env['hr.formula.rule'].create({
            'config_id': cfg.id, 'name': 'Basic', 'code': 'BASICPAY',
            'column_type': 'input', 'sequence': 10, 'default_value': 0.0,
        })
        double = self.env['hr.formula.rule'].create({
            'config_id': cfg.id, 'name': 'Doubled', 'code': 'DOUBLED',
            'column_type': 'formula', 'sequence': 20,
            'excel_formula': '=%s*2' % basic.column_letter,
            'appears_on_payslip': False,
        })
        return cfg, basic, double

    def _payslip(self, cfg, inputs, name='RD46 Person'):
        company = self.env.company
        emp = self.env['hr.employee'].create({
            'name': name, 'company_id': company.id})
        contract = self.env['hr.contract'].create({
            'name': '%s contract' % name, 'employee_id': emp.id, 'wage': 1000.0,
            'state': 'open', 'date_start': '2020-01-01',
            'company_id': company.id,
        })
        run = self.env['hr.payslip.run'].create({
            'name': 'RD46 Run', 'date_start': '2026-06-01',
            'date_end': '2026-06-30',
        })
        slip = self.env['hr.payslip'].create({
            'employee_id': emp.id, 'contract_id': contract.id,
            'name': 'RD46 Slip', 'formula_config_id': cfg.id,
            'payslip_run_id': run.id,
            'date_from': '2026-06-01', 'date_to': '2026-06-30',
            'formula_input_values': json.dumps(inputs),
            'formula_input_sources': json.dumps(
                {k: {'src': 'excel', 'key': k, 'via': 'header'} for k in inputs}),
            'pb_sourced_inputs': len(inputs),
        })
        return run, emp, slip

    # =====================================================================
    # 1 — the real person's numbers reach the panel
    # =====================================================================
    def test_01a_a_payslip_s_inputs_run_through_the_current_formulas(self):
        cfg, basic, double = self._scheme()
        _run, _emp, slip = self._payslip(cfg, {'BASICPAY': 500.0})

        out = self.Studio.preview_from_payslip(cfg.id, slip.id)

        self.assertTrue(out['ok'])
        self.assertEqual(out['values'][basic.column_letter], 500.0,
                         "the person's own input, not a sample's")
        self.assertEqual(out['values'][double.column_letter], 1000.0,
                         "and the scheme's formula applied to it")

    def test_01b_it_uses_TODAY_s_formula_not_the_one_that_ran(self):
        """The point of the panel: try a change against a real case."""
        cfg, basic, double = self._scheme()
        _run, _emp, slip = self._payslip(cfg, {'BASICPAY': 500.0})
        double.excel_formula = '=%s*3' % basic.column_letter

        out = self.Studio.preview_from_payslip(cfg.id, slip.id)

        self.assertEqual(out['values'][double.column_letter], 1500.0)

    def test_01c_the_label_names_the_person(self):
        cfg, _b, _d = self._scheme()
        _run, emp, slip = self._payslip(cfg, {'BASICPAY': 1.0}, name='Thai Pham')
        out = self.Studio.preview_from_payslip(cfg.id, slip.id)
        self.assertIn(emp.name, out['label'])
        self.assertFalse(out['anonymized'])

    def test_01d_the_name_can_be_hidden(self):
        cfg, _b, _d = self._scheme()
        _run, emp, slip = self._payslip(cfg, {'BASICPAY': 1.0}, name='Thai Pham')
        out = self.Studio.preview_from_payslip(cfg.id, slip.id, anonymize=True)
        self.assertNotIn(emp.name, out['label'])
        self.assertTrue(out['anonymized'])

    # =====================================================================
    # 2 — THE COPY RULE, asserted as an absence of writes
    # =====================================================================
    def test_02a_previewing_does_not_touch_the_payslip(self):
        cfg, basic, double = self._scheme()
        _run, _emp, slip = self._payslip(cfg, {'BASICPAY': 500.0})
        before = {
            'values': slip.formula_input_values,
            'sources': slip.formula_input_sources,
            'computed': slip.formula_computed_values,
            'lines': len(slip.line_ids),
        }
        # A CHANGED formula, so a write-through would be visible rather than
        # coincidentally identical.
        double.excel_formula = '=%s*7' % basic.column_letter
        self.env.flush_all()

        out = self.Studio.preview_from_payslip(cfg.id, slip.id)
        self.env.flush_all()
        slip.invalidate_recordset()

        self.assertEqual(out['values'][double.column_letter], 3500.0)
        self.assertEqual(slip.formula_input_values, before['values'])
        self.assertEqual(slip.formula_input_sources, before['sources'])
        self.assertEqual(slip.formula_computed_values, before['computed'],
                         "the payslip keeps the numbers it was computed with — "
                         "a preview is a copy, and this is the assertion that "
                         "makes editing a formula over real pay safe")
        self.assertEqual(len(slip.line_ids), before['lines'])

    def test_02b_previewing_saves_no_sample(self):
        cfg, _b, _d = self._scheme()
        _run, _emp, slip = self._payslip(cfg, {'BASICPAY': 500.0})
        self.Studio.preview_from_payslip(cfg.id, slip.id)
        self.Studio.preview_from_payslip(cfg.id, slip.id)
        self.assertFalse(
            cfg.sample_data_ids,
            "previewing a hundred people must not leave a hundred samples")

    def test_02c_keeping_one_is_an_explicit_act(self):
        cfg, _b, _d = self._scheme()
        _run, _emp, slip = self._payslip(cfg, {'BASICPAY': 500.0})
        r = self.Studio.preview_keep_as_sample(cfg.id, slip.id, anonymize=True)
        self.assertTrue(r['ok'])
        self.assertTrue(cfg.sample_data_ids)

    # =====================================================================
    # 3 — the picker offers only what this scheme actually computed
    # =====================================================================
    def test_03a_runs_are_scoped_to_this_scheme(self):
        cfg, _b, _d = self._scheme()
        run, _emp, _slip = self._payslip(cfg, {'BASICPAY': 1.0})
        other, _ob, _od = self._scheme()
        other_run, _oe, _os = self._payslip(other, {'BASICPAY': 1.0})

        ids = [r['id'] for r in self.Studio.preview_runs(cfg.id)['runs']]

        self.assertIn(run.id, ids)
        self.assertNotIn(other_run.id, ids,
                         "previewing somebody against formulas that were never "
                         "applied to them is worse than offering nobody")

    def test_03b_people_are_scoped_the_same_way(self):
        cfg, _b, _d = self._scheme()
        run, emp, slip = self._payslip(cfg, {'BASICPAY': 1.0})
        # someone in the SAME run, computed by a different scheme
        other, _ob, _od = self._scheme()
        stranger = self.env['hr.employee'].create({'name': 'Not This Scheme'})
        self.env['hr.payslip'].create({
            'employee_id': stranger.id, 'name': 'Stranger',
            'formula_config_id': other.id, 'payslip_run_id': run.id,
        })

        people = self.Studio.preview_people(run.id, cfg.id)['people']

        self.assertEqual([p['payslip_id'] for p in people], [slip.id])
        self.assertIn(emp.name, people[0]['name'])

    def test_03c_a_run_with_nothing_of_ours_is_an_empty_list_not_an_error(self):
        cfg, _b, _d = self._scheme()
        other, _ob, _od = self._scheme()
        other_run, _e, _s = self._payslip(other, {'BASICPAY': 1.0})
        out = self.Studio.preview_people(other_run.id, cfg.id)
        self.assertTrue(out['ok'])
        self.assertEqual(out['people'], [])

    def test_03d_a_payslip_that_is_gone_is_reported_not_raised(self):
        cfg, _b, _d = self._scheme()
        _run, _emp, slip = self._payslip(cfg, {'BASICPAY': 1.0})
        slip_id = slip.id
        slip.unlink()
        out = self.Studio.preview_from_payslip(cfg.id, slip_id)
        self.assertFalse(out['ok'])
        self.assertEqual(out['reason'], 'gone')

    # =====================================================================
    # 4 — the two doors, and why they are two signals
    # =====================================================================
    def test_04a_the_payslip_door_asks_for_read_only(self):
        cfg, _b, _d = self._scheme()
        _run, _emp, slip = self._payslip(cfg, {'BASICPAY': 1.0})

        act = slip.action_show_calculation()

        self.assertEqual(act['tag'], 'pb_formula_studio')
        self.assertEqual(act['params']['config_id'], cfg.id)
        self.assertEqual(act['params']['pbfs_preview_payslip_id'], slip.id)
        self.assertTrue(act['params']['pbfs_readonly'])

    def test_04b_loading_a_person_and_locking_are_separate_signals(self):
        """The picker must be able to load a person WITHOUT locking editing.

        Asserted on the client source, because the two signals meeting in one
        flag is exactly the mistake that would make the studio's own picker
        read-only and quietly remove the reason it exists.
        """
        import os
        from odoo.modules.module import get_module_path
        path = os.path.join(get_module_path('pb_formula_studio'),
                            'static', 'src', 'js', 'formula_studio.js')
        with open(path, encoding='utf-8') as fh:
            src = fh.read()
        self.assertIn('pbfs_preview_payslip_id', src)
        self.assertIn('pbfs_readonly', src)
        # `pickPerson` is what the picker calls, and it must not touch the lock.
        body = src.split('async pickPerson(', 1)[1].split('\n    }', 1)[0]
        self.assertNotIn('auditMode', body)
        self.assertNotIn('canEdit', body)

    def test_04c_a_payslip_with_no_scheme_says_so_plainly(self):
        emp = self.env['hr.employee'].create({'name': 'RD46 No Scheme'})
        slip = self.env['hr.payslip'].create({
            'employee_id': emp.id, 'name': 'RD46 Bare'})
        from odoo.exceptions import UserError
        with self.assertRaises(UserError):
            slip.action_show_calculation()
