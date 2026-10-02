# -*- coding: utf-8 -*-
"""SC-4 — the Run Payroll wizard reshapes itself to the scheme's source lanes.

Hiding a button is chrome; the contract here is SERVER truth: a scheme whose
spreadsheet lane is off must refuse an upload however it arrives, and a scheme
whose connected-system lane is off must refuse a sync — a stale browser tab,
a bookmark or a script must not be able to walk through a door the settings
closed.
"""
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestSc4LaneGates(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Wizard = cls.env['pb.payrun.wizard']
        cls.Config = cls.env['hr.formula.config']

    def _scheme(self, code, **vals):
        cfg = self.Config.create(dict({
            'name': 'SC4 %s' % code, 'code': code, 'country_code': 'VN',
            'state': 'active'}, **vals))
        rule = self.env['hr.formula.rule'].create({
            'config_id': cfg.id, 'name': 'Base pay', 'code': '%sPAY' % code,
            'column_type': 'input'})
        rule.set_source_binding('excel', 'Base pay column', origin='board')
        return cfg

    def test_01_excel_lane_off_hides_the_upload_step(self):
        cfg = self._scheme('SC4A', source_excel_enabled=False)
        gate = self.Wizard.spreadsheet_gate({'config_id': cfg.id})
        wanting = [c['id'] for c in (gate.get('choices') or [])]
        self.assertNotIn(cfg.id, wanting,
                         "a scheme that takes no files must not put the "
                         "upload step in anybody's way")

    def test_02_excel_lane_off_refuses_an_upload_server_side(self):
        cfg = self._scheme('SC4B', source_excel_enabled=False)
        run = self.env['hr.payslip.run'].create({
            'name': 'SC4 run', 'date_start': '2026-06-01',
            'date_end': '2026-06-30'})
        out = self.Wizard.attach_spreadsheet(
            run.id, cfg.id, 'Zm9v', 'pay.xlsx',
            '2026-06-01', '2026-06-30')
        self.assertFalse(out['ok'])
        self.assertIn('sources settings', out['msg'])

    def test_03_api_lane_off_empties_the_sync_plan_and_refuses_steps(self):
        conn = self.env['hr.integration.connector'].create({
            'name': 'SC4 conn', 'connector_type': 'demo'})
        cfg = self._scheme('SC4C', source_api_enabled=False,
                           connector_id=conn.id)
        vals = {'config_id': cfg.id}
        plan = self.Wizard.sync_plan(vals)
        self.assertEqual(plan, {'steps': [], 'unroutable': []})
        step = self.Wizard.sync_step(
            {'label': 'People', 'connector_id': conn.id, 'endpoint_id': 1},
            vals)
        self.assertIn('sources settings', step['error'])
        out = self.Wizard.update_records_from_feed(vals)
        self.assertFalse(out['ok'])
        self.assertIn('sources settings', out['msg'])

    def test_04_the_gate_carries_the_lanes_even_when_no_file_is_wanted(self):
        cfg = self._scheme('SC4D', source_excel_enabled=False,
                           source_priority='records,api,excel')
        gate = self.Wizard.spreadsheet_gate({'config_id': cfg.id})
        lanes = gate.get('lanes') or {}
        self.assertFalse(lanes.get('excel'))
        self.assertTrue(lanes.get('api'))
        self.assertTrue(lanes.get('records_first'),
                        "the wizard needs this to caption 'Update Payobook' "
                        "truthfully when records are the source of truth")

    def test_05_defaults_change_nothing(self):
        cfg = self._scheme('SC4E')
        gate = self.Wizard.spreadsheet_gate({'config_id': cfg.id})
        self.assertTrue(gate.get('wanted'),
                        "an untouched scheme with an excel binding still "
                        "wants its file — the gate's behaviour is unchanged")
        lanes = gate.get('lanes') or {}
        self.assertTrue(lanes.get('api') and lanes.get('excel')
                        and lanes.get('records'))
