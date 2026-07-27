# Part of Payobook. See LICENSE file for full copyright and licensing details.
"""Phase L — the 3-tier payroll approval chain, enforced model-side.

Handover §6: 1 (selection order), 2 (submit lands on level0), 3 (officer tier),
4 (HR + Finance tiers, analytics hook), 5 (no-tier user is refused BY THE MODEL
— the money assertion of this phase), 6 (super-admin), 7 (reject + reason),
10 (wizard submit on a non-draft run).

MAIL SAFETY (C18.47/48): the legacy level1→level2 advance creates and SENDS a
mail.mail to the final approvers. Every test that crosses that tier patches
``_notify_general_manager_for_batch_approval`` out — no test may put a row in
the live mail queue.
"""

from datetime import date
from unittest.mock import patch

from odoo.exceptions import AccessError, UserError
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestApprovalChain(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Run = cls.env['hr.payslip.run']
        cls.RunCls = type(cls.env['hr.payslip.run'])

        # Far-future period: keeps any analytics/period lookup off the real data.
        cls.d_from = date(2030, 1, 1)
        cls.d_to = date(2030, 1, 31)

        cls.employee = cls.env['hr.employee'].create({'name': 'L Chain Emp'})

        # Every test user carries the payroll ACL groups; only the TIER group
        # varies. So a refusal below is the tier gate talking, never a missing
        # model ACL — u_none can write pay runs and payslips and is still
        # refused every advance.
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

        cls.u_none = _user('l_none', [])
        cls.u_officer = _user('l_officer', ['pb_hr_payroll_base.group_payroll_base_officer'])
        cls.u_hr = _user('l_hr', ['pb_hr_payroll_base.group_payroll_base_manager'])
        cls.u_fin = _user('l_fin', ['pb_hr_payroll_base.group_payroll_final_approver'])
        cls.u_super = _user('l_super', ['pb_hr_payroll_base.group_payroll_super_admin'])

    # ------------------------------------------------------------- helpers
    def _payrun(self, state='draft', with_slip=True):
        """A pay run in ``state``. NEVER name a fixture ``run`` (C18.44)."""
        payrun = self.Run.create({
            'name': 'L Chain %s' % state,
            'date_start': self.d_from, 'date_end': self.d_to,
        })
        if with_slip:
            self.env['hr.payslip'].create({
                'name': 'L Chain slip', 'employee_id': self.employee.id,
                'date_from': self.d_from, 'date_to': self.d_to,
                'payslip_run_id': payrun.id,
            })
        if state != 'draft':
            payrun.write({'state': state})
        return payrun

    def _no_mail(self):
        """Patch the legacy GM notification (creates + sends a real mail)."""
        return patch.object(self.RunCls, '_notify_general_manager_for_batch_approval',
                            return_value=False)

    # ------------------------------------------------------------- §6.1
    def test_01_selection_order(self):
        sel = [k for k, _lbl in self.Run.fields_get(['state'])['state']['selection']]
        self.assertIn('level0', sel, "the Officer tier must exist on hr.payslip.run.state")
        self.assertEqual(sel.index('draft') + 1, sel.index('level0'),
                         "level0 must sit immediately after draft")
        self.assertEqual(sel.index('level0') + 1, sel.index('level1'),
                         "level0 must sit immediately before level1 (HR)")
        # frozen downstream contracts
        for key in ('level1', 'level2', 'done', 'cancel'):
            self.assertIn(key, sel, "existing state KEYS must never be renamed")

    # ------------------------------------------------------------- §6.2
    def test_02_submit_enters_at_level0(self):
        payrun = self._payrun()
        payrun.with_user(self.u_officer).done_payslip_run()
        self.assertEqual(payrun.state, 'level0',
                         "submit must enter the chain at the Officer tier, "
                         "not level1 and certainly not level2")
        self.assertTrue(payrun.slip_ids)
        self.assertFalse(payrun.slip_ids.filtered(lambda s: s.state == 'draft'),
                         "chain entry confirms every payslip")

    def test_02b_level1_done_from_draft_is_refused(self):
        """The regression that motivated the phase: the legacy advance writes
        its target state unconditionally, so from draft it jumped to level2."""
        payrun = self._payrun()
        with self.assertRaises(UserError):
            payrun.with_user(self.u_hr).action_payslip_run_level1_done()
        self.assertEqual(payrun.state, 'draft')

    def test_02c_submit_twice_is_refused(self):
        payrun = self._payrun()
        payrun.with_user(self.u_officer).done_payslip_run()
        with self.assertRaises(UserError):
            payrun.with_user(self.u_officer).done_payslip_run()
        self.assertEqual(payrun.state, 'level0')

    # ------------------------------------------------------------- §6.3
    def test_03_officer_tier(self):
        payrun = self._payrun('level0')
        payrun.with_user(self.u_officer).action_payslip_run_level0_done()
        self.assertEqual(payrun.state, 'level1')

        # …and an officer may go no further
        hr_run = self._payrun('level1')
        with self.assertRaises(AccessError):
            hr_run.with_user(self.u_officer).action_payslip_run_level1_done()
        self.assertEqual(hr_run.state, 'level1')

        fin_run = self._payrun('level2')
        with self.assertRaises(AccessError):
            fin_run.with_user(self.u_officer).action_payslip_run_level2_done()
        self.assertEqual(fin_run.state, 'level2')

    def test_03b_level0_sends_no_mail_and_leaves_slips_alone(self):
        payrun = self._payrun('level0')
        payrun.slip_ids.write({'state': 'level1'})
        before = self.env['mail.mail'].search_count([])
        payrun.with_user(self.u_officer).action_payslip_run_level0_done()
        self.assertEqual(self.env['mail.mail'].search_count([]), before,
                         "the Officer tier must never queue mail (C18.47/48)")
        self.assertEqual(payrun.slip_ids.mapped('state'), ['level1'],
                         "the Officer tier moves the run only")

    # ------------------------------------------------------------- §6.4
    def test_04_hr_and_finance_tiers(self):
        payrun = self._payrun('level1')
        with self._no_mail(), patch.object(
                self.RunCls, '_auto_generate_batch_analytics_on_level2') as analytics:
            payrun.with_user(self.u_hr).action_payslip_run_level1_done()
        self.assertEqual(payrun.state, 'level2')
        # The analytics auto-generation still fires on reaching level2. Which
        # implementation runs depends on what is installed: om_hr_payroll calls
        # _auto_generate_batch_analytics_on_level2, while om_hr_payroll_account
        # REPLACES the advance (no super()) and inlines its own generate_analytics
        # call — assert the hook only when the base implementation is the one in
        # the MRO. (That the gate ran at all is proven by test_05.)
        param = self.env['ir.config_parameter'].sudo().get_param(
            'payroll_analytics_approval.auto_generate', 'True')
        has_account = bool(self.env['ir.module.module'].sudo().search_count(
            [('name', '=', 'om_hr_payroll_account'), ('state', '=', 'installed')]))
        if not has_account:
            self.assertEqual(analytics.called, param == 'True')

        payrun.with_user(self.u_fin).action_payslip_run_level2_done()
        self.assertEqual(payrun.state, 'done',
                         "'done' stays the approved signal read downstream")

    def test_04b_hr_cannot_do_the_finance_tier(self):
        payrun = self._payrun('level2')
        with self.assertRaises(AccessError):
            payrun.with_user(self.u_hr).action_payslip_run_level2_done()
        self.assertEqual(payrun.state, 'level2')

    # ------------------------------------------------------------- §6.5
    def test_05_user_without_any_tier_is_refused_by_the_model(self):
        """The money assertion: no view, no button, no facade — the MODEL says no."""
        for state, method in (('level0', 'action_payslip_run_level0_done'),
                              ('level1', 'action_payslip_run_level1_done'),
                              ('level2', 'action_payslip_run_level2_done')):
            payrun = self._payrun(state)
            with self.assertRaises(AccessError):
                getattr(payrun.with_user(self.u_none), method)()
            self.assertEqual(payrun.state, state)

        draft = self._payrun()
        with self.assertRaises(AccessError):
            draft.with_user(self.u_none).done_payslip_run()
        with self.assertRaises(AccessError):
            draft.with_user(self.u_none).action_payslip_run_cancel()
        self.assertEqual(draft.state, 'draft')

    def test_05b_a_direct_state_write_cannot_skip_the_chain(self):
        """C18.24: the gates guard the ACTIONS — without a write() seal, anyone
        holding plain write access could call_kw write({'state':'done'}) and
        skip every tier. Proven live before the seal existed."""
        payrun = self._payrun('level1')
        for user in (self.u_none, self.u_officer, self.u_hr, self.u_fin):
            with self.assertRaises(AccessError):
                payrun.with_user(user).write({'state': 'done'})
            self.assertEqual(payrun.state, 'level1')
        # a client-forged context flag must NOT open the seal (the token is an
        # object() identity, unreachable from JSON)
        with self.assertRaises(AccessError):
            payrun.with_user(self.u_fin).with_context(
                pb_chain_state_write=True).write({'state': 'done'})
        self.assertEqual(payrun.state, 'level1')
        # …while the sanctioned action still works
        with self._no_mail():
            payrun.with_user(self.u_hr).action_payslip_run_level1_done()
        self.assertEqual(payrun.state, 'level2')

    # ------------------------------------------------------------- §6.6
    def test_06_super_admin_passes_every_tier(self):
        payrun = self._payrun()
        admin = payrun.with_user(self.u_super)
        admin.done_payslip_run()
        self.assertEqual(payrun.state, 'level0')
        admin.action_payslip_run_level0_done()
        self.assertEqual(payrun.state, 'level1')
        with self._no_mail():
            admin.action_payslip_run_level1_done()
        self.assertEqual(payrun.state, 'level2')
        admin.action_payslip_run_level2_done()
        self.assertEqual(payrun.state, 'done')

    # ------------------------------------------------------------- §6.7
    def test_07_reject_from_each_pending_tier(self):
        for state, user in (('draft', self.u_officer), ('level0', self.u_officer),
                            ('level1', self.u_hr), ('level2', self.u_fin)):
            payrun = self._payrun(state)
            payrun.with_user(user).with_context(
                pb_reject_note='Wrong period (%s)' % state).action_payslip_run_cancel()
            self.assertEqual(payrun.state, 'cancel')
            self.assertEqual(payrun.pb_reject_note, 'Wrong period (%s)' % state)
            self.assertEqual(payrun.pb_reject_uid, user,
                             "the actor is forced server-side, never client-supplied")
            self.assertTrue(payrun.pb_reject_date)

    def test_07b_officer_cannot_reject_an_hr_tier_run(self):
        payrun = self._payrun('level1')
        with self.assertRaises(AccessError):
            payrun.with_user(self.u_officer).action_payslip_run_cancel()
        self.assertEqual(payrun.state, 'level1')

    def test_07c_a_decided_run_can_no_longer_be_rejected(self):
        payrun = self._payrun('done')
        with self.assertRaises(UserError):
            payrun.with_user(self.u_super).action_payslip_run_cancel()
        self.assertEqual(payrun.state, 'done')

    def test_07d_reset_to_draft_is_finance_gated(self):
        """Same class of hole as the advances: 'Set to Draft' undoes the Finance
        decision and was guarded only by the button's invisible= rule."""
        payrun = self._payrun('done')
        with self.assertRaises(AccessError):
            payrun.with_user(self.u_officer).draft_payslip_run()
        self.assertEqual(payrun.state, 'done')
        payrun.with_user(self.u_fin).draft_payslip_run()
        self.assertEqual(payrun.state, 'draft')

    # ------------------------------------------------------------- §6.10
    def test_10_wizard_submit_seam(self):
        if 'pb.payrun.wizard' not in self.env:
            self.skipTest('pb_payrun_wizard is not installed')
        Wiz = self.env['pb.payrun.wizard']

        payrun = self._payrun()
        res = Wiz.with_user(self.u_officer).submit_for_approval(payrun.id)
        self.assertTrue(res['ok'])
        self.assertEqual(payrun.state, 'level0',
                         "the cockpit seam must enter at level0, not level2")

        # a second submit is a friendly refusal, state untouched
        res = Wiz.with_user(self.u_officer).submit_for_approval(payrun.id)
        self.assertFalse(res['ok'])
        self.assertTrue(res.get('msg'), "the refusal must carry a real reason")
        self.assertEqual(payrun.state, 'level0')

    def test_10b_wizard_submit_surfaces_the_tier_refusal(self):
        if 'pb.payrun.wizard' not in self.env:
            self.skipTest('pb_payrun_wizard is not installed')
        payrun = self._payrun()
        res = self.env['pb.payrun.wizard'].with_user(self.u_none).submit_for_approval(payrun.id)
        self.assertFalse(res['ok'])
        self.assertIn('Payroll Officer', res.get('msg', ''),
                      "the wizard must surface the model's own words, not a silent ok=False")
        self.assertEqual(payrun.state, 'draft')

    # ------------------------------------------------------ perms are honest
    def test_11_button_flags_match_the_gate(self):
        """Visibility is cosmetic, but it must never disagree with the gate."""
        for state, allowed in (('level0', self.u_officer),
                               ('level1', self.u_hr), ('level2', self.u_fin)):
            payrun = self._payrun(state)
            self.assertTrue(payrun.with_user(allowed).pb_awaiting_me)
            self.assertTrue(payrun.with_user(allowed)._pb_tier_ok(state))
            self.assertFalse(payrun.with_user(self.u_none).pb_awaiting_me)
            self.assertFalse(payrun.with_user(self.u_none)._pb_tier_ok(state))
            self.assertFalse(payrun.with_user(self.u_none).pb_can_reject)

        officer_run = self._payrun('level0')
        self.assertTrue(officer_run.with_user(self.u_officer).pb_can_approve_officer)
        self.assertFalse(officer_run.with_user(self.u_none).pb_can_approve_officer)
        self.assertFalse(officer_run.with_user(self.u_officer).pb_can_submit,
                         "a run already in the chain cannot be submitted again")

    # ------------------------------------------ combined-review fixes (G–M pass)
    def test_12_cancel_and_draft_writes_are_sealed_too(self):
        """Review L-2: a raw call_kw write to 'cancel' killed a run awaiting
        Finance with no owning tier and no testimony; a raw write to 'draft'
        undid a Finance decision. Every state value is sealed now."""
        payrun = self._payrun('level2')
        for user in (self.u_officer, self.u_hr):
            with self.assertRaises(AccessError):
                payrun.with_user(user).write({'state': 'cancel'})
        self.assertEqual(payrun.state, 'level2')
        done_run = self._payrun('done')
        for user in (self.u_officer, self.u_hr):
            with self.assertRaises(AccessError):
                done_run.with_user(user).write({'state': 'draft'})
        self.assertEqual(done_run.state, 'done')

    def test_13_sudo_server_caller_passes_the_tier(self):
        """Review L-3: the analytics finalize path advances level2 under sudo()
        with a user who holds no Finance tier — sanctioned server code, and
        call_kw can never hand a client su."""
        payrun = self._payrun('level2')
        with self._no_mail():
            payrun.with_user(self.u_none).sudo().action_payslip_run_level2_done()
        self.assertEqual(payrun.state, 'done')

    def test_14_demo_authority_stops_at_the_demo_world(self):
        """Review L-1: a demo login drives the chain ONLY on generator-stamped
        demo runs — its all-records rules must never walk a REAL run."""
        try:
            demo_group = self.env.ref('pb_demo.group_payobook_demo')
        except ValueError:
            self.skipTest('pb_demo is not installed')
        u_demo = self.env['res.users'].create({
            'name': 'l_demo', 'login': 'l_demo',
            'group_ids': [(6, 0, [self.env.ref('base.group_user').id,
                                  demo_group.id])],
        })
        real_run = self._payrun('level0')
        with self.assertRaises(AccessError):
            real_run.with_user(u_demo).action_payslip_run_level0_done()
        self.assertEqual(real_run.state, 'level0')
        self.assertFalse(real_run.with_user(u_demo).pb_awaiting_me,
                         "the cosmetic flag must not disagree with the gate")
        if 'is_demo' not in self.Run._fields:
            self.skipTest('hr.payslip.run.is_demo is absent (pb_demo partial)')
        demo_run = self._payrun('level0')
        demo_run.sudo().write({'is_demo': True})
        demo_run.with_user(u_demo).action_payslip_run_level0_done()
        self.assertEqual(demo_run.state, 'level1',
                         "a demo login must still drive the showcase chain")
        # even on a demo run, the raw state write stays sealed
        sealed_run = self._payrun('level2')
        sealed_run.sudo().write({'is_demo': True})
        with self.assertRaises(AccessError):
            sealed_run.with_user(u_demo).write({'state': 'done'})

    def test_15_vi_translations_load(self):
        """Review L-7: the pb_approval loader assert existed; pb_payruns' own
        python strings were never load-asserted (the C18.74 failure mode)."""
        lang = self.env['res.lang'].with_context(active_test=False).search(
            [('code', '=', 'vi_VN')], limit=1)
        if not lang or not lang.active:
            self.skipTest('vi_VN is not active on this database')
        from odoo.tools.translate import code_translations
        py = code_translations.get_python_translations('pb_payruns', 'vi_VN')
        self.assertTrue(py, "no python translations loaded from pb_payruns/i18n/vi_VN.po")
        self.assertEqual(py.get('This pay run is not awaiting an approval decision.'),
                         'Đợt lương này không ở trạng thái chờ quyết định phê duyệt.')
