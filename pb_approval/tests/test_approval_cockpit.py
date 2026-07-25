# Part of Payobook. See LICENSE file for full copyright and licensing details.
"""Phase L — the Approvals cockpit facade (``pb.approval``).

Handover §6: 5 (facade gate: a user in NONE of the tier groups is refused on
get_approvals AND approve_run), 7 (reject_run gated + reason required),
8 (approve on a decided run → friendly ok=False), 9 (downstream contract: a
'done' run is still listed by pb_pay_delivery), 11 (vi.po loads),
12 (the ``mine`` flag is per-tier correct).
"""

from datetime import date
from unittest.mock import patch

from odoo.exceptions import AccessError
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestApprovalCockpit(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Run = cls.env['hr.payslip.run']
        cls.RunCls = type(cls.env['hr.payslip.run'])
        cls.Appr = cls.env['pb.approval']
        cls.d_from = date(2030, 2, 1)
        cls.d_to = date(2030, 2, 28)
        cls.employee = cls.env['hr.employee'].create({'name': 'L Cockpit Emp'})

        # payroll ACLs for everyone; only the TIER group varies (see the chain
        # test's note) — a refusal here is always the gate, never an ACL.
        base_groups = ['base.group_user', 'om_hr_payroll.group_hr_payroll_manager',
                       # read-only need of the level2 cascade: the formula engine's
                       # _trigger_mid_cycle_carryover searches hr.payroll.import.batch
                       # WITHOUT sudo (pre-existing, reported — not a Phase-L change)
                       'pb_hr_payroll_formula.group_formula_manager']

        def _user(login, groups):
            return cls.env['res.users'].create({
                'name': login, 'login': login,
                'group_ids': [(6, 0, [cls.env.ref(g).id
                                      for g in base_groups + list(groups)])],
            })

        cls.u_none = _user('l_c_none', [])
        cls.u_officer = _user('l_c_officer', ['pb_hr_payroll_base.group_payroll_base_officer'])
        cls.u_hr = _user('l_c_hr', ['pb_hr_payroll_base.group_payroll_base_manager'])
        cls.u_fin = _user('l_c_fin', ['pb_hr_payroll_base.group_payroll_final_approver'])

    def _payrun(self, state, name='L Cockpit'):
        payrun = self.Run.create({
            'name': '%s %s' % (name, state),
            'date_start': self.d_from, 'date_end': self.d_to,
        })
        self.env['hr.payslip'].create({
            'name': 'L Cockpit slip', 'employee_id': self.employee.id,
            'date_from': self.d_from, 'date_to': self.d_to,
            'payslip_run_id': payrun.id,
        })
        if state != 'draft':
            payrun.write({'state': state})
        return payrun

    def _mine_ids(self, user):
        data = self.Appr.with_user(user).get_approvals()
        return {r['id'] for r in data['pending'] if r['mine']}

    # ------------------------------------------------------------- §6.5
    def test_05_facade_gate(self):
        payrun = self._payrun('level1')
        with self.assertRaises(AccessError):
            self.Appr.with_user(self.u_none).get_approvals()
        with self.assertRaises(AccessError):
            self.Appr.with_user(self.u_none).approve_run(payrun.id)
        with self.assertRaises(AccessError):
            self.Appr.with_user(self.u_none).reject_run(payrun.id, 'nope')
        self.assertEqual(payrun.state, 'level1')

    def test_05b_wrong_tier_gets_the_models_own_words(self):
        """An officer may OPEN the cockpit (facade gate passes) but the model
        refuses the HR tier — and the refusal text is the model's, not a
        generic 'Action blocked'."""
        payrun = self._payrun('level1')
        res = self.Appr.with_user(self.u_officer).approve_run(payrun.id)
        self.assertFalse(res['ok'])
        self.assertIn('HR Manager', res['msg'])
        self.assertEqual(payrun.state, 'level1')

    # ------------------------------------------------------------- §6.12
    def test_12_mine_flag_per_tier(self):
        r0 = self._payrun('level0')
        r1 = self._payrun('level1')
        r2 = self._payrun('level2')

        officer_mine = self._mine_ids(self.u_officer)
        self.assertIn(r0.id, officer_mine)
        self.assertNotIn(r1.id, officer_mine)
        self.assertNotIn(r2.id, officer_mine)

        hr_mine = self._mine_ids(self.u_hr)
        self.assertIn(r1.id, hr_mine)
        self.assertNotIn(r2.id, hr_mine)

        fin_mine = self._mine_ids(self.u_fin)
        self.assertIn(r2.id, fin_mine)

        data = self.Appr.with_user(self.u_officer).get_approvals()
        lanes = {lane['key']: lane for lane in data['lanes']}
        self.assertEqual(list(lanes), ['level0', 'level1', 'level2'])
        self.assertIn(r0.id, [x['id'] for x in lanes['level0']['runs']])
        self.assertGreaterEqual(data['summary']['officer'], 1)
        self.assertGreaterEqual(data['summary']['hr'], 1)
        self.assertGreaterEqual(data['summary']['fin'], 1)
        # chain stepper position
        self.assertEqual([x['step'] for x in lanes['level2']['runs']
                          if x['id'] == r2.id], [2])

    # --------------------------------------------------------- approve/reject
    def test_08_approve_a_decided_run_is_friendly(self):
        for state in ('done', 'cancel'):
            payrun = self._payrun(state)
            res = self.Appr.with_user(self.u_fin).approve_run(payrun.id)
            self.assertFalse(res['ok'])
            self.assertTrue(res['msg'])
            self.assertEqual(payrun.state, state)

    def test_08b_approve_advances_the_owning_tier(self):
        payrun = self._payrun('level0')
        res = self.Appr.with_user(self.u_officer).approve_run(payrun.id)
        self.assertTrue(res['ok'], res.get('msg'))
        self.assertEqual(payrun.state, 'level1')

        with patch.object(self.RunCls, '_notify_general_manager_for_batch_approval',
                          return_value=False):
            res = self.Appr.with_user(self.u_hr).approve_run(payrun.id)
        self.assertTrue(res['ok'], res.get('msg'))
        self.assertEqual(payrun.state, 'level2')

    def test_07_reject_needs_a_reason_and_stores_it(self):
        payrun = self._payrun('level0')
        res = self.Appr.with_user(self.u_officer).reject_run(payrun.id, '   ')
        self.assertFalse(res['ok'])
        self.assertEqual(payrun.state, 'level0', "no reason → no state change")

        res = self.Appr.with_user(self.u_officer).reject_run(payrun.id, 'Bad period')
        self.assertTrue(res['ok'], res.get('msg'))
        self.assertEqual(payrun.state, 'cancel')
        self.assertEqual(payrun.pb_reject_note, 'Bad period')
        self.assertEqual(payrun.pb_reject_uid, self.u_officer)

        data = self.Appr.with_user(self.u_officer).get_approvals()
        row = [r for r in data['recent'] if r['id'] == payrun.id]
        self.assertTrue(row, "a rejected run shows in the recently-decided rail")
        self.assertEqual(row[0]['reject_note'], 'Bad period')

    def test_07b_reject_is_gated_by_the_owning_tier(self):
        payrun = self._payrun('level2')
        res = self.Appr.with_user(self.u_officer).reject_run(payrun.id, 'not mine')
        self.assertFalse(res['ok'])
        self.assertIn('Finance', res['msg'])
        self.assertEqual(payrun.state, 'level2')

    # ------------------------------------------------------------- §6.9
    def test_09_downstream_done_contract(self):
        if 'pb.pay.delivery' not in self.env:
            self.skipTest('pb_pay_delivery is not installed')
        payrun = self._payrun('level2')
        payrun.with_user(self.u_fin).action_payslip_run_level2_done()
        self.assertEqual(payrun.state, 'done')
        # read as the test superuser: the delivery facade has its own (finance)
        # gate, which is not what this contract test is about
        runs = self.env['pb.pay.delivery'].get_recent_runs()
        self.assertIn(payrun.id, [r['id'] for r in runs],
                      "'done' must stay the approved signal Pay & Deliver reads")

    # ------------------------------------------------------------- §6.11
    def test_11_vi_translations_load(self):
        lang = self.env['res.lang'].with_context(active_test=False).search(
            [('code', '=', 'vi_VN')], limit=1)
        if not lang or not lang.active:
            self.skipTest('vi_VN is not active on this database')
        # the loader is the thing under test: an entry is only picked up when it
        # carries BOTH "#. module:" and the "#. odoo-python"/"#. odoo-javascript"
        # marker — without the marker the PO parses fine and translates nothing
        from odoo.tools.translate import code_translations
        py = code_translations.get_python_translations('pb_approval', 'vi_VN')
        self.assertTrue(py, "no python translations loaded from pb_approval/i18n/vi_VN.po")
        self.assertEqual(py.get('Officer review'), 'Chuyên viên duyệt')
        web = code_translations.get_web_translations('pb_approval', 'vi_VN')
        self.assertTrue(web['messages'], "no web (OWL/JS) translations loaded")

        labels = self.Appr.with_context(lang='vi_VN')._stage_labels()
        self.assertEqual(labels['level0'][0], 'Chuyên viên duyệt')
        self.assertEqual(labels['level2'][1], 'Tài chính / Tổng giám đốc')
