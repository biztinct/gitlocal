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

    # =================================================================
    #  WFPLAN P2 — the assumptions a lead can change, and the brief
    # =================================================================

    # ------------------------------------------------------------- T21
    def test_t21_an_upgraded_row_carries_the_new_defaults(self):
        """T21. An assumptions row created before Phase 2 must read the new
        shift fields at their defaults after the upgrade — and the three
        demand shares must be refused unless they describe a whole day."""
        row = self.Assumptions.get_for_company(self.company)
        self.assertEqual(row.shift_evening_pct, 25.0)
        self.assertEqual(row.shift_night_pct, 15.0)
        self.assertEqual(row.evening_uplift_pct, 0.0)
        self.assertEqual(row.demand_day_pct, 60.0)
        self.assertEqual(row.demand_evening_pct, 25.0)
        self.assertEqual(row.demand_night_pct, 15.0)
        self.assertEqual(row.productivity_cost_per_point, 0.0)
        with self.assertRaises(ValidationError) as caught:
            row.write({'demand_night_pct': 20.0})
        message = str(caught.exception)
        self.assertIn('100', message)
        self.assertIn('add up', message)
        self.assertNotIn('constraint', message.lower())
        # 60 + 25 + 15 is still fine, and so is any other whole day.
        row.write({'demand_day_pct': 50.0, 'demand_evening_pct': 30.0,
                   'demand_night_pct': 20.0})
        self.assertEqual(row.demand_day_pct, 50.0)
        with self.assertRaises(ValidationError):
            row.write({'shift_evening_pct': 50.0, 'shift_night_pct': 40.0})

    # ------------------------------------------------------------- T22
    def test_t22_only_the_planning_lead_changes_the_assumptions(self):
        """T22. Refused for a plan-tier user with a sentence that says who to
        ask; written by the lead, recorded in the chatter with the old and the
        new value; and the cached roster is dropped, because which teams earn
        revenue is part of the roster itself."""
        with self.assertRaises(AccessError) as caught:
            self._as(self.user_plan).save_assumptions({'employer_rate_pct': 24})
        said = str(caught.exception)
        self.assertIn('HR or finance lead', said)
        self.assertNotIn('Odoo', said)

        row = self.Assumptions.get_for_company(self.company)
        # WF16. `mail.thread.create` DISCARDS tracking for a record it has
        # just created — so a create is not also reported as twenty-five
        # changes — and the discard lasts the whole transaction. On a real
        # database this row already exists and the discard never happens; in
        # a test it always does, because the row is created inside the very
        # transaction that then changes it. Clearing the marker is what makes
        # this test measure the product rather than that artefact.
        self.env.cr.precommit.data.pop(
            'mail.tracking.pb.decision.assumptions', None)
        before = row.employer_rate_pct
        # A value that is definitely NOT the one already there: writing a
        # field its current value is not a change, and a change is what the
        # chatter records.
        after = 24.0 if abs(before - 24.0) > 0.01 else 25.0
        out = self._as(self.user_lead).save_assumptions(
            {'employer_rate_pct': after})
        self.assertEqual(out['employer_rate_pct'], after)
        # Tracking messages are posted in the cursor's PRE-COMMIT hook, not
        # inside `write()`. In a test, which never commits, they do not exist
        # until that hook is run by hand.
        self.env.flush_all()
        self.env.cr.precommit.run()
        row.invalidate_recordset()
        tracked = row.message_ids.tracking_value_ids
        self.assertTrue(tracked, 'the change was not recorded on the record')
        values = [(t.old_value_float, t.new_value_float) for t in tracked]
        self.assertIn((before, after), values)

        # ... and the cache really is dropped: drop a revenue team and the
        # baseline that comes back must agree.
        room = self._room(self.user_lead)
        earners = [t for t in room['baseline']['teams'] if t['revenue']]
        if earners and earners[0]['department_id']:
            keep = [t['department_id'] for t in room['baseline']['teams']
                    if t['revenue'] and t['department_id']
                    and t['department_id'] != earners[0]['department_id']]
            self._as(self.user_lead).save_assumptions(
                {'revenue_team_ids': keep})
            after = self._room(self.user_lead)
            dropped = [t for t in after['baseline']['teams']
                       if t['department_id'] == earners[0]['department_id']]
            self.assertTrue(dropped)
            self.assertFalse(dropped[0]['revenue'],
                             'the baseline cache was not cleared')

    # ------------------------------------------------------------- T23
    def test_t23_the_editable_form_is_the_model_and_nothing_else(self):
        """T23. The dialog is GENERATED from this list, so a field that is on
        the list and not on the model would draw a box that saves nowhere, and
        one on the model and not the list would be invisible for ever."""
        form = self._room(self.user_lead)['assumptions_form']
        keys = [f['key'] for f in form]
        self.assertEqual(len(keys), len(set(keys)), 'a field appears twice')
        model_fields = self.Assumptions._fields
        for field in form:
            self.assertIn(field['key'], model_fields, field['key'])
            self.assertTrue(field['label'], field['key'])
            self.assertTrue(field['help'], field['key'])
            self.assertIn(field['kind'],
                          ('money', 'pct', 'months', 'int', 'teams', 'rate'))
            self.assertNotIn('Odoo', field['help'])
        # Everything a person could reasonably want to change is offered.
        expected = {
            'revenue_target', 'demand_growth_pct', 'revenue_team_ids',
            'employer_rate_pct', 'employee_rate_pct', 'contribution_cap',
            'allowance_pct', 'bonus_months', 'bonus_month_index',
            'recruit_cost_months', 'severance_months', 'ramp_first_month_pct',
            'attrition_pct_year', 'work_days', 'ot_multiplier',
            'shift_evening_pct', 'shift_night_pct', 'evening_uplift_pct',
            'night_uplift_pct', 'demand_day_pct', 'demand_evening_pct',
            'demand_night_pct', 'other_fixed_monthly', 'other_pct_revenue',
            'productivity_cost_per_point',
        }
        self.assertEqual(set(keys), expected)
        groups = self._room(self.user_lead)['assumptions_groups']
        self.assertEqual(set(f['group'] for f in form) - set(groups), set())

    def test_the_assumption_ranges_are_a_server_rule_and_not_a_suggestion(self):
        room = self._as(self.user_lead)
        with self.assertRaises(UserError) as caught:
            room.save_assumptions({'employer_rate_pct': 900})
        self.assertIn('between', str(caught.exception))
        with self.assertRaises(UserError):
            room.save_assumptions({'revenue_target': -5})
        with self.assertRaises(UserError):
            room.save_assumptions({'work_days': 'lots'})

    # ------------------------------------------------------------- T24
    def _brief(self, **kw):
        payload = {
            'plan_name': 'Board draft',
            'comparison_name': 'Today',
            'currency_code': 'VND',
            'headline_title': 'Twelve more people adds profit.',
            'headline_copy': 'Workforce cost is up for the year.',
            'goals': [{'label': 'Operating margin', 'bound': 'At least',
                       'target': '20.0%', 'actual': '23.4%', 'met': True,
                       'status': 'Met'}],
            'outcome': [{'label': 'Operating profit', 'ref': '1B',
                         'plan': '1.2B'}],
            'bridge': [{'label': 'Revenue delivered', 'reason': 'What was served',
                        'value': '+200M', 'good': True}],
            'bridge_total': '+200M',
            'changes': ['12 more people in Production from March'],
            'inputs': [{'label': 'Overtime per person', 'ref': '0 h a month',
                        'plan': '8 h a month'}],
            'months': [{'name': 'January', 'people': '4,533', 'cost': '90B',
                        'served': '98.0%', 'profit': '12B'}],
            'assumptions': [{'title': 'Who this is about',
                             'copy': '4,533 people in 13 teams.'}],
        }
        payload.update(kw)
        return self._as(self.user_plan).render_brief(payload)

    def test_t24_the_brief_is_one_self_contained_page(self):
        """T24. It is saved to a laptop and mailed on: a brief whose layout
        depends on a server it can no longer reach is not a brief."""
        html = self._brief()
        for forbidden in ('<script', '<link', 'http://', 'https://', 'src=',
                          '@import'):
            self.assertNotIn(forbidden, html,
                             'the brief reaches outside itself: %s' % forbidden)
        self.assertIn('<!doctype html>', html)
        self.assertIn(self.company.display_name, html)
        self.assertIn('Board draft', html)
        self.assertIn('Nothing in payroll', html)
        self.assertIn('Operating margin', html)
        self.assertIn('Who this is about', html)
        self.assertIn('4,533 people in 13 teams.', html)
        self.assertIn('12 more people in Production from March', html)
        self.assertIn('January', html)
        self.assertIn('Overtime per person', html)
        self.assertNotIn('Odoo', html)

    # ------------------------------------------------------------- T25
    def test_t25_the_brief_never_lets_a_name_become_markup(self):
        """T25. A plan called `<b>x</b>` prints those five characters."""
        html = self._brief(plan_name='<b>x</b>',
                           comparison_name='"><script>alert(1)</script>')
        self.assertIn('&lt;b&gt;x&lt;/b&gt;', html)
        self.assertNotIn('<b>x</b>', html)
        self.assertNotIn('<script>alert(1)</script>', html)

    def test_the_brief_is_refused_to_somebody_with_no_room(self):
        with self.assertRaises(AccessError):
            self.Room.with_user(self.user_none).render_brief({})

    def test_the_baseline_that_leaves_this_server_names_nobody(self):
        """The fixture the engine checks use is written from here, so what the
        node checks are timed against is the REAL roster — and the check that
        it carries no person is the same check that writes it."""
        import json
        import os
        room = self._room(self.user_plan, refresh=True)
        baseline = room['baseline']
        blob = json.dumps(baseline)
        self.assertNotIn('employee', blob.lower())
        for team in baseline['teams']:
            self.assertEqual(set(team) - {
                'key', 'name', 'department_id', 'revenue', 'heads',
                'pay_month_avg', 'roles'}, set())
            for role in team['roles']:
                self.assertEqual(set(role) - {
                    'key', 'name', 'job_id', 'heads', 'pay_month_avg',
                    'level'}, set())
        path = os.path.join('/tmp', 'pb_decision_room_baseline.json')
        try:
            with open(path, 'w', encoding='utf-8') as fh:
                json.dump(baseline, fh, indent=1)
            _logger.info('Decision Room: baseline fixture written to %s', path)
        except OSError as e:      # a read-only /tmp is not a test failure
            _logger.info('Decision Room: fixture not written (%s)', e)

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
