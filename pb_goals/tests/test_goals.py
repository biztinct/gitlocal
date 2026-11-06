# -*- coding: utf-8 -*-
"""RIZE W2 B1 — the rails that must not quietly stop working.

The live Chrome run is what proves the pages render; these are the floor.
Every one of them is written against a failure this module could have and that
nothing at runtime would report:

  * a goal sheet that can be agreed with weights adding up to ninety is a year
    where nothing matters most, and the screen would look perfectly normal;
  * a locked goal that still accepts a rewrite is an agreement one side can
    change afterwards, silently;
  * an ownership check that trusts the id in the form is somebody else's goals
    on your page, and nothing anywhere would say so;
  * a reminder key that is not written is four thousand people emailed every
    morning for the rest of the year, with a cheerful count in the log;
  * two adjacent string literals in a JS file blank the ENTIRE backend asset
    bundle for every user in the product, with a clean server log;
  * an icon name that is not in the shared registry draws a plain circle with
    no error at all.

WHY THE FIXTURES ARE NAMED "DEMO". Everything this suite creates is rolled back
with the transaction, but the names are the live convention anyway (ledger rule
9): a fixture copied into a live script keeps the name it was written with, and
a fixture called "RIZE test" is how the customer's name ends up on a screen
somebody is being shown.
"""

import ast
import re

from datetime import date, timedelta

from lxml import etree

from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.modules.module import get_module_path
from odoo.tests import TransactionCase, tagged

_RE_ADJACENT_STRINGS = re.compile(r"""["']\s*\n\s*["']""")
#: The word that may never reach a user-visible string. Comments, xmlids and
#: import lines are stripped before the gate looks (R118) — engineering
#: readers need the real name, and the rule binds STRINGS.
_RE_VENDOR = re.compile(r'\bodoo\b', re.IGNORECASE)


def _path(*parts):
    return get_module_path('pb_goals') + '/' + '/'.join(parts)


def _src(*parts):
    with open(_path(*parts), encoding='utf-8') as fh:
        return fh.read()


class GoalsCase(TransactionCase):
    """One goal year, one employee with a manager, one goal sheet."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Cycle = cls.env['pb.goal.cycle']
        cls.Set = cls.env['pb.goal.set']
        cls.Goal = cls.env['pb.goal']
        cls.Kr = cls.env['pb.goal.kr']
        cls.My = cls.env['pb.my.goals']
        cls.Board = cls.env['pb.goals']

        cls.company = cls.env['res.company'].create({'name': 'DEMO Goals Co'})

        # NO SIGNUP EMAIL. `res.users.create` sends one by default and on this
        # box a queued mail goes out within the second (R47) — the addresses
        # are @example.com, but a test that posts mail is a test that will one
        # day post it somewhere real.
        Users = cls.env['res.users'].with_context(no_reset_password=True)
        cls.boss_user = Users.create({
            'name': 'DEMO Boss',
            'login': 'demo.goals.boss@example.com',
            'email': 'demo.goals.boss@example.com',
            'company_id': cls.company.id,
            'company_ids': [(6, 0, [cls.company.id])],
            'group_ids': [(6, 0, [cls.env.ref('base.group_user').id])],
        })
        cls.staff_user = Users.create({
            'name': 'DEMO Staff',
            'login': 'demo.goals.staff@example.com',
            'email': 'demo.goals.staff@example.com',
            'company_id': cls.company.id,
            'company_ids': [(6, 0, [cls.company.id])],
            'group_ids': [(6, 0, [cls.env.ref('base.group_user').id])],
        })
        cls.stranger_user = Users.create({
            'name': 'DEMO Stranger',
            'login': 'demo.goals.stranger@example.com',
            'email': 'demo.goals.stranger@example.com',
            'company_id': cls.company.id,
            'company_ids': [(6, 0, [cls.company.id])],
            'group_ids': [(6, 0, [cls.env.ref('base.group_user').id])],
        })

        Employee = cls.env['hr.employee']
        cls.boss = Employee.create({
            'name': 'DEMO Boss', 'company_id': cls.company.id,
            'user_id': cls.boss_user.id,
            'work_email': 'demo.goals.boss@example.com'})
        cls.staff = Employee.create({
            'name': 'DEMO Staff', 'company_id': cls.company.id,
            'user_id': cls.staff_user.id, 'parent_id': cls.boss.id,
            'work_email': 'demo.goals.staff@example.com'})
        cls.stranger = Employee.create({
            'name': 'DEMO Stranger', 'company_id': cls.company.id,
            'user_id': cls.stranger_user.id,
            'work_email': 'demo.goals.stranger@example.com'})

        cls.cycle = cls.Cycle.create({
            'name': 'DEMO FY2026',
            'company_id': cls.company.id,
            'date_start': date(2026, 4, 1),
            'date_end': date(2027, 3, 31),
            'mid_year_date': date(2026, 10, 1),
            'submission_days': 14,
        })
        cls.cycle.action_open()

    # ------------------------------------------------------------- helpers
    def _sheet(self, employee=None):
        return self.Set.create({
            'employee_id': (employee or self.staff).id,
            'cycle_id': self.cycle.id,
            'company_id': self.company.id,
            'deadline': date.today() + timedelta(days=14),
        })

    def _goal(self, sheet, title='DEMO Grow the north region', weight=0.0,
              krs=1):
        goal = self.Goal.create({
            'set_id': sheet.id,
            'title': title,
            'description': 'DEMO why it matters and what good looks like.',
            'date_start': date(2026, 4, 1),
            'date_end': date(2027, 3, 31),
            'weight': weight,
            'self_rating': '3',
        })
        for index in range(krs):
            self.Kr.create({
                'goal_id': goal.id,
                'title': 'DEMO new customers %s' % (index + 1),
                'measure': 'customers a month',
                'target': 50.0,
            })
        return goal

    def _lock(self, sheet):
        """Do to the sheet exactly what the engine does when the last rung is
        agreed, and never write `locked_at` by hand.

        `chain_shim._approval_apply` is two lines — write the status, then call
        the after-hook — and those two lines are what this replays. Driving the
        whole published route here would mean minting seats for two approvers
        and would be a test of the ENGINE rather than of this module; the route
        end to end is proved live, and `test_sent_back_is_its_own_state` below
        walks a real rung as the real approver.

        The point being proved is that the CONSEQUENCE of a lock hangs off the
        STATUS (see `_after_approval_transition`), so it is identical whether a
        route drove the sheet there or the record's own ladder did.
        """
        sheet._chain_engine_write('locked')
        sheet._after_approval_transition('locked')
        sheet.invalidate_recordset()
        return sheet


# =========================================================================
#  1. The goal year
# =========================================================================
@tagged('post_install', '-at_install')
class TestCycle(GoalsCase):

    def test_only_one_cycle_may_be_open_at_a_time(self):
        """Two open years is a question nobody can answer."""
        second = self.Cycle.create({
            'name': 'DEMO FY2027', 'company_id': self.company.id,
            'date_start': date(2027, 4, 1), 'date_end': date(2028, 3, 31)})
        with self.assertRaises(UserError) as caught:
            second.action_open()
        # The refusal NAMES the other one — a refusal that does not say which
        # record is in the way is a refusal somebody has to go hunting about.
        self.assertIn('DEMO FY2026', str(caught.exception))

    def test_a_year_has_to_end_after_it_starts(self):
        with self.assertRaises(ValidationError):
            self.Cycle.create({
                'name': 'DEMO Backwards', 'company_id': self.company.id,
                'date_start': date(2027, 4, 1), 'date_end': date(2026, 3, 31)})

    def test_the_half_way_point_falls_inside_the_year(self):
        with self.assertRaises(ValidationError):
            self.cycle.write({'mid_year_date': date(2029, 1, 1)})

    def test_open_for_everyone_says_how_many_before_it_makes_any(self):
        """R54 — a button that writes to a company says the number first."""
        preview = self.Cycle.preview_open_for_everyone(self.cycle.id)
        self.assertTrue(preview['ok'])
        self.assertEqual(preview['todo'], 3)
        self.assertIn('3', preview['sentence'])

    def test_open_for_everyone_is_idempotent(self):
        """Run it again after the new starters arrive: nothing is doubled."""
        first = self.cycle._open_for_everyone()
        self.assertEqual(first['made'], 3)
        second = self.cycle._open_for_everyone()
        self.assertEqual(second['made'], 0)
        self.assertEqual(second['skipped'], 3)
        self.assertEqual(
            self.Set.search_count([('cycle_id', '=', self.cycle.id)]), 3)

    def test_one_sheet_per_person_per_year(self):
        """`_sql_constraints` as a LIST is silently ignored on Odoo 19, so
        this proves the `models.Constraint` form is the one that landed."""
        self._sheet()
        with self.assertRaises(Exception):
            with self.env.cr.savepoint():
                self._sheet()

    def test_open_for_everyone_is_refused_to_somebody_without_the_tier(self):
        with self.assertRaises(UserError):
            self.Cycle.with_user(self.staff_user).open_for_everyone(
                self.cycle.id)


# =========================================================================
#  2. The sheet, the goals and what a lock means
# =========================================================================
@tagged('post_install', '-at_install')
class TestSheet(GoalsCase):

    def test_the_manager_is_computed_from_the_hops_it_is_made_of(self):
        """R138 — a compute that depends on the RECORD is frozen for the life
        of the environment, and a sheet stays addressed to March's manager."""
        sheet = self._sheet()
        self.assertEqual(sheet.manager_user_id, self.boss_user)
        # A FRESH LOGIN, because `hr_employee_user_uniq` means one login has
        # exactly one employee record — reusing another fixture's user is a
        # raw Postgres error rather than a test failure.
        second = self.env['res.users'].with_context(
            no_reset_password=True).create({
                'name': 'DEMO Second Boss',
                'login': 'demo.goals.boss2@example.com',
                'email': 'demo.goals.boss2@example.com',
                'company_id': self.company.id,
                'company_ids': [(6, 0, [self.company.id])],
                'group_ids': [(6, 0, [self.env.ref('base.group_user').id])]})
        new_boss = self.env['hr.employee'].create({
            'name': 'DEMO Second Boss', 'company_id': self.company.id,
            'user_id': second.id})
        self.staff.write({'parent_id': new_boss.id})
        sheet.invalidate_recordset()
        self.assertEqual(sheet.manager_user_id, second)

    def test_weights_and_progress_add_up(self):
        sheet = self._sheet()
        self._goal(sheet, 'DEMO One', 60)
        self._goal(sheet, 'DEMO Two', 40)
        self.assertEqual(sheet.weight_total, 100)
        self.assertEqual(sheet.goal_count, 2)
        self.assertEqual(sheet.kr_count, 2)

    def test_progress_is_weighted_and_falls_back_to_a_plain_average(self):
        """A sheet whose weights are not in yet still has an honest answer,
        and it is the plain average rather than zero."""
        sheet = self._sheet()
        one = self._goal(sheet, 'DEMO One', 0)
        two = self._goal(sheet, 'DEMO Two', 0)
        one.kr_ids.write({'progress': 100})
        two.kr_ids.write({'progress': 0})
        self.assertEqual(sheet.progress, 50.0)
        one.write({'weight': 75})
        two.write({'weight': 25})
        self.assertEqual(sheet.progress, 75.0)

    def test_a_goal_must_end_inside_the_year(self):
        sheet = self._sheet()
        with self.assertRaises(ValidationError) as caught:
            self.Goal.create({
                'set_id': sheet.id, 'title': 'DEMO Outside',
                'description': 'DEMO', 'date_end': date(2030, 1, 1)})
        # The refusal REPEATS THE BOUNDARIES, because a date outside the year
        # is almost always a typo in the year part.
        self.assertIn('2026-04-01', str(caught.exception))

    def test_a_locked_goal_cannot_be_reworded_but_its_numbers_still_move(self):
        sheet = self._sheet()
        goal = self._goal(sheet, 'DEMO One', 100)
        self._lock(sheet)
        self.assertTrue(goal.locked)
        with self.assertRaises(UserError):
            goal.with_user(self.staff_user).write({'title': 'DEMO Changed'})
        # PROGRESS IS NOT A CHANGE OF PLAN.
        goal.kr_ids[0].with_user(self.staff_user).write({'progress': 40})
        self.assertEqual(goal.kr_ids[0].progress, 40)

    def test_a_locked_key_result_cannot_be_re_targeted(self):
        sheet = self._sheet()
        goal = self._goal(sheet, 'DEMO One', 100)
        self._lock(sheet)
        with self.assertRaises(UserError):
            goal.kr_ids[0].with_user(self.staff_user).write({'target': 1})

    def test_every_move_writes_a_history_row(self):
        sheet = self._sheet()
        goal = self._goal(sheet, 'DEMO One', 100)
        kr = goal.kr_ids[0]
        self.Kr.with_user(self.staff_user).move(kr.id, 40, 20, 'DEMO note')
        self.assertEqual(len(kr.history_ids), 1)
        row = kr.history_ids[0]
        self.assertEqual(row.progress, 40)
        self.assertEqual(row.note, 'DEMO note')
        self.assertEqual(row.by_user_id, self.staff_user)
        # WRITING THE SAME VALUE AGAIN IS NOT A MOVE, so the trail does not
        # fill with rows that say nothing happened.
        self.Kr.with_user(self.staff_user).move(kr.id, 40, 20, '')
        self.assertEqual(len(kr.history_ids), 1)

    def test_progress_is_clamped_to_a_figure_out_of_a_hundred(self):
        sheet = self._sheet()
        goal = self._goal(sheet, 'DEMO One', 100)
        result = self.Kr.move(goal.kr_ids[0].id, 500)
        self.assertEqual(result['progress'], 100)
        with self.assertRaises(ValidationError):
            goal.kr_ids[0].sudo().write({'progress': 140})

    def test_a_weight_outside_nought_to_a_hundred_is_refused(self):
        sheet = self._sheet()
        with self.assertRaises(ValidationError):
            self._goal(sheet, 'DEMO One', 140)


# =========================================================================
#  3. The employee's own page
# =========================================================================
@tagged('post_install', '-at_install')
class TestMyGoals(GoalsCase):

    def test_the_page_says_so_when_nothing_is_open(self):
        data = self.My.with_user(self.staff_user).home()
        self.assertTrue(data['ok'])
        self.assertTrue(data['empty'])
        self.assertTrue(data['why'])

    def test_the_whole_journey_on_the_page(self):
        sheet = self._sheet()
        My = self.My.with_user(self.staff_user)
        My.add_goal({'title': 'DEMO Grow the north region',
                     'description': 'DEMO why it matters.',
                     'date_end': '2027-03-31', 'self_rating': '3'})
        My.add_goal({'title': 'DEMO Cut the time to answer',
                     'description': 'DEMO why it matters.',
                     'date_end': '2027-03-31', 'self_rating': '4'})
        data = My.home()
        self.assertEqual(len(data['goals']), 2)
        # A GOAL WITH NO KEY RESULT IS A WISH: the button is off and the page
        # says why, before anybody presses it.
        self.assertFalse(data['ready']['can'])
        self.assertIn('key result', data['ready']['why'])
        for goal in data['goals']:
            My.add_kr(goal['id'], {'title': 'DEMO customers', 'target': 50})
        data = My.home()
        self.assertTrue(data['ready']['can'])
        My.submit()
        sheet.invalidate_recordset()
        self.assertEqual(sheet.state, 'submitted')

    def test_a_goal_needs_a_name_a_reason_and_a_date(self):
        self._sheet()
        My = self.My.with_user(self.staff_user)
        for bad in ({'description': 'DEMO', 'date_end': '2027-03-31'},
                    {'title': 'DEMO', 'date_end': '2027-03-31'},
                    {'title': 'DEMO', 'description': 'DEMO'}):
            with self.assertRaises(UserError):
                My.add_goal(bad)

    def test_somebody_elses_goal_is_not_reachable_from_the_page(self):
        """The form carries an id and the id is checked against the caller's
        own sheet — a crafted request is not a way in."""
        mine = self._sheet()
        theirs = self._sheet(self.stranger)
        self._goal(mine, 'DEMO Mine', 100)
        other_goal = self._goal(theirs, 'DEMO Theirs', 100)
        My = self.My.with_user(self.staff_user)
        with self.assertRaises(UserError):
            My.edit_goal(other_goal.id, {'title': 'DEMO Hijacked'})
        with self.assertRaises(UserError):
            My.delete_goal(other_goal.id)
        with self.assertRaises(UserError):
            My.move_kr(other_goal.kr_ids[0].id, 90)

    def test_a_sent_in_sheet_cannot_be_edited(self):
        sheet = self._sheet()
        goal = self._goal(sheet, 'DEMO One', 0)
        sheet.action_goals_submit()
        My = self.My.with_user(self.staff_user)
        with self.assertRaises(UserError):
            My.edit_goal(goal.id, {'title': 'DEMO Changed'})
        with self.assertRaises(UserError):
            My.add_goal({'title': 'DEMO Another', 'description': 'DEMO',
                         'date_end': '2027-03-31'})

    def test_a_template_is_copied_in_and_not_linked(self):
        """A template edited in March must not reword goals agreed in
        January, so using one COPIES it and only a pointer survives."""
        template = self.env['pb.goal.template'].create({
            'name': 'DEMO Grow a region',
            'title': 'DEMO Grow the north region',
            'description': 'DEMO what good looks like.',
            'kr_titles': 'DEMO new customers\nDEMO revenue\n\n',
            'company_id': self.company.id,
        })
        self._sheet()
        My = self.My.with_user(self.staff_user)
        result = My.use_template(template.id)
        goal = self.Goal.browse(result['goal_id'])
        self.assertEqual(goal.title, 'DEMO Grow the north region')
        self.assertEqual(len(goal.kr_ids), 2)      # the blank line is not one
        self.assertEqual(goal.template_id, template)
        template.write({'title': 'DEMO Something else'})
        self.assertEqual(goal.title, 'DEMO Grow the north region')

    def test_a_template_is_offered_by_job_and_by_department(self):
        wrong_job = self.env['hr.job'].create({'name': 'DEMO Other job'})
        self.env['pb.goal.template'].create({
            'name': 'DEMO Only that job', 'title': 'DEMO', 'description': 'D',
            'job_ids': [(6, 0, [wrong_job.id])],
            'company_id': self.company.id})
        everybody = self.env['pb.goal.template'].create({
            'name': 'DEMO Everybody', 'title': 'DEMO', 'description': 'D',
            'company_id': self.company.id})
        offered = self.env['pb.goal.template'].for_employee(self.staff.id)
        self.assertIn(everybody, offered)
        self.assertEqual(len(offered), 1)

    def test_the_page_stays_usable_after_the_lock(self):
        sheet = self._sheet()
        goal = self._goal(sheet, 'DEMO One', 100)
        self._lock(sheet)
        My = self.My.with_user(self.staff_user)
        data = My.home()
        self.assertTrue(data['locked'])
        self.assertFalse(data['editable'])
        My.move_kr(goal.kr_ids[0].id, 40, 20, 'DEMO on track')
        self.assertEqual(goal.kr_ids[0].progress, 40)


# =========================================================================
#  4. The route, the weights and the lock
# =========================================================================
@tagged('post_install', '-at_install')
class TestApproval(GoalsCase):

    def test_the_route_is_registered_with_no_date_field(self):
        """R192 — a `date_field` decides WHO IS ASKED, not just when. A goal
        sheet's own dates are its deadline and its year, and naming either
        would ask who held the HR seat back then."""
        from odoo.addons.biz_approval_workflow.models.chain_shim import (
            CHAIN_PROCESS_KEYS)
        spec = CHAIN_PROCESS_KEYS.get('pb.goal.set')
        self.assertTrue(spec)
        self.assertEqual(spec['process_key'], 'goal_set')
        self.assertIsNone(spec['date_field'])
        self.assertEqual(spec['submit_state'], 'submitted')
        self.assertEqual(spec['driven'], ('manager_ok', 'locked'))
        self.assertEqual(spec['reverse_to'], ('returned',))

    def test_the_weights_rule_refuses_with_the_arithmetic_in_it(self):
        sheet = self._sheet()
        self._goal(sheet, 'DEMO One', 60)
        self._goal(sheet, 'DEMO Two', 30)
        with self.assertRaises(UserError) as caught:
            sheet._require_weights()
        message = str(caught.exception)
        self.assertIn('90', message)
        self.assertIn('100', message)

    def test_the_pre_decision_hook_answers_for_the_manager_rung(self):
        """The engine calls `_approval_before_approve` before it records
        anything, which is the only place a rung can actually be refused:
        `_approval_validate` is the submit check, and `_approval_advance`
        runs AFTER the decision and has its exceptions swallowed."""
        sheet = self._sheet()
        self._goal(sheet, 'DEMO One', 60)
        self._goal(sheet, 'DEMO Two', 30)
        sheet.write({'state': 'submitted'})
        with self.assertRaises(UserError):
            sheet._approval_before_approve(None, 'mgr')
        sheet.goal_ids[1].write({'weight': 40})
        sheet.invalidate_recordset(['weight_total'])
        self.assertTrue(sheet._approval_before_approve(None, 'mgr'))

    def test_the_engine_asks_the_record_before_it_approves(self):
        """The seam itself, and that it is harmless to everybody else."""
        engine = self.env['biz.approval.engine']
        self.assertTrue(hasattr(engine, '_pb_goals_precondition'))
        # A record with no hook at all is let straight through.
        self.assertTrue(engine._pb_goals_precondition(0, 'mgr'))

    def test_the_lock_writes_who_and_when_and_freezes_the_goals(self):
        sheet = self._sheet()
        goal = self._goal(sheet, 'DEMO One', 100)
        sheet._do_lock(by_user=self.boss_user)
        self.assertTrue(sheet.locked_at)
        self.assertEqual(sheet.locked_by_id, self.boss_user)
        self.assertTrue(goal.locked)
        # Locking twice is locking once.
        stamp = sheet.locked_at
        sheet._do_lock(by_user=self.staff_user)
        self.assertEqual(sheet.locked_at, stamp)
        self.assertEqual(sheet.locked_by_id, self.boss_user)

    def test_sent_back_is_its_own_state_with_the_note_on_it(self):
        """`returned` and `draft` are different rows on a board and the
        difference is the only useful thing on it."""
        sheet = self._sheet()
        self._goal(sheet, 'DEMO One', 100)
        sheet.action_goals_submit()
        # AS THE REAL APPROVER, which is the whole point: with a route
        # published the press becomes a decision on a live rung, and the
        # engine refuses anybody the route did not ask.
        sheet.with_user(self.boss_user).action_goals_send_back(
            'DEMO please add a customer number')
        sheet.invalidate_recordset()
        self.assertEqual(sheet.state, 'returned')
        self.assertIn('customer number', sheet.return_note or '')
        data = self.My.with_user(self.staff_user).home()
        self.assertIn('customer number', data['return_note'])
        self.assertTrue(data['editable'])

    def test_the_revision_stamp_is_the_goals_and_never_the_weights(self):
        """AM32 — a stamp over anything an APPROVER is meant to change on the
        way through refuses a perfectly good approval. Setting the weights is
        the manager's whole job on their own rung, so a stamp over them means
        the HR lead's press is recorded and the sheet never moves, with the
        reason only inside the request's `block_reason`. Found live."""
        sheet = self._sheet()
        goal = self._goal(sheet, 'DEMO One', 0)
        before = sheet._chain_revision_values()
        goal.kr_ids[0].write({'progress': 40})
        goal.write({'weight': 100})
        sheet.invalidate_recordset()
        self.assertEqual(before, sheet._chain_revision_values())
        goal.write({'title': 'DEMO Reworded'})
        self.assertNotEqual(before, sheet._chain_revision_values())

    def test_send_it_back_works_when_the_route_has_already_closed(self):
        """THE ADVICE THE ENGINE GIVES HAS TO WORK.

        Reword a goal while the sheet is waiting on the HR lead and the engine
        correctly refuses to carry out an approval that was given to a
        different sheet — "Send it back and ask for it again" — and closes the
        request. Before this the record sat at "Waiting on the HR lead" with no
        live request behind it, and that very button answered *"This has not
        been sent in for approval, so there is nothing to decide yet."* Found
        live.
        """
        sheet = self._sheet()
        self._goal(sheet, 'DEMO One', 100)
        # No request at all is the same shape as a request that has closed.
        sheet.write({'state': 'manager_ok'})
        sheet.action_goals_send_back('DEMO the wording changed')
        self.assertEqual(sheet.state, 'returned')
        self.assertIn('wording', sheet.return_note or '')

    def test_the_manager_may_not_reweigh_after_they_have_agreed_it(self):
        """Otherwise the HR lead agrees a split nobody signed off."""
        sheet = self._sheet()
        self._goal(sheet, 'DEMO One', 100)
        sheet.write({'state': 'submitted'})
        self.assertTrue(
            self.Board.with_user(self.boss_user)._may_weight(sheet))
        sheet.write({'state': 'manager_ok'})
        self.assertFalse(
            self.Board.with_user(self.boss_user)._may_weight(sheet))

    def test_the_facts_read_as_the_system(self):
        """AM40 — the maker is the employee, who holds no goals permission."""
        sheet = self._sheet()
        self._goal(sheet, 'DEMO One', 100)
        facts = sheet.with_user(self.staff_user)._chain_facts()
        self.assertEqual(facts['weight_total']['value'], 100.0)
        self.assertTrue(facts['weights_add_up']['value'])

    def test_the_catalogue_row_this_module_owns_is_shipped(self):
        """WITHOUT IT NOTHING VISIBLY BREAKS, which is exactly the problem.
        `Seed.lay` refuses with one INFO line, the install reports success,
        and a goal sheet sent in never reaches anybody's inbox. Found live on
        the first install of this module."""
        process = self.env.ref('pb_goals.process_goal_set')
        self.assertEqual(process.key, 'goal_set')
        self.assertEqual(process.model_name, 'pb.goal.set')

    def test_the_route_heals_itself_the_next_morning(self):
        """The third leg on "every database ends up with a route": the hook
        covers a fresh install, a migration covers an upgrade, and this covers
        the install where the catalogue row had not loaded yet."""
        laid = self.env['pb.goals.automation']._ensure_route()
        self.assertIsNot(laid, False)
        workflow = self.env['biz.approval.workflow'].sudo().search(
            [('process_id.key', '=', 'goal_set'),
             ('company_id', '=', self.company.id)], limit=1)
        self.assertTrue(workflow, 'the goal-sheet route was not laid')

    def test_the_route_carries_the_two_sla_dials(self):
        from odoo.addons.pb_goals.models.goal_set_approval import goals_route
        self.env['ir.config_parameter'].sudo().set_param(
            'pb_goals.sla_days', '7')
        self.env['ir.config_parameter'].sudo().set_param(
            'pb_goals.escalate_days', '4')
        definition = goals_route(self.env)
        self.assertEqual(definition['safeguards']['due']['days'], 7)
        self.assertEqual(
            definition['safeguards']['late']['escalate_days'], 4)
        self.assertEqual(len(definition['steps']), 2)
        self.assertEqual(definition['steps'][0]['who']['mode'], 'manager')
        self.assertEqual(definition['steps'][1]['who']['role'], 'hr_lead')

    def test_the_engine_write_runs_as_the_system(self):
        """R132 — the middle of a route is written AS THE APPROVER, who may
        hold no permission on this model at all. Without the sudo the rule
        refuses, the engine swallows it, and the record sits one rung
        behind for ever with one line in the server log."""
        source = _src('models', 'goal_set_approval.py')
        self.assertIn('def _chain_engine_write', source)
        # The whole METHOD, never a slice of it: the first six hundred
        # characters after the `def` are the docstring that explains why the
        # sudo is there, which is not the same as the sudo being there.
        body = source.split('def _chain_engine_write')[1].split('\n    def ')[0]
        self.assertIn('self.sudo()', body)


# =========================================================================
#  5. Who may see what
# =========================================================================
@tagged('post_install', '-at_install')
class TestVisibility(GoalsCase):

    def test_an_employee_sees_their_own_and_nobody_elses(self):
        mine = self._sheet()
        theirs = self._sheet(self.stranger)
        seen = self.Set.with_user(self.staff_user).search([])
        self.assertIn(mine, seen)
        self.assertNotIn(theirs, seen)

    def test_a_manager_sees_their_teams(self):
        mine = self._sheet()
        theirs = self._sheet(self.stranger)
        seen = self.Set.with_user(self.boss_user).search([])
        self.assertIn(mine, seen)
        self.assertNotIn(theirs, seen)

    def test_the_hr_tier_sees_them_all(self):
        """SHIP THE PAIR (R60): the wide rule beside the narrow one, or
        anybody holding both groups is silently narrowed to the narrow one."""
        mine = self._sheet()
        theirs = self._sheet(self.stranger)
        hr = self.staff_user.sudo()
        hr.write({'group_ids': [(4, self.env.ref(
            'pb_goals.group_goals_manager').id)]})
        seen = self.Set.with_user(hr).search([])
        self.assertIn(mine, seen)
        self.assertIn(theirs, seen)

    def test_the_weights_are_not_the_employees_word(self):
        """A record rule is a domain and cannot say "this field but not that
        one", so the guard is on the facade door."""
        sheet = self._sheet()
        self._goal(sheet, 'DEMO One', 0)
        with self.assertRaises(UserError):
            self.Board.with_user(self.staff_user).set_weights(
                sheet.id, {sheet.goal_ids[0].id: 100})

    def test_the_manager_may_weigh_a_sheet_that_is_with_them(self):
        sheet = self._sheet()
        goal = self._goal(sheet, 'DEMO One', 0)
        sheet.write({'state': 'submitted'})
        result = self.Board.with_user(self.boss_user).set_weights(
            sheet.id, {goal.id: 100})
        self.assertTrue(result['weights_ok'])
        self.assertEqual(goal.weight, 100)

    def test_a_locked_sheet_refuses_a_new_weight(self):
        sheet = self._sheet()
        goal = self._goal(sheet, 'DEMO One', 100)
        self._lock(sheet)
        with self.assertRaises(UserError):
            self.Board.set_weights(sheet.id, {goal.id: 50})

    def test_sending_back_with_no_note_is_refused(self):
        sheet = self._sheet()
        self._goal(sheet, 'DEMO One', 100)
        sheet.write({'state': 'submitted'})
        with self.assertRaises(UserError):
            self.Board.with_user(self.boss_user).send_back(sheet.id, '   ')


# =========================================================================
#  6. The chasing, and the kick-off
# =========================================================================
@tagged('post_install', '-at_install')
class TestAutomation(GoalsCase):

    def test_the_nudges_land_on_the_right_days_and_only_once(self):
        Auto = self.env['pb.goals.automation']
        today = date.today()
        sheet = self._sheet()
        for offset, expected in ((3, 'd3'), (1, 'd1'), (0, 'd0'),
                                 (-3, 'late-3'), (-6, 'late-6')):
            sheet.write({'deadline': today + timedelta(days=offset),
                         'reminder_log': ''})
            due = dict((row[0].id, row[1]) for row in Auto._due_reminders())
            self.assertEqual(due.get(sheet.id), expected,
                             'offset %s should owe %s' % (offset, expected))
        # A day that owes nothing owes nothing.
        sheet.write({'deadline': today + timedelta(days=2),
                     'reminder_log': ''})
        self.assertNotIn(
            sheet.id, [row[0].id for row in Auto._due_reminders()])

    def test_a_nudge_that_has_been_sent_is_not_sent_again(self):
        Auto = self.env['pb.goals.automation']
        sheet = self._sheet()
        sheet.write({'deadline': date.today(), 'reminder_log': ''})
        self.assertTrue([r for r in Auto._due_reminders()
                         if r[0].id == sheet.id])
        sheet._nudge('d0', 'd0')
        self.assertFalse([r for r in Auto._due_reminders()
                          if r[0].id == sheet.id])

    def test_a_goal_email_never_comes_from_the_person_who_pressed_the_button(self):
        """Found live: company 5 carries no email at all, so every goal email
        fell through to the template's `user.email_formatted` and "Your goals
        have come back" arrived FROM the manager's personal address."""
        sheet = self._sheet()
        icp = self.env['ir.config_parameter'].sudo()
        icp.set_param('mail.default.from', 'people@example.com')
        self.company.write({'email': False})
        self.company.partner_id.write({'email': False})
        self.assertEqual(sheet.with_user(self.boss_user)._sender(),
                         'people@example.com')
        icp.set_param('pb_goals.hr_sender', 'goals@example.com')
        self.assertEqual(sheet._sender(), 'goals@example.com')

    def test_a_person_with_no_address_stops_owing_a_nudge(self):
        """Otherwise they are "due" every single morning for the rest of the
        year and the job's honest count becomes a number nobody can read."""
        sheet = self._sheet()
        sheet.employee_id.sudo().write({'work_email': False})
        sheet.employee_id.sudo().user_id.write({'email': False})
        sheet.write({'deadline': date.today(), 'reminder_log': ''})
        self.assertFalse(sheet._nudge('d0', 'd0'))
        self.assertTrue(sheet._already_nudged('d0'))

    def test_off_is_a_real_state_and_the_job_says_what_it_would_have_done(self):
        """R54 — a switch that is off and does not SAY so is reported as
        broken."""
        self.env['ir.config_parameter'].sudo().set_param(
            'pb_goals.reminders', '0')
        sheet = self._sheet()
        sheet.write({'deadline': date.today(), 'reminder_log': ''})
        result = self.env['pb.goals.automation']._cron_daily()
        self.assertTrue(result['off'])
        self.assertEqual(result['sent'], 0)
        self.assertGreaterEqual(result['would_have'], 1)

    def test_a_locked_sheet_is_never_chased(self):
        sheet = self._sheet()
        sheet.write({'deadline': date.today() - timedelta(days=3)})
        self._goal(sheet, 'DEMO One', 100)
        sheet.write({'state': 'locked'})
        self.assertFalse([r for r in
                          self.env['pb.goals.automation']._due_reminders()
                          if r[0].id == sheet.id])

    def test_the_kick_off_handler_is_registered_under_its_key(self):
        handlers = self.env['pb.journey.task']._automation_handlers()
        self.assertEqual(handlers.get('goals_kickoff'), '_auto_goals_kickoff')

    def test_the_kick_off_step_is_on_the_joining_checklist(self):
        step = self.env.ref('pb_goals.step_rize_goals')
        self.assertEqual(step.automation_key, 'goals_kickoff')
        self.assertEqual(step.anchor, 'doj')
        self.assertEqual(step.offset_days, 1)
        # A FREE SEQUENCE, and it stays free: E2 took 65 and the shipped
        # checklist uses 10-90 in tens.
        template = self.env.ref(
            'pb_onboarding.journey_template_rize_onboarding')
        others = template.step_ids.filtered(lambda s: s.id != step.id)
        self.assertNotIn(step.sequence, others.mapped('sequence'))


# =========================================================================
#  7. The board
# =========================================================================
@tagged('post_install', '-at_install')
class TestBoard(GoalsCase):

    def test_the_board_ranks_the_problem_first(self):
        """R113/R50 — never by the spelling of the status, which is
        alphabetical order pretending to be lifecycle order."""
        locked = self._sheet()
        self._goal(locked, 'DEMO One', 100)
        locked.write({'state': 'locked'})
        back = self._sheet(self.stranger)
        back.write({'state': 'returned'})
        data = self.Board.get_board({'cycle_id': self.cycle.id})
        self.assertTrue(data['allowed'])
        self.assertEqual(data['rows'][0]['state'], 'returned')
        self.assertEqual(data['rows'][-1]['state'], 'locked')

    def test_the_board_opens_on_the_year_people_are_in(self):
        """Found live: next year's sheet had been set up ready to open, it
        sorts first by start date, and the board opened on it — empty, for
        everybody, over a database with eight goal sheets in it. "Newest
        first" is right for the strip and wrong for the default."""
        later = self.Cycle.create({
            'name': 'DEMO FY2027 (being set up)', 'company_id': self.company.id,
            'date_start': date(2027, 4, 1), 'date_end': date(2028, 3, 31)})
        sheet = self._sheet()
        self._goal(sheet, 'DEMO One', 100)
        # SCOPED TO THIS FIXTURE'S OWN COMPANY. The board reads every goal
        # year the SESSION can see, and the live database this suite runs on
        # has its own open year in another company.
        data = self.Board.with_context(
            allowed_company_ids=[self.company.id]).get_board({})
        self.assertEqual(data['cycle_id'], self.cycle.id)
        self.assertEqual(data['cycles'][0]['id'], self.cycle.id)
        self.assertIn(later.id, [c['id'] for c in data['cycles']])
        self.assertEqual(len(data['rows']), 1)

    def test_the_scope_sentence_is_true_of_the_reader(self):
        """"Your team's goals" over a board holding only their own is a screen
        telling somebody they manage people they do not."""
        self._sheet()
        self.assertEqual(self.Board.with_user(self.boss_user)._scope_sentence(),
                         "Your team's goals, and your own.")
        self.assertEqual(
            self.Board.with_user(self.staff_user)._scope_sentence(),
            "Your own goals.")

    def test_the_headline_does_the_arithmetic(self):
        sheet = self._sheet()
        self._goal(sheet, 'DEMO One', 100)
        sheet.write({'state': 'locked'})
        data = self.Board.get_board({'cycle_id': self.cycle.id})
        self.assertIn('1 of 1', data['headline'])

    def test_the_empty_state_teaches(self):
        data = self.Board.get_board({'cycle_id': self.cycle.id})
        self.assertIn('yet', data['headline'])

    def test_the_search_box_is_accent_blind(self):
        """R78 — Postgres on this box has no `unaccent`, and most people on
        this database have an accent in their name."""
        accented = self.env['hr.employee'].create({
            'name': 'Bùi Hữu Dũng', 'company_id': self.company.id})
        self._sheet(accented)
        data = self.Board.get_board({'cycle_id': self.cycle.id, 'q': 'bui huu'})
        self.assertEqual(len(data['rows']), 1)

    def test_the_drawer_reads_the_whole_sheet(self):
        sheet = self._sheet()
        goal = self._goal(sheet, 'DEMO One', 100)
        self.Kr.move(goal.kr_ids[0].id, 40, 20, 'DEMO note')
        drawer = self.Board.get_set(sheet.id)
        self.assertTrue(drawer['ok'])
        self.assertEqual(len(drawer['goals']), 1)
        self.assertEqual(len(drawer['goals'][0]['krs']), 1)
        self.assertEqual(len(drawer['history']), 1)

    def test_the_drawer_refuses_a_sheet_the_reader_cannot_see(self):
        theirs = self._sheet(self.stranger)
        drawer = self.Board.with_user(self.staff_user).get_set(theirs.id)
        self.assertFalse(drawer['ok'])

    def test_a_record_argument_survives_the_wire(self):
        """R43/R52 — a recordset arrives over JSON-RPC as a plain integer, and
        an integer walks straight past `if not record`."""
        sheet = self._sheet()
        self.assertTrue(self.Board.get_set(sheet.id)['ok'])
        self.assertTrue(self.Board.get_set(str(sheet.id))['ok'])


# =========================================================================
#  8. The gates — the things nothing at runtime would report
# =========================================================================
@tagged('post_install', '-at_install')
class TestGates(GoalsCase):

    # EVERY FILE THIS MODULE SHIPS, AND THE LIST IS THE GATE (R146). A gate
    # that names half the files checks half the files, and the half it misses
    # is the half that was written last — which is exactly how a board shipped
    # against an icon the registry did not have and drew a blank circle for
    # two phases with nobody reporting it. B2's files are in these lists for
    # that reason and any later phase adds its own here in the same change.
    _JS = ('static/src/js/goals_board.js', 'static/src/js/goals_palette.js',
           'static/src/js/goals_numbers.js', 'static/src/js/goals_home.js')
    _PY = ('models/goals_common.py', 'models/cycle.py', 'models/goal_set.py',
           'models/goal.py', 'models/kr.py', 'models/template.py',
           'models/goal_set_approval.py', 'models/approval_engine_ext.py',
           'models/journey_ext.py', 'models/automation.py',
           'models/pb_goals.py', 'models/pb_my_goals.py',
           'models/checkin.py', 'models/review.py', 'models/scoring.py',
           'models/change.py', 'models/change_approval.py',
           'models/close.py', 'models/analytics.py',
           'models/pb_goals_year.py', 'models/pb_goals_home.py',
           'models/pb_my_goals_year.py',
           'controllers/portal.py', 'hooks.py', '__manifest__.py')
    _XML = ('views/goal_views.xml', 'views/goal_year_views.xml',
            'views/portal_templates.xml', 'views/portal_templates_b2.xml',
            'data/mail_template_data.xml', 'data/mail_template_b2.xml',
            'data/ir_cron.xml', 'data/approval_process.xml',
            'data/goal_band_data.xml',
            'data/journey_step.xml', 'security/pb_goals_security.xml',
            'security/pb_goals_rules.xml',
            'security/pb_goals_rules_b2.xml',
            'static/src/xml/goals_board.xml',
            'static/src/xml/goals_year.xml',
            'static/src/xml/goals_numbers.xml',
            'static/src/xml/goals_home.xml')
    #: The OWL templates alone — the three gates below are about the compiled
    #: template scope and not about XML in general.
    _OWL = ('static/src/xml/goals_board.xml',
            'static/src/xml/goals_year.xml',
            'static/src/xml/goals_numbers.xml',
            'static/src/xml/goals_home.xml')
    _SCSS = ('static/src/scss/goals.scss',
             'static/src/scss/portal_goals.scss')

    # ------------------------------------------------------------ the word
    def test_the_vendor_name_never_reaches_a_user_visible_string(self):
        """R118 — the gate strips COMMENTS before it greps. The rule binds
        user-visible STRINGS; an engineering comment must be able to say the
        real name, and the first version of this test failed on the very
        sentence that stops the next contributor reintroducing a bug."""
        for name in self._PY:
            tree = ast.parse(_src(*name.split('/')))
            # A DOCSTRING IS A COMMENT THAT HAPPENS TO BE A STRING, so it is
            # collected by identity and taken out rather than guessed at by
            # length — the length test would fail the day somebody writes a
            # short docstring naming the framework, which they should be able
            # to do.
            docs = set()
            for node in ast.walk(tree):
                if isinstance(node, (ast.Module, ast.ClassDef,
                                     ast.FunctionDef, ast.AsyncFunctionDef)):
                    body = getattr(node, 'body', None) or []
                    if body and isinstance(body[0], ast.Expr) \
                            and isinstance(body[0].value, ast.Constant) \
                            and isinstance(body[0].value.value, str):
                        docs.add(id(body[0].value))
            for node in ast.walk(tree):
                if not isinstance(node, ast.Constant) \
                        or not isinstance(node.value, str) \
                        or id(node) in docs:
                    continue
                if _RE_VENDOR.search(node.value) and \
                        'odoo.addons' not in node.value and \
                        'odoo/' not in node.value:
                    self.fail('%s: a string says the vendor name: %r'
                              % (name, node.value[:90]))

    def test_no_emoji_anywhere(self):
        for name in self._PY + self._JS + self._XML:
            for char in _src(*name.split('/')):
                self.assertLess(
                    ord(char), 0x1F000,
                    '%s carries an emoji, and this product uses Lucide' % name)

    # ------------------------------------------------------------ the icons
    def test_every_icon_name_is_in_the_shared_registry(self):
        """R146/R147 — the gate reads the object-literal maps as well as the
        `ic()` calls, and it reads them against the INSTALLED copy of
        `pb_import_kit`, because a local check passes while the live screen
        draws blank circles."""
        registry_src = open(
            get_module_path('pb_import_kit')
            + '/static/src/js/import_icons.js', encoding='utf-8').read()
        known = set(re.findall(r'^\s{4}([A-Za-z][A-Za-z0-9]*)\s*:',
                               registry_src, re.M))
        self.assertIn('target', known)          # the registry really parsed
        used = set()
        for name in self._JS + self._OWL:
            source = _src(*name.split('/'))
            used |= set(re.findall(r"""\bic\(\s*['"]([A-Za-z0-9]+)['"]""",
                                   source))
            # ... and every `*_ICON = { key: "name" }` map beside them.
            for block in re.findall(r'_ICON\s*=\s*\{(.*?)\}', source,
                                    re.S):
                used |= set(re.findall(r""":\s*["']([A-Za-z0-9]+)["']""",
                                       block))
        self.assertTrue(used)
        missing = sorted(used - known)
        self.assertFalse(
            missing,
            'these icons are not in the shared registry and will draw a '
            'plain circle with no error: %s' % ', '.join(missing))

    # -------------------------------------------------------------- the JS
    def test_no_adjacent_string_literals_in_the_js(self):
        """R2 — a Python habit (`"one " "two"`) is a SyntaxError that kills
        the ENTIRE backend asset bundle: every OWL surface in the product
        goes blank, and the only clue is one console line."""
        for name in self._JS:
            self.assertFalse(
                _RE_ADJACENT_STRINGS.search(_src(*name.split('/'))),
                '%s has two adjacent string literals' % name)

    def test_the_owl_template_calls_no_javascript_global(self):
        """A compiled OWL expression runs in a RESTRICTED SCOPE. `filter(
        Boolean)` is ordinary JavaScript and dies in a template with
        "undefined is not a function", the whole component fails to render,
        and the real cause sits two levels down an OwlError's `cause`. Found
        live: the drawer simply never opened, with nothing on the screen.
        Anything a template needs that is not a property or a method of the
        component belongs in the component."""
        for template in self._OWL:
            # R118 — THE GATE STRIPS COMMENTS BEFORE IT GREPS, and this is the
            # third time on this programme that it has had to learn it. The
            # rule binds what the template COMPILES; the comment beside it is
            # the sentence that stops the next contributor reintroducing the
            # bug, and it has to be able to name the thing it is warning
            # about. The first version of this gate failed on its own warning.
            source = re.sub(r'<!--.*?-->', '', _src(*template.split('/')),
                            flags=re.S)
            for name in ('Boolean', 'Object.', 'JSON.', 'Number(', 'String(',
                         'parseInt', 'parseFloat', 'Array.'):
                self.assertNotIn(
                    name, source,
                    '%s: `%s` is a JavaScript global and an OWL template '
                    'cannot see it' % (template, name))

    def test_no_reserved_loop_variable_in_the_owl_template(self):
        """R1 — OWL reserves lt/gt/lte/gte as OPERATORS, and `t-as="lt"`
        compiles into a bare `<` that kills the whole template."""
        for template in self._OWL:
            source = _src(*template.split('/'))
            for bad in ('lt', 'gt', 'lte', 'gte', 'and', 'or', 'not', 'in'):
                self.assertNotIn('t-as="%s"' % bad, source,
                                 '%s: `%s` is an OWL operator and cannot be '
                                 'a loop variable' % (template, bad))

    # ------------------------------------------------------------- the XML
    def test_every_xml_file_parses(self):
        for name in self._XML:
            etree.parse(_path(*name.split('/')))

    def test_no_section_comment_is_ruled_with_hyphens(self):
        """R35 — a doubled hyphen INSIDE an XML comment is a parse error that
        takes the whole file with it. The gate looks inside the comments and
        nowhere else: `pbgl-chip--bad` is a class name and is fine."""
        for name in self._XML:
            for body in re.findall(r'<!--(.*?)-->', _src(*name.split('/')),
                                   re.S):
                self.assertNotIn(
                    '--', body,
                    '%s: a comment ruled with hyphens is a parse error — '
                    'rule section comments with "=" (R35)' % name)

    def test_every_nolabel_field_in_a_group_carries_a_colspan(self):
        """R128 — an inner `<group>` is a two-column grid and a label-less
        field takes the NARROW cell, so a description box comes out 150px
        wide with a thousand pixels of empty row beside it."""
        for name in ('views/goal_views.xml',
                     'views/goal_year_views.xml'):
            tree = etree.parse(_path(*name.split('/')))
            for field in tree.iter('field'):
                if field.get('nolabel') != '1':
                    continue
                parent = field.getparent()
                if parent is not None and parent.tag == 'group':
                    self.assertTrue(
                        field.get('colspan'),
                        '%s: <field name="%s" nolabel="1"> inside a <group> '
                        'needs colspan="2"' % (name, field.get('name')))


    def test_no_inherited_view_selects_by_string(self):
        """VIEW INHERITANCE MAY NOT SELECT BY `string` on this build, and it
        is not a warning: *"View inheritance may not use attribute 'string' as
        a selector"* ABORTS THE WHOLE MODULE LOAD. Worse, the error names the
        CHILD view's own first line rather than the xpath that did it, so the
        line number in the log points somewhere innocent."""
        for name in self._XML:
            tree = etree.parse(_path(*name.split('/')))
            for node in tree.iter('xpath'):
                expr = node.get('expr') or ''
                self.assertNotIn(
                    '@string', expr,
                    '%s: an xpath selects by string (%s) — pick a `name`, a '
                    'hasclass() or a structural anchor' % (name, expr))

    def test_no_search_group_carries_a_string_or_expand(self):
        """R129 — Odoo 19 search `<group>` takes NEITHER, and it does not warn:
        it fails RNG validation and ABORTS THE WHOLE MODULE LOAD."""
        for name in ('views/goal_views.xml', 'views/goal_year_views.xml'):
            tree = etree.parse(_path(*name.split('/')))
            for search in tree.iter('search'):
                for group in search.iter('group'):
                    self.assertIsNone(group.get('string'), name)
                    self.assertIsNone(group.get('expand'), name)

    def test_no_cron_row_carries_a_removed_column(self):
        """`numbercall` and `doall` were REMOVED from `ir.cron` on Odoo 19 and
        including either aborts the whole module load."""
        # R118 — THE GATE STRIPS COMMENTS BEFORE IT GREPS. The rule binds the
        # data, and the comment beside the record is the sentence that stops
        # the next contributor reintroducing the bug.
        source = re.sub(r'<!--.*?-->', '', _src('data', 'ir_cron.xml'), flags=re.S)
        self.assertNotIn('numbercall', source)
        self.assertNotIn('doall', source)

    # ------------------------------------------------------------ the doors
    def test_every_hand_built_window_action_carries_views(self):
        """R125 — `_preprocessAction` maps over `action.views` unconditionally
        and the ORM computes that field only on a real action RECORD, so a
        dict handed to `doAction` throws a TypeError the theme shows as a
        generic "something went wrong" with nothing useful in the console."""
        for name in self._PY:
            if not name.endswith('.py'):
                continue
            tree = ast.parse(_src(*name.split('/')))
            for node in ast.walk(tree):
                if not isinstance(node, ast.Dict):
                    continue
                keys = [k.value for k in node.keys
                        if isinstance(k, ast.Constant)]
                if 'type' not in keys or 'view_mode' not in keys:
                    continue
                kinds = [v.value for k, v in zip(node.keys, node.values)
                         if isinstance(k, ast.Constant) and k.value == 'type'
                         and isinstance(v, ast.Constant)]
                if 'ir.actions.act_window' not in kinds:
                    continue
                self.assertIn('views', keys,
                              '%s: an act_window dict with no "views"' % name)

    # ------------------------------------------------- the portal helpers
    def test_every_private_portal_helper_carries_this_modules_prefix(self):
        """R186 — ALL `CustomerPortal` SUBCLASSES MERGE INTO ONE CLASS. A
        helper called `_notice` here and `_notice` in another module are the
        same attribute on the same class, and whichever module loads last
        silently wins. Nothing about it is visible at runtime; it has taken a
        confirmation sentence and two portal pages down on this programme."""
        tree = ast.parse(_src('controllers', 'portal.py'))
        for node in ast.walk(tree):
            if not isinstance(node, ast.ClassDef):
                continue
            for item in node.body:
                if not isinstance(item, ast.FunctionDef):
                    continue
                if not item.name.startswith('_'):
                    continue
                # Framework hooks are overridden ON PURPOSE.
                if item.name.startswith('_prepare_'):
                    continue
                self.assertTrue(
                    item.name.startswith('_gl_'),
                    'controllers/portal.py: %s() must be prefixed `_gl_` or '
                    'it silently collides with another module' % item.name)

    # ------------------------------------------------------------ the SCSS
    def test_no_mixed_unit_min_or_max_in_the_scss(self):
        """Sass evaluates `min()`/`max()` and a px/% pair kills the ENTIRE
        asset bundle, not just this file."""
        for name in self._SCSS:
            source = _src(*name.split('/'))
            for call in re.findall(r'\b(?:min|max)\(([^)]*)\)', source):
                self.assertFalse(
                    '%' in call and 'px' in call,
                    '%s: a mixed-unit min()/max() kills the whole bundle'
                    % name)

    def test_every_keyframe_declares_both_ends(self):
        """R156 — with `animation-fill-mode: both` and a `from`-only keyframe
        the 100% frame is the element's OWN computed value, which the same
        rule has just set to `opacity: 0`: the surface animates from
        invisible to invisible and stays there."""
        for name in self._SCSS:
            source = _src(*name.split('/'))
            for block in re.findall(r'@keyframes[^{]*\{(.*?)\n\}', source,
                                    re.S):
                self.assertIn('from', block, '%s: keyframe has no from' % name)
                self.assertIn('to', block,
                              '%s: a from-only keyframe animates from '
                              'invisible to invisible' % name)

    def test_the_progress_track_owns_its_own_box(self):
        """R178 — a rule further up the cascade pads a span, and a fill whose
        containing block is 32px narrower than its track draws "finished" as
        "nearly finished" with no error anywhere."""
        for name, selector in (('static/src/scss/goals.scss', '.pbgl-track'),
                               ('static/src/scss/portal_goals.scss',
                                '.pbgl-dial')):
            source = _src(*name.split('/'))
            block = source.split(selector + ' {')[1].split('}')[0]
            self.assertIn('box-sizing', block)
            self.assertIn('padding: 0', block)

    # ---------------------------------------------------------- the switches
    def test_every_switch_reads_through_the_fallback(self):
        """A database with no row at all has to behave identically, or a
        feature works on the box it was written on and nowhere else."""
        from odoo.addons.pb_goals.models.goals_common import (
            DEFAULTS, flag, number)
        icp = self.env['ir.config_parameter'].sudo()
        for key in DEFAULTS:
            row = icp.search([('key', '=', key)])
            row.unlink()
        self.assertTrue(flag(self.env, 'pb_goals.reminders'))
        self.assertEqual(number(self.env, 'pb_goals.sla_days'), 5)

    def test_no_translated_sentence_says_bracket_s(self):
        """R46 — "9 goal(s)" is how a screen announces it was written by a
        programme rather than by a person, and this product's whole voice is
        the other thing. LOG LINES KEEP THE SHORTHAND — nobody reads a log for
        its prose — so the gate looks only inside `_()`, which is exactly the
        set of strings a person reads."""
        for name in self._PY:
            tree = ast.parse(_src(*name.split('/')))
            for node in ast.walk(tree):
                if not isinstance(node, ast.Call):
                    continue
                if not (isinstance(node.func, ast.Name)
                        and node.func.id == '_'):
                    continue
                for arg in node.args:
                    if isinstance(arg, ast.Constant) \
                            and isinstance(arg.value, str):
                        self.assertNotIn(
                            '(s)', arg.value,
                            '%s: a sentence a person reads says "(s)"' % name)
