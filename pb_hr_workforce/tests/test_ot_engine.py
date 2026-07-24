# Part of Payobook. See LICENSE file for full copyright and licensing details.
"""Server tests for the Phase-K OT limits + Bonus-Hours engine and Overtime Desk.

Handover §6: 1 (facade gates / restriction), 6 (split math), 7 (bi-weekly window),
8 (approval recompute), 9 (reduction stays allowed), 10 (minor regression),
12 (bonus review filters/group-by/cap), 13 (bulk act survives), 14 (menu
retirement), 15 (facade writes no state / bonus_hours readonly via RPC).
"""

from datetime import date, timedelta

from odoo.exceptions import AccessError
from odoo.tests import TransactionCase, tagged

_INF = float('inf')


@tagged('post_install', '-at_install')
class TestOtEngine(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.Ceil = cls.env['pb.ot.ceiling']
        cls.Req = cls.env['hr.overtime.request']
        cls.Desk = cls.env['pb.ot.desk']
        cls.WE = cls.env['hr.attendance.weekentry']

        cls.emp = cls.env['hr.employee'].create({
            'name': 'OT Adult', 'company_id': cls.company.id})
        # a fixed weekday anchor (Wednesday) inside a known month
        anchor = date(2026, 6, 17)
        cls.wed = anchor - timedelta(days=anchor.weekday()) + timedelta(days=2)

        # weekday OT config so the grid path applies on a weekday
        cls.env['hr.overtime.config'].create({
            'name': 'WD OT K', 'overtime_type': 'weekday',
            'rate_multiplier': 1.5, 'sequence': 1, 'country_id': False})

        # one company-specific ceiling we mutate per test (wins over the global
        # seed row via _for_company's two-search resolver)
        cls.ceil = cls.Ceil.create({
            'name': 'K Test Ceiling', 'company_id': cls.company.id,
            'daily_cap': 0.0, 'weekly_cap': 0.0, 'biweekly_cap': 0.0,
            'monthly_cap': 0.0, 'annual_cap': 0.0, 'annual_cap_special': 0.0})

    def _caps(self, **kw):
        base = {'daily_cap': 0.0, 'weekly_cap': 0.0, 'biweekly_cap': 0.0,
                'monthly_cap': 0.0, 'annual_cap': 0.0, 'annual_cap_special': 0.0}
        base.update(kw)
        self.ceil.write(base)

    def _used(self, hours, day, state='approved', ot_type='weekday'):
        return self.Req.create({
            'employee_id': self.emp.id, 'company_id': self.company.id,
            'date': day, 'overtime_type': ot_type,
            'planned_hours': hours, 'actual_hours': hours,
            'approved_hours': hours if state in ('approved', 'submitted') else 0.0,
            'reason': 'x', 'state': state})

    # ------------------------------------------------------------- §6.6 split
    def test_06a_daily_split(self):
        self._caps(daily_cap=4.0)
        approved, bonus = self.Ceil._split(self.emp, self.wed, 6.0)
        self.assertEqual((approved, bonus), (4.0, 2.0))

    def test_06b_weekly_split(self):
        self._caps(weekly_cap=10.0)
        # 8h already used earlier in the same ISO week (Monday)
        self._used(8.0, self.wed - timedelta(days=2))
        approved, bonus = self.Ceil._split(self.emp, self.wed, 6.0)
        self.assertEqual((approved, bonus), (2.0, 4.0))

    def test_06c_tightest_wins(self):
        # daily allows 4, but the month has only 1 h of slack → 1 + 5
        self._caps(daily_cap=4.0, monthly_cap=5.0)
        self._used(4.0, self.wed - timedelta(days=3))   # 4 used earlier this month
        approved, bonus = self.Ceil._split(self.emp, self.wed, 6.0)
        self.assertEqual((approved, bonus), (1.0, 5.0))

    def test_06d_no_caps_all_approved(self):
        self._caps()   # everything 0 = not enforced
        self.assertEqual(self.Ceil._allowance(self.emp, self.wed), _INF)
        approved, bonus = self.Ceil._split(self.emp, self.wed, 6.0)
        self.assertEqual((approved, bonus), (6.0, 0.0))

    def test_06e_allowance_never_counts_bonus(self):
        # a prior request's BONUS hours must NOT reduce the allowance (rail 2)
        self._caps(daily_cap=10.0)
        r = self._used(4.0, self.wed)
        r.write({'bonus_hours': 20.0})   # huge bonus — must be ignored by _allowance
        # allowance = 10 - 4 (approved only) = 6
        self.assertEqual(self.Ceil._allowance(self.emp, self.wed, exclude_ids=[]), 6.0)

    # ------------------------------------------------------------- §6.7 biweekly
    def _odd_monday(self, start):
        d = start - timedelta(days=start.weekday())
        for _ in range(8):
            if d.isocalendar()[1] % 2 == 1:
                return d
            d += timedelta(days=7)
        return d

    def test_07_biweekly_window(self):
        self._caps(biweekly_cap=10.0)
        wk1 = self._odd_monday(date(2026, 6, 1))      # odd ISO week (pair start)
        wk2 = wk1 + timedelta(days=7)                  # next week — SAME pair
        wk3 = wk1 + timedelta(days=14)                 # next odd week — NEW pair
        self._used(6.0, wk1)
        # week 2 shares the fortnight → used 6, allowance 4 → 4 + 2
        a2, b2 = self.Ceil._split(self.emp, wk2, 6.0)
        self.assertEqual((a2, b2), (4.0, 2.0))
        # week 3 opens a fresh fortnight → allowance 10 → all approved
        a3, b3 = self.Ceil._split(self.emp, wk3, 6.0)
        self.assertEqual((a3, b3), (6.0, 0.0))

    # ------------------------------------------------------------- §6.8 recompute
    def test_08_approval_recompute(self):
        self._caps(daily_cap=4.0)
        # A submitted for 6h; its stored split is still 0 (direct create)
        a = self._used(6.0, self.wed, state='submitted')
        a.write({'approved_hours': 0.0})
        # meanwhile another 2h gets approved the same day → eats allowance
        self._used(2.0, self.wed, state='approved')
        a.action_approve()
        self.assertEqual(a.state, 'approved')
        self.assertEqual((a.approved_hours, a.bonus_hours), (2.0, 4.0))

    # ------------------------------------------------------------- §6.9 reduction
    def test_09_reduction_resplits_and_commits(self):
        self._caps(daily_cap=4.0)
        payload = {'cells': [{'rowId': self.emp.id, 'dayISO': self.wed.isoformat(),
                              'measure': 'weekday', 'value': 6.0}]}
        res = self.WE.save_week_entries(payload)
        self.assertTrue(res['results'][0]['ok'])
        self.assertEqual(res['results'][0]['approved'], 4.0)
        self.assertEqual(res['results'][0]['bonus'], 2.0)
        draft = self.Req.search([('employee_id', '=', self.emp.id),
                                 ('date', '=', self.wed)], limit=1)
        self.assertEqual((draft.approved_hours, draft.bonus_hours), (4.0, 2.0))
        # reduce to 4h — must re-split with no bonus and never raise
        payload['cells'][0]['value'] = 4.0
        res2 = self.WE.save_week_entries(payload)
        self.assertTrue(res2['results'][0]['ok'])
        self.assertEqual(res2['results'][0]['bonus'], 0.0)
        draft = draft.exists() or self.Req.search([
            ('employee_id', '=', self.emp.id), ('date', '=', self.wed)], limit=1)
        self.assertEqual((draft.approved_hours, draft.bonus_hours), (4.0, 0.0))

    # ------------------------------------------------------------- §6.10 minor
    def test_10_minor_ot_blocked_no_bonus(self):
        if 'pb.young.worker' not in self.env:
            self.skipTest('pb_young_worker not installed')
        Rule = self.env['pb.young.worker.rule'].sudo().with_context(active_test=False)
        # deactivate any existing rules and create a FRESH ACTIVE one — seeding
        # via _seed_vn_defaults would skip (its has-one check counts inactive
        # rows too), leaving no active rule and _has_any_rule() False.
        Rule.search([('company_id', '=', self.company.id)]).write({'active': False})
        self.env['pb.young.worker.rule'].sudo().create({
            'name': 'YW test', 'company_id': self.company.id, 'active': True,
            'band_ids': [(0, 0, {'age_min': 15, 'age_max': 18, 'ot_blocked': True,
                                 'night_blocked': True, 'max_hours_day': 8.0,
                                 'max_hours_week': 40.0})]})
        minor = self.env['hr.employee'].create({
            'name': 'Minor K', 'company_id': self.company.id,
            'birthday': date.today() - timedelta(days=365 * 16 + 60)})
        self._caps(daily_cap=4.0)
        from odoo.exceptions import ValidationError
        with self.assertRaises(ValidationError):
            self.Req.create({
                'employee_id': minor.id, 'company_id': self.company.id,
                'date': self.wed, 'overtime_type': 'weekday',
                'planned_hours': 6.0, 'actual_hours': 6.0, 'reason': 'x'})
        self.assertFalse(self.Req.search([('employee_id', '=', minor.id)]))

    # ------------------------------------------------------------- §6.1 gates
    def test_01_desk_gates(self):
        # a plain internal user cannot act
        user = self.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'Plain', 'login': 'k_plain',
            'group_ids': [(6, 0, [self.env.ref('base.group_user').id])]})
        with self.assertRaises(AccessError):
            self.Desk.with_user(user).act([1], 'approve')
        # an attendance manager WITHOUT payroll-manager is refused the bonus tab
        mgr = self.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'ApproverOnly', 'login': 'k_approver',
            'group_ids': [(6, 0, [
                self.env.ref('hr_attendance.group_hr_attendance_manager').id])]})
        # can open the desk…
        self.Desk.with_user(mgr).get_desk()
        # …but NOT the restricted bonus review
        with self.assertRaises(AccessError):
            self.Desk.with_user(mgr).get_bonus_hours({}, 0, 'employee')
        with self.assertRaises(AccessError):
            self.Desk.with_user(mgr).export_bonus_csv({})

    # ------------------------------------------------------------- §6.13 bulk
    def test_13_bulk_act_survives_bad_row(self):
        # 2 approvable requests + 1 doomed row (non-existent id). The batch must
        # never abort — 2 approved, 1 per-row failure chip. (A minor can never
        # BE a queue item: the E-gate blocks minor OT at creation, C18.63 — so
        # the realistic per-row failure is a vanished/invalid record.)
        self._caps(daily_cap=4.0)
        good1 = self._used(3.0, self.wed, state='submitted')
        good2 = self._used(2.0, self.wed - timedelta(days=1), state='submitted')
        res = self.Desk.act([good1.id, good2.id, 999999999], 'approve')
        oks = [r for r in res['results'] if r['ok']]
        fails = [r for r in res['results'] if not r['ok']]
        self.assertEqual(len(oks), 2)
        self.assertEqual(len(fails), 1)
        self.assertEqual(good1.state, 'approved')
        self.assertEqual(good2.state, 'approved')

    # ------------------------------------------------------------- §6.12 bonus
    def test_12_bonus_review_filters(self):
        self._caps(daily_cap=4.0)
        # two approved overflow requests (6h → 4 + 2 each) on distinct days
        for off in (0, 5):
            r = self._used(6.0, self.wed - timedelta(days=off), state='submitted')
            r.write({'approved_hours': 0.0})
            r.action_approve()
        data = self.Desk.get_bonus_hours({'preset': 'custom',
            'date_from': (self.wed - timedelta(days=10)).isoformat(),
            'date_to': (self.wed + timedelta(days=1)).isoformat()}, 0, 'employee')
        self.assertAlmostEqual(data['grand_hours'], 4.0)   # 2 + 2 bonus
        self.assertEqual(data['grand_count'], 2)
        self.assertEqual(len(data['groups']), 1)            # one employee
        # min_hours filter above the per-row bonus → nothing
        empty = self.Desk.get_bonus_hours({'min_hours': 5.0}, 0, 'employee')
        self.assertEqual(empty['grand_count'], 0)
        # group by day → two day-groups
        byday = self.Desk.get_bonus_hours({'preset': 'custom',
            'date_from': (self.wed - timedelta(days=10)).isoformat(),
            'date_to': (self.wed + timedelta(days=1)).isoformat()}, 0, 'day')
        self.assertEqual(len(byday['groups']), 2)

    # ------------------------------------------------------------- §6.14 menu
    def test_14_native_ot_menus_retired(self):
        IMD = self.env['ir.model.data']
        for xmlid in ('menu_overtime', 'menu_overtime_requests',
                      'menu_overtime_to_approve', 'menu_my_overtime',
                      'menu_overtime_config'):
            self.assertFalse(IMD.search([
                ('module', '=', 'pb_hr_workforce'), ('name', '=', xmlid)]),
                'menuitem %s should be retired' % xmlid)
        # the act_window actions still resolve (kept off-menu)
        self.assertTrue(self.env.ref(
            'pb_hr_workforce.action_overtime_request', raise_if_not_found=False))
        self.assertTrue(self.env.ref(
            'pb_hr_workforce.action_overtime_config', raise_if_not_found=False))

    # ------------------------------------------------------------- §6.15 readonly
    def test_15_bonus_hours_readonly_and_facades_stateless(self):
        # bonus_hours is declared readonly (the facade/RPC guard; the only ORM
        # writers are grid-save + approve-recompute)
        self.assertTrue(self.Req._fields['bonus_hours'].readonly)
        # facades never write a state field directly (grep-level, C18.17/§5.1)
        import os
        here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        desk_src = open(os.path.join(here, 'models', 'ot_desk.py')).read()
        self.assertNotIn(".write({'state'", desk_src)
        self.assertNotIn('.sudo().action_approve', desk_src)   # act() is real-user
        to = os.path.join(os.path.dirname(here), 'pb_timeoff', 'models', 'pb_timeoff.py')
        if os.path.exists(to):
            to_src = open(to).read()
            self.assertNotIn(".write({'state'", to_src)
            # reads may sudo (consolidation board, C18.65) but MUTATIONS never do
            self.assertNotIn('.sudo().action_', to_src)
            self.assertNotIn('.sudo().create', to_src)
