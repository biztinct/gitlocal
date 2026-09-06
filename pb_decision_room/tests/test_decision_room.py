# -*- coding: utf-8 -*-
"""The Decision Room's server surface — the numbered facts from WFPLAN P1.

Every test here is one of the numbered cases in
`docs/handovers/WFPLAN_P1_DECISION_ROOM.md` §7 and says which one it is, so a
reader of the phase report can match a row to a method without guessing.

The load-bearing ones are T1 (a reader with no group gets an EXPLAINED empty
room and never an access dialog), T2/T3 (the baseline is the company's own
roster and nobody else's) and T8 (the room answers in under 800 ms warm on the
4,500-person demo company — a planning screen that takes two seconds to open is
a planning screen nobody opens twice).
"""
import logging
import time

from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests.common import TransactionCase, tagged
from odoo.tools import mute_logger

_logger = logging.getLogger(__name__)


@tagged('post_install', '-at_install')
class TestDecisionRoomFacade(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Room = cls.env['pb.decision.room']
        cls.Plan = cls.env['pb.decision.plan']
        cls.Assumptions = cls.env['pb.decision.assumptions']
        # The company with the most people on it: on the master that is the
        # Vietnam demo (company 5), on a tenant it is the only one there is.
        cls.env.cr.execute("""
            SELECT company_id, COUNT(*) FROM hr_employee
             WHERE active AND company_id IS NOT NULL
             GROUP BY company_id ORDER BY 2 DESC LIMIT 1
        """)
        row = cls.env.cr.fetchone()
        cls.company = cls.env['res.company'].browse(row[0]) if row \
            else cls.env.company
        cls.user_none = cls.env['res.users'].create({
            'name': 'No Decision Room', 'login': 'dr_none@test.local',
            'group_ids': [(6, 0, [cls.env.ref('base.group_user').id])],
            'company_id': cls.company.id,
            'company_ids': [(6, 0, [cls.company.id])],
        })
        cls.user_plan = cls.env['res.users'].create({
            'name': 'Plans the year', 'login': 'dr_user@test.local',
            'group_ids': [(6, 0, [
                cls.env.ref('base.group_user').id,
                cls.env.ref('pb_decision_room.group_decision_user').id])],
            'company_id': cls.company.id,
            'company_ids': [(6, 0, [cls.company.id])],
        })
        cls.user_other = cls.env['res.users'].create({
            'name': 'Also plans the year', 'login': 'dr_other@test.local',
            'group_ids': [(6, 0, [
                cls.env.ref('base.group_user').id,
                cls.env.ref('pb_decision_room.group_decision_user').id])],
            'company_id': cls.company.id,
            'company_ids': [(6, 0, [cls.company.id])],
        })
        cls.user_lead = cls.env['res.users'].create({
            'name': 'Owns the assumptions', 'login': 'dr_lead@test.local',
            'group_ids': [(6, 0, [
                cls.env.ref('base.group_user').id,
                cls.env.ref('pb_decision_room.group_decision_manager').id])],
            'company_id': cls.company.id,
            'company_ids': [(6, 0, [cls.company.id])],
        })

    def _room(self, user, **kw):
        return self.Room.with_user(user).with_company(self.company)\
            .with_context(allowed_company_ids=[self.company.id])\
            .get_room(company_id=self.company.id, **kw)

    def _as(self, user):
        return self.Room.with_user(user).with_company(self.company)\
            .with_context(allowed_company_ids=[self.company.id])

    # -------------------------------------------------------------- T1
    def test_t1_a_reader_with_no_group_gets_an_explained_empty_room(self):
        """T1. Never an AccessError: the screen has to be able to SAY what it
        is and who to ask, and an access dialog says neither."""
        room = self._room(self.user_none)
        self.assertFalse(room['allowed'])
        self.assertFalse(room['can_manage'])
        self.assertEqual(room['baseline']['teams'], [])
        self.assertEqual(room['plans'], [])

    # -------------------------------------------------------------- T2
    def test_t2_the_baseline_is_this_companys_own_roster(self):
        """T2. Team heads add up to the active employees in the company, roles
        add up to their team, and nothing is priced at zero."""
        room = self._room(self.user_plan, refresh=True)
        self.assertTrue(room['allowed'])
        baseline = room['baseline']
        teams = baseline['teams']
        self.assertTrue(teams, 'the demo company must have at least one team')
        self.assertLessEqual(len(teams), 13, '12 teams plus "Other teams"')
        active = self.env['hr.employee'].with_context(
            active_test=True).search_count([('company_id', '=', self.company.id)])
        self.assertEqual(sum(t['heads'] for t in teams), active)
        self.assertEqual(baseline['headcount'], active)
        # The strongest form of the claim: EVERY person is inside some role of
        # some team. A roll-up that drops a role passes the per-team check and
        # fails this one — which is exactly how five of AB Mauri's people went
        # missing before it was written.
        self.assertEqual(
            sum(r['heads'] for t in teams for r in t['roles']), active,
            'the roll-up lost people between the teams and their roles')
        for team in teams:
            self.assertGreater(team['heads'], 0, team['name'])
            self.assertGreater(team['pay_month_avg'], 0, team['name'])
            self.assertEqual(sum(r['heads'] for r in team['roles']),
                             team['heads'], team['name'])
            for role in team['roles']:
                self.assertGreater(role['pay_month_avg'], 0,
                                   '%s / %s' % (team['name'], role['name']))
                self.assertIn(role['level'], (1, 2, 3, 4))

    # -------------------------------------------------------------- T3
    def test_t3_the_baseline_is_company_scoped(self):
        """T3. Another company's roster is another company's roster."""
        other = self.env['res.company'].search(
            [('id', '!=', self.company.id)], limit=1)
        if not other:
            self.skipTest('this database has only one company')
        self.user_plan.write({'company_ids': [(4, other.id)]})
        room = self.Room.with_user(self.user_plan).with_company(other)\
            .with_context(allowed_company_ids=[other.id])\
            .get_room(company_id=other.id, refresh=True)
        mine = self._room(self.user_plan)
        self.assertNotEqual(room['baseline']['headcount'],
                            mine['baseline']['headcount'])
        self.assertEqual(room['company']['id'], other.id)

    # -------------------------------------------------------------- T4
    def test_t4_assumptions_are_created_once_per_company(self):
        """T4. First read creates the row; the second gets the same one; a
        duplicate is refused by the database, not by hope."""
        first = self.Assumptions.get_for_company(self.company)
        second = self.Assumptions.get_for_company(self.company)
        self.assertTrue(first.id)
        self.assertEqual(first.id, second.id)
        with self.assertRaises(Exception), mute_logger('odoo.sql_db'):
            with self.env.cr.savepoint():
                self.Assumptions.create({'company_id': self.company.id})

    # -------------------------------------------------------------- T5
    def test_t5_saving_a_plan_creates_replaces_and_refuses(self):
        """T5. Create, replace, refuse a duplicate name, refuse the 21st."""
        room = self._as(self.user_plan)
        plan_id = room.save_plan({
            'name': 'T5 first', 'company_id': self.company.id,
            'state': {'target': 0}, 'goals': {}, 'summary': {'profit': 1},
        })
        self.assertTrue(plan_id)
        with self.assertRaises(UserError):
            room.save_plan({'name': 'T5 first',
                            'company_id': self.company.id, 'state': {}})
        same = room.save_plan({
            'name': 'T5 first', 'replace': True,
            'company_id': self.company.id, 'state': {'target': 99},
            'summary': {'profit': 2},
        })
        self.assertEqual(same, plan_id)
        self.assertEqual(self.Plan.browse(plan_id).state, {'target': 99})
        with self.assertRaises(UserError):
            room.save_plan({'name': '   ', 'company_id': self.company.id})
        existing = self.Plan.search_count([('company_id', '=', self.company.id)])
        for n in range(existing, 20):
            room.save_plan({'name': 'T5 filler %s' % n,
                            'company_id': self.company.id, 'state': {}})
        with self.assertRaises(UserError):
            room.save_plan({'name': 'T5 one too many',
                            'company_id': self.company.id, 'state': {}})

    # -------------------------------------------------------------- T6
    def test_t6_a_plan_belongs_to_whoever_saved_it(self):
        """T6. Mine, yes. Somebody else's, no — and the refusal is a sentence
        a person can act on. The planning lead may remove anyone's."""
        mine = self._as(self.user_plan).save_plan({
            'name': 'T6 mine', 'company_id': self.company.id, 'state': {}})
        self.assertTrue(self._as(self.user_plan).delete_plan(mine))

        theirs = self._as(self.user_other).save_plan({
            'name': 'T6 theirs', 'company_id': self.company.id, 'state': {}})
        with self.assertRaises(AccessError) as caught:
            self._as(self.user_plan).delete_plan(theirs)
        self.assertIn('T6 theirs', str(caught.exception))
        self.assertTrue(self._as(self.user_lead).delete_plan(theirs))

    # -------------------------------------------------------------- T7
    def test_t7_at_most_one_reference_plan_per_company(self):
        """T7."""
        room = self._as(self.user_plan)
        a = room.save_plan({'name': 'T7 a', 'company_id': self.company.id,
                            'state': {}})
        b = room.save_plan({'name': 'T7 b', 'company_id': self.company.id,
                            'state': {}})
        room.set_reference(a)
        room.set_reference(b)
        refs = self.Plan.search([('company_id', '=', self.company.id),
                                 ('is_reference', '=', True)])
        self.assertEqual(len(refs), 1)
        self.assertEqual(refs.id, b)
        room.set_reference(0)
        self.assertFalse(self.Plan.search_count(
            [('company_id', '=', self.company.id), ('is_reference', '=', True)]))

    # -------------------------------------------------------------- T8
    def test_t8_the_room_opens_fast_enough_to_open_twice(self):
        """T8. Cold under 3 s, warm under 800 ms, on the biggest company this
        database has. Both numbers are logged for the phase report."""
        started = time.time()
        cold = self._room(self.user_plan, refresh=True)
        cold_ms = (time.time() - started) * 1000
        started = time.time()
        warm = self._room(self.user_plan)
        warm_ms = (time.time() - started) * 1000
        _logger.info('T8 Decision Room timing on company %s (%s people): '
                     'cold %.0f ms, warm %.0f ms',
                     self.company.id, cold['baseline']['headcount'],
                     cold_ms, warm_ms)
        self.assertTrue(warm['allowed'])
        self.assertLess(cold_ms, 3000, 'cold read took %.0f ms' % cold_ms)
        self.assertLess(warm_ms, 800, 'warm read took %.0f ms' % warm_ms)

    # -------------------------------------------------------------- T10
    def test_t10_the_roles_that_should_already_have_it_do(self):
        """T10. The HR manager plans; the administrator owns the assumptions;
        every Workforce Planning tier carries the room with it (post_init)."""
        room_user = self.env.ref('pb_decision_room.group_decision_user')
        room_lead = self.env.ref('pb_decision_room.group_decision_manager')
        self.assertIn(room_user,
                      self.env.ref('hr.group_hr_manager').implied_ids)
        self.assertIn(room_lead,
                      self.env.ref('base.group_system').implied_ids)
        self.assertIn(room_user, room_lead.implied_ids)
        wfp = self.env.ref('pb_hr_workforce_planning.group_wfp_user',
                           raise_if_not_found=False)
        if wfp:
            self.assertIn(room_user, wfp.implied_ids,
                          'post_init_hook did not link the planning tier')

    # ------------------------------------------------------- extra rails
    def test_a_plan_refuses_a_payload_that_is_not_the_shape_the_room_writes(self):
        with self.assertRaises(ValidationError):
            self.Plan.create({'name': 'bad shape',
                              'company_id': self.company.id,
                              'state': ['not', 'a', 'dict']})

    def test_the_assumptions_saver_is_the_planning_leads_alone(self):
        with self.assertRaises(AccessError):
            self._as(self.user_plan).save_assumptions({'revenue_target': 1000})
        out = self._as(self.user_lead).save_assumptions(
            {'revenue_target': 1234000000, 'demand_growth_pct': 7})
        self.assertEqual(out['revenue_target'], 1234000000)
        self.assertEqual(out['demand_growth_pct'], 7)

    def test_the_room_never_writes_to_an_hr_model(self):
        """The promise on the screen, checked against the source."""
        import os
        import re
        here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        bad = []
        for root, _dirs, files in os.walk(os.path.join(here, 'models')):
            for name in files:
                if not name.endswith('.py'):
                    continue
                with open(os.path.join(root, name), encoding='utf-8') as fh:
                    src = fh.read()
                for hit in re.finditer(
                        r"env\['(hr\.[\w.]+)'\]\s*(?:\.\w+)*\."
                        r"(create|write|unlink)\b", src):
                    bad.append('%s: %s' % (name, hit.group(0)))
        self.assertFalse(bad, 'the room writes to payroll data: %s' % bad)
