# -*- coding: utf-8 -*-
"""WDGAP PR merge — seam 2b: a held payslip in an EXTRA run (PR-D) is left out
of the bank file, the release and the payslip send-out like in any other run
(PR-C). Same fixture as PR-C's own tests; only the run's kind differs.
Skips itself where pb_payruns (the run kinds) is not installed.
"""
from datetime import date
from unittest.mock import patch

from odoo.tests import tagged

from .test_wdgap_prc_hold import _PrcFixture, _RENDER, _valid_pdf_bytes


@tagged('post_install', '-at_install', 'wdgap_prm')
class TestPrMergeExtraRunHold(_PrcFixture):

    @classmethod
    def _make_world(cls):
        Run = cls.env['hr.payslip.run']
        field = Run._fields.get('pb_run_kind')
        kinds = [k for k, _l in field.selection] if field and isinstance(
            field.selection, list) else []
        cls.has_extra = 'extra' in kinds
        vals = {'name': 'PRM Extra run June',
                'date_start': date(2026, 6, 1), 'date_end': date(2026, 6, 30)}
        if cls.has_extra:
            vals['pb_run_kind'] = 'extra'
        cls.payrun = Run.create(vals)
        cls.emp_a = cls._employee('PRM Alpha', '223456789012')
        cls.emp_b = cls._employee('PRM Beta', '223456789013')
        cls.emp_c = cls._employee('PRM Gamma', '223456789014')
        cls.emp_d = cls._employee('PRM Delta', '223')    # fails account_ok
        cls.slip_a = cls._slip(cls.emp_a, 5000000)
        cls.slip_b = cls._slip(cls.emp_b, 3000000)
        cls.slip_c = cls._slip(cls.emp_c, 2500000)
        cls.slip_d = cls._slip(cls.emp_d, 1000000)
        cls._finish_run(cls.payrun)

    def setUp(self):
        super().setUp()
        if not self.has_extra:
            self.skipTest('pb_payruns has no Extra run kind')
        self.assertEqual(self.payrun.pb_run_kind, 'extra')

    def test_2b_held_person_in_an_extra_run_is_left_out_everywhere(self):
        self._hold(self.slip_b)
        bank_file = self._approved_file()
        self.assertEqual(set(bank_file.slip_ids.ids), {self.slip_a.id, self.slip_c.id})
        self.assertEqual(bank_file.held_count, 1)
        held = [r for r in bank_file.excluded() if r.get('on_hold')]
        self.assertEqual([r['employee'] for r in held], ['PRM Beta'])
        raw = bank_file.attachment_id.sudo().raw.decode('utf-8-sig', 'ignore')
        self.assertNotIn('PRM Beta', raw)
        release = self._released(bank_file, ref='REF-PRM')
        self.assertEqual(release.beneficiaries, 2)
        self.assertTrue(self.slip_a.pb_paid_on)
        self.assertFalse(self.slip_b.pb_paid_on, 'a held person was marked paid')
        self.assertFalse(self.slip_d.pb_paid_on)
        batch = self.env['pb.payslip.delivery.batch'].create({'run_id': self.payrun.id})
        with patch(_RENDER, return_value=_valid_pdf_bytes()):
            batch.action_send()
        state = {l.slip_id.id: l.state for l in batch.line_ids}
        self.assertEqual(state[self.slip_b.id], 'held')
        self.assertEqual(state[self.slip_a.id], 'sent')
        self.assertEqual(batch.held_count, 1)
