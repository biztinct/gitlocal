# -*- coding: utf-8 -*-
"""RIZE W2 C1 — the rails that must not quietly stop working.

The live Chrome run is what proves the pages render; these are the floor.
Every one of them is written against a failure this module could have and that
nothing at runtime would report:

  * a sender that is not idempotent is four thousand people emailed twice,
    with a cheerful count in the log;
  * an audience that silently drops the people with no work email is a notice
    a shift worker never saw and nobody can explain;
  * an edit window that does not hold is a change made the night before that
    nobody can find afterwards;
  * a recurrence that spawns twice is a town hall on the calendar two Mondays
    running for ever;
  * two adjacent string literals in a JS file blank the ENTIRE backend asset
    bundle for every user in the product, with a clean server log;
  * an icon name that is not in the shared registry draws a plain circle with
    no error at all.

WHY THE FIXTURES ARE NAMED "DEMO". Everything this suite creates is rolled
back with the transaction, but the names are the live convention anyway
(ledger rule 9): a fixture copied into a live script keeps the name it was
written with, and a fixture called "RIZE test" is how the customer's name ends
up on a screen somebody is being shown.

NOTHING HERE SENDS AN EMAIL. Every address is `@example.com` and every message
is a `mail.mail` row created inside a transaction that is rolled back — but on
this database a queued mail goes out within the second of a COMMIT (R47), so
the addresses matter as much as the rollback does.
"""

import ast
import re

from datetime import date, datetime, timedelta

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
    return get_module_path('pb_hr_comm') + '/' + '/'.join(parts)


def _src(*parts):
    with open(_path(*parts), encoding='utf-8') as fh:
        return fh.read()


class CommCase(TransactionCase):
    """One company, one team with work emails, one announcement."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Post = cls.env['pb.hr.comm.post']
        cls.Template = cls.env['pb.hr.comm.template']
        cls.Delivery = cls.env['pb.hr.comm.delivery']
        cls.Default = cls.env['pb.hr.comm.default']
        cls.Jobs = cls.env['pb.hr.comm.automation']
        cls.Board = cls.env['pb.hr.comm']

        cls.company = cls.env['res.company'].create({'name': 'DEMO Comm Co'})
        cls.other_company = cls.env['res.company'].create(
            {'name': 'DEMO Comm Co Two'})

        # NO SIGNUP EMAIL. `res.users.create` sends one by default and on this
        # box a queued mail goes out within the second of a commit (R47).
        Users = cls.env['res.users'].with_context(no_reset_password=True)
        cls.hr_user = Users.create({
            'name': 'DEMO Comm HR',
            'login': 'demo.comm.hr@example.com',
            'email': 'demo.comm.hr@example.com',
            'company_id': cls.company.id,
            'company_ids': [(6, 0, [cls.company.id, cls.other_company.id])],
            'group_ids': [(6, 0, [
                cls.env.ref('base.group_user').id,
                cls.env.ref('pb_hr_comm.group_comm_manager').id])],
        })
        cls.officer_user = Users.create({
            'name': 'DEMO Comm Officer',
            'login': 'demo.comm.officer@example.com',
            'email': 'demo.comm.officer@example.com',
            'company_id': cls.company.id,
            'company_ids': [(6, 0, [cls.company.id])],
            'group_ids': [(6, 0, [
                cls.env.ref('base.group_user').id,
                cls.env.ref('pb_hr_comm.group_comm_user').id])],
        })
        #: THE PERSON WHO LOOKS AFTER ONE ANNOUNCEMENT AND HOLDS NO GROUP.
        #: The whole permission design rests on this account being able to do
        #: exactly one thing and nothing else.
        cls.resp_user = Users.create({
            'name': 'DEMO Comm Responsible',
            'login': 'demo.comm.resp@example.com',
            'email': 'demo.comm.resp@example.com',
            'company_id': cls.company.id,
            'company_ids': [(6, 0, [cls.company.id])],
            'group_ids': [(6, 0, [cls.env.ref('base.group_user').id])],
        })
        cls.stranger_user = Users.create({
            'name': 'DEMO Comm Stranger',
            'login': 'demo.comm.stranger@example.com',
            'email': 'demo.comm.stranger@example.com',
            'company_id': cls.company.id,
            'company_ids': [(6, 0, [cls.company.id])],
            'group_ids': [(6, 0, [cls.env.ref('base.group_user').id])],
        })

        Department = cls.env['hr.department']
        cls.team = Department.create({'name': 'DEMO Comm Team',
                                      'company_id': cls.company.id})
        cls.other_team = Department.create({'name': 'DEMO Comm Other Team',
                                            'company_id': cls.company.id})
        cls.job = cls.env['hr.job'].create({'name': 'DEMO Comm Job',
                                            'company_id': cls.company.id})

        Employee = cls.env['hr.employee']
        cls.people = Employee.browse()
        for index in range(3):
            cls.people |= Employee.create({
                'name': 'DEMO Comm Person %s' % (index + 1),
                'company_id': cls.company.id,
                'department_id': cls.team.id,
                'job_id': cls.job.id,
                'work_email': 'demo.comm.person%s@example.com' % (index + 1),
            })
        #: The hole in the delivery: somebody with no work email at all. Every
        #: count this module reports has to name them rather than quietly
        #: drop them.
        cls.no_email_person = Employee.create({
            'name': 'DEMO Comm No Email',
            'company_id': cls.company.id,
            'department_id': cls.team.id,
        })
        cls.outsider = Employee.create({
            'name': 'DEMO Comm Outsider',
            'company_id': cls.company.id,
            'department_id': cls.other_team.id,
            'work_email': 'demo.comm.outsider@example.com',
        })

        cls.template = cls.Template.create({
            'name': 'DEMO Town hall template',
            'subject': 'DEMO Town hall',
            'body_html': '<p>DEMO everybody in the canteen at four.</p>',
            'company_id': cls.company.id,
        })

    # ------------------------------------------------------------- helpers
    def _post(self, **values):
        vals = {
            'subject': 'DEMO Town hall',
            'body_html': '<p>DEMO everybody in the canteen at four.</p>',
            'company_id': self.company.id,
            'audience_kind': 'department',
            'department_ids': [(6, 0, self.team.ids)],
            'send_at': datetime.now() + timedelta(days=5),
            'responsible_user_id': self.resp_user.id,
        }
        vals.update(values)
        return self.Post.create(vals)

    def _mails_for(self, post):
        """Only this fixture's own messages.

        A TEST THAT ASSERTS OVER THE WHOLE TABLE ONLY PASSES ON AN EMPTY
        DATABASE (R221), and this suite runs against the live demo box.
        """
        return self.env['mail.mail'].sudo().search(
            [('subject', '=', post.subject)])


# =========================================================================
#  1. Who gets it
# =========================================================================
@tagged('post_install', '-at_install')
class TestAudience(CommCase):

    def test_a_department_audience_is_that_department(self):
        post = self._post()
        found = post.expand_audience()
        self.assertEqual(found['total'], 4)          # three plus the no-email
        self.assertEqual(found['with_email'], 3)
        self.assertEqual(found['no_email'], 1)
        self.assertIn('DEMO Comm No Email', found['no_email_names'])
        self.assertNotIn('demo.comm.outsider@example.com',
                         [row['email'] for row in found['rows']])

    def test_everybody_means_the_whole_company(self):
        post = self._post(audience_kind='everyone',
                          department_ids=[(5, 0, 0)])
        found = post.expand_audience()
        self.assertIn('demo.comm.outsider@example.com',
                      [row['email'] for row in found['rows']])

    def test_a_job_audience_is_that_job(self):
        post = self._post(audience_kind='job', department_ids=[(5, 0, 0)],
                          job_ids=[(6, 0, self.job.ids)])
        found = post.expand_audience()
        self.assertEqual(found['with_email'], 3)

    def test_an_audience_of_nobody_is_refused(self):
        with self.assertRaises(ValidationError):
            self._post(audience_kind='department',
                       department_ids=[(5, 0, 0)])

    def test_the_cap_is_a_ceiling_on_one_pass_and_says_so(self):
        post = self._post()
        found = post.expand_audience(cap=2)
        self.assertEqual(len(found['rows']), 2)
        self.assertTrue(found['capped'])

    def test_somebody_already_sent_it_is_skipped(self):
        post = self._post()
        self.Delivery.create({'post_id': post.id,
                              'employee_id': self.people[0].id,
                              'email': self.people[0].work_email})
        found = post.expand_audience(skip_delivered=True)
        self.assertEqual(len(found['rows']), 2)

    def test_a_person_cannot_be_sent_the_same_one_twice(self):
        """The idempotency rule is a ROW and Postgres decides, not Python."""
        post = self._post()
        self.Delivery.create({'post_id': post.id,
                              'employee_id': self.people[0].id})
        with self.assertRaises(Exception):
            with self.env.cr.savepoint():
                self.Delivery.create({'post_id': post.id,
                                      'employee_id': self.people[0].id})

    def test_checking_who_gets_it_counts_and_never_sends(self):
        post = self._post()
        before = len(self._mails_for(post))
        post.action_check_audience()
        self.assertEqual(post.recipient_count, 3)
        self.assertTrue(post.recipient_checked_on)
        self.assertEqual(len(self._mails_for(post)), before)

    def test_the_audience_sentence_is_a_sentence(self):
        post = self._post()
        self.assertIn('DEMO Comm Team', post.audience_note)
        everyone = self._post(audience_kind='everyone',
                              department_ids=[(5, 0, 0)])
        self.assertIn('DEMO Comm Co', everyone.audience_note)


# =========================================================================
#  2. The edit window
# =========================================================================
@tagged('post_install', '-at_install')
class TestWindow(CommCase):

    def test_the_responsible_may_change_it_up_to_the_window(self):
        post = self._post()
        # R229 — a fixture a guard will be asked about is re-browsed through a
        # clean recordset, never handed on from the create, or the guard is
        # asked with the context that exempts it.
        mine = self.Post.browse(post.id).with_user(self.resp_user)
        mine.write({'subject': 'DEMO Town hall, moved'})
        self.assertEqual(post.subject, 'DEMO Town hall, moved')

    def test_inside_the_window_the_responsible_is_refused_with_a_sentence(self):
        post = self._post(send_at=datetime.now() + timedelta(hours=6))
        mine = self.Post.browse(post.id).with_user(self.resp_user)
        with self.assertRaises(UserError) as caught:
            mine.write({'subject': 'DEMO Too late'})
        self.assertIn('HR lead', str(caught.exception))

    def test_inside_the_window_the_hr_lead_may_and_it_is_written_down(self):
        post = self._post(send_at=datetime.now() + timedelta(hours=6))
        theirs = self.Post.browse(post.id).with_user(self.hr_user)
        before = self.env['mail.message'].sudo().search_count(
            [('model', '=', 'pb.hr.comm.post'), ('res_id', '=', post.id)])
        theirs.write({'subject': 'DEMO Changed late'})
        self.assertEqual(post.subject, 'DEMO Changed late')
        after = self.env['mail.message'].sudo().search_count(
            [('model', '=', 'pb.hr.comm.post'), ('res_id', '=', post.id)])
        self.assertGreater(after, before,
                           'a late change has to be written into the history')

    def test_after_it_has_gone_out_nothing_changes(self):
        post = self._post()
        post._hc_move('scheduled')
        post._hc_move('sending')
        post._hc_move('sent')
        theirs = self.Post.browse(post.id).with_user(self.hr_user)
        with self.assertRaises(UserError):
            theirs.write({'subject': 'DEMO After the fact'})

    def test_the_window_follows_the_switch(self):
        post = self._post(send_at=datetime.now() + timedelta(days=5))
        self.assertTrue(post.editable_now)
        self.env['ir.config_parameter'].sudo().set_param(
            'pb_hr_comm.edit_window_days', '30')
        post.invalidate_recordset()
        self.assertFalse(post.editable_now)
        self.env['ir.config_parameter'].sudo().set_param(
            'pb_hr_comm.edit_window_days', '2')

    def test_a_sent_announcement_cannot_be_deleted(self):
        post = self._post()
        post._hc_move('scheduled')
        post._hc_move('sending')
        post._hc_move('sent')
        with self.assertRaises(UserError):
            self.Post.browse(post.id).with_user(self.hr_user).unlink()

    def test_saying_something_new_is_a_copy_and_starts_clean(self):
        post = self._post()
        post._hc_move('scheduled')
        post._hc_move('sending')
        post.sudo().write({'sent_count': 3})
        post._hc_move('sent')
        action = post.action_copy_it()
        copied = self.Post.browse(action['res_id'])
        self.assertEqual(copied.state, 'draft')
        self.assertEqual(copied.sent_count, 0)
        self.assertFalse(copied.sent_at)


# =========================================================================
#  3. The sender
# =========================================================================
@tagged('post_install', '-at_install')
class TestSender(CommCase):

    def _due(self, **values):
        post = self._post(**values)
        post._hc_move('scheduled')
        post.sudo().write({'send_at': datetime.now() - timedelta(minutes=5)})
        return post

    def test_one_message_per_person_with_a_work_email(self):
        post = self._due()
        self.Jobs.run_sender()
        post.invalidate_recordset()
        mails = self._mails_for(post)
        self.assertEqual(len(mails), 3)
        self.assertEqual(sorted(mails.mapped('email_to')),
                         sorted(self.people.mapped('work_email')))
        self.assertEqual(post.state, 'sent')
        self.assertEqual(post.sent_count, 3)
        self.assertEqual(post.no_email_count, 1)
        self.assertTrue(post.sent_at)

    def test_running_it_twice_sends_nothing_a_second_time(self):
        post = self._due()
        self.Jobs.run_sender()
        first = len(self._mails_for(post))
        self.Jobs.run_sender()
        self.assertEqual(len(self._mails_for(post)), first)

    def test_everybody_who_got_it_has_a_row(self):
        post = self._due()
        self.Jobs.run_sender()
        self.assertEqual(len(post.delivery_ids), 3)
        self.assertEqual(
            sorted(post.delivery_ids.mapped('employee_id').ids),
            sorted(self.people.ids))

    def test_the_burst_cap_finishes_on_the_next_pass(self):
        """A CAP IS A CEILING ON ONE PASS AND NEVER A PAGE SIZE (R76)."""
        icp = self.env['ir.config_parameter'].sudo()
        icp.set_param('pb_hr_comm.burst_cap', '2')
        try:
            post = self._due()
            self.Jobs.run_sender()
            post.invalidate_recordset()
            self.assertEqual(post.state, 'sending')
            self.assertEqual(post.sent_count, 2)
            self.Jobs.run_sender()
            post.invalidate_recordset()
            self.assertEqual(post.state, 'sent')
            self.assertEqual(post.sent_count, 3)
            self.assertEqual(len(self._mails_for(post)), 3)
        finally:
            icp.set_param('pb_hr_comm.burst_cap', '500')

    def test_switched_off_it_still_finishes_and_says_so(self):
        """A THING THAT IS OFF AND DOES NOT SAY SO IS REPORTED AS BROKEN
        (R54)."""
        icp = self.env['ir.config_parameter'].sudo()
        icp.set_param('pb_hr_comm.send_mail', '0')
        try:
            post = self._due()
            result = self.Jobs.run_sender()
            post.invalidate_recordset()
            self.assertFalse(result['enabled'])
            self.assertEqual(result['would'], 3)
            self.assertEqual(post.state, 'sent')
            self.assertEqual(post.sent_count, 0)
            self.assertEqual(len(self._mails_for(post)), 0)
            bodies = self.env['mail.message'].sudo().search(
                [('model', '=', 'pb.hr.comm.post'),
                 ('res_id', '=', post.id)]).mapped('body')
            self.assertTrue(any('switched off' in (body or '')
                                for body in bodies))
        finally:
            icp.set_param('pb_hr_comm.send_mail', '1')

    def test_the_poster_goes_with_it(self):
        attachment = self.env['ir.attachment'].sudo().create({
            'name': 'DEMO poster.txt',
            'datas': 'REVNTyBwb3N0ZXI=',
            'res_model': 'pb.hr.comm.post',
        })
        post = self._due(poster_ids=[(6, 0, attachment.ids)])
        self.Jobs.run_sender()
        mails = self._mails_for(post)
        self.assertTrue(mails)
        for mail in mails:
            self.assertIn(attachment.id, mail.attachment_ids.ids)

    def test_the_message_carries_the_words_and_not_their_source(self):
        post = self._due()
        self.Jobs.run_sender()
        body = self._mails_for(post)[0].body_html or ''
        self.assertIn('DEMO everybody in the canteen at four.', body)
        self.assertNotIn('&lt;p&gt;', body)

    def test_a_post_that_is_not_due_is_not_sent(self):
        post = self._post()
        post._hc_move('scheduled')
        self.Jobs.run_sender()
        self.assertEqual(len(self._mails_for(post)), 0)
        self.assertEqual(post.state, 'scheduled')


# =========================================================================
#  4. Coming round again
# =========================================================================
@tagged('post_install', '-at_install')
class TestRecurrence(CommCase):

    def test_a_monthly_one_makes_the_next_and_only_one(self):
        post = self._post(recurrence='monthly')
        post._hc_move('scheduled')
        post.sudo().write({'send_at': datetime.now() - timedelta(minutes=5)})
        self.Jobs.run_sender()
        following = self.Post.search([('parent_id', '=', post.id)])
        self.assertEqual(len(following), 1)
        self.assertEqual(following.state, 'scheduled')
        self.assertGreater(following.send_at, post.send_at)
        # IDEMPOTENT BY THE DATE (R214): a second pass makes no second one.
        self.Jobs._spawn_next(post)
        self.assertEqual(
            self.Post.search_count([('parent_id', '=', post.id)]), 1)

    def test_it_stops_when_it_was_told_to(self):
        # THE LAST DAY IS AFTER THIS ONE AND BEFORE THE NEXT: a recurrence
        # that stops before its own first outing is refused on create, which
        # is a different rule and has its own test below.
        post = self._post(recurrence='monthly',
                          recur_until=date.today() + timedelta(days=10))
        post._hc_move('scheduled')
        post.sudo().write({'send_at': datetime.now() - timedelta(minutes=5)})
        self.Jobs.run_sender()
        self.assertEqual(
            self.Post.search_count([('parent_id', '=', post.id)]), 0)

    def test_a_one_off_makes_nothing(self):
        post = self._post()
        post._hc_move('scheduled')
        post.sudo().write({'send_at': datetime.now() - timedelta(minutes=5)})
        self.Jobs.run_sender()
        self.assertEqual(
            self.Post.search_count([('parent_id', '=', post.id)]), 0)

    def test_it_cannot_stop_before_it_starts(self):
        with self.assertRaises(ValidationError):
            self._post(recurrence='weekly',
                       recur_until=date.today() - timedelta(days=1))

    def test_a_month_on_keeps_the_time_of_day(self):
        when = datetime(2026, 1, 31, 8, 30, 0)
        later = self.Jobs._next_datetime(when, 'monthly')
        self.assertEqual(later.hour, 8)
        self.assertEqual(later.minute, 30)
        self.assertEqual(later.month, 2)


# =========================================================================
#  5. The reminder
# =========================================================================
@tagged('post_install', '-at_install')
class TestNudge(CommCase):

    def test_it_reminds_the_right_person_on_the_right_day_once(self):
        post = self._post(send_at=datetime.now() + timedelta(days=2,
                                                             hours=3))
        post._hc_move('scheduled')
        result = self.Jobs.run_nudges()
        post.invalidate_recordset()
        self.assertGreaterEqual(result['sent'], 1)
        self.assertTrue(post.nudge_sent_at)
        mails = self.env['mail.mail'].sudo().search(
            [('email_to', '=', self.resp_user.email)])
        self.assertTrue(mails)
        self.assertTrue(post.activity_ids)
        self.assertEqual(post.activity_ids[0].user_id, self.resp_user)
        # A WINDOW, NOT A THRESHOLD (R148): a second run does nothing.
        before = len(mails)
        self.Jobs.run_nudges()
        self.assertEqual(len(self.env['mail.mail'].sudo().search(
            [('email_to', '=', self.resp_user.email)])), before)

    def test_something_going_out_next_month_is_not_reminded_about(self):
        post = self._post(send_at=datetime.now() + timedelta(days=30))
        post._hc_move('scheduled')
        self.Jobs.run_nudges()
        post.invalidate_recordset()
        self.assertFalse(post.nudge_sent_at)

    def test_the_default_responsible_is_the_hr_lead_unless_named(self):
        self.Default.create({'company_id': self.company.id,
                             'user_id': self.officer_user.id})
        holder = self.Default.responsible_for(self.company)
        self.assertEqual(holder, self.officer_user)

    def test_somebody_who_cannot_see_the_company_cannot_look_after_it(self):
        with self.assertRaises(ValidationError):
            self.Default.create({'company_id': self.other_company.id,
                                 'user_id': self.resp_user.id})


# =========================================================================
#  6. The sign-off
# =========================================================================
@tagged('post_install', '-at_install')
class TestApproval(CommCase):

    def test_the_route_is_registered_with_no_date_field(self):
        """R192 — a `date_field` asks who held the seat on a date in the past,
        and an announcement booked three months out would block on a seat
        nobody holds yet."""
        from odoo.addons.biz_approval_workflow.models.chain_shim import (
            CHAIN_PROCESS_KEYS)
        spec = CHAIN_PROCESS_KEYS.get('pb.hr.comm.post')
        self.assertTrue(spec)
        self.assertEqual(spec['process_key'], 'hr_comm_post')
        self.assertEqual(spec['submit_state'], 'submitted')
        self.assertEqual(spec['final_state'], 'scheduled')
        self.assertEqual(spec['refuse_state'], 'cancelled')
        self.assertFalse(spec['date_field'])

    def test_the_catalogue_row_this_module_owns_is_shipped(self):
        """R208 — without the row `Seed.lay` refuses with one INFO line, the
        install reports success, and nothing ever reaches an inbox."""
        process = self.env.ref('pb_hr_comm.process_hr_comm_post')
        self.assertEqual(process.key, 'hr_comm_post')
        self.assertEqual(process.model_name, 'pb.hr.comm.post')

    def test_with_sign_off_off_the_route_is_never_entered(self):
        icp = self.env['ir.config_parameter'].sudo()
        icp.set_param('pb_hr_comm.signoff', '0')
        post = self._post()
        post.action_schedule()
        self.assertEqual(post.state, 'scheduled')
        bodies = self.env['mail.message'].sudo().search(
            [('model', '=', 'pb.hr.comm.post'),
             ('res_id', '=', post.id)]).mapped('body')
        self.assertTrue(any('sign-off is switched off' in (body or '')
                            for body in bodies))

    def test_the_stamp_is_the_words_the_audience_and_the_moment(self):
        """R202 — a revision stamp may not contain anything an approver is
        meant to change on the way through, and it may not contain a number
        that is true of the world rather than of the record."""
        post = self._post()
        stamp = post._chain_revision_values()
        self.assertEqual(set(stamp), {'subject', 'body', 'send_at',
                                      'audience', 'departments', 'jobs'})
        self.assertNotIn('recipient_count', stamp)
        self.assertNotIn('write_date', stamp)
        first = post._hc_body_fingerprint()
        post.sudo().write({'body_html': '<p>DEMO something else.</p>'})
        self.assertNotEqual(first, post._hc_body_fingerprint())

    def test_the_drawer_rows_are_dicts(self):
        """R212 — the one inbox silently discards a row that is not a dict
        with head/sub/cells, and the drawer then reads as "there was nothing
        to show"."""
        post = self._post()
        detail = post._approval_detail(self.env['biz.approval.request'])
        self.assertTrue(detail['rows'])
        for row in detail['rows']:
            self.assertIsInstance(row, dict)
            self.assertIn('head', row)
            self.assertIn('cells', row)
        self.assertEqual(len(detail['columns']), len(detail['rows'][0]['cells']))

    def test_the_facts_read_as_the_system(self):
        post = self._post()
        facts = post.with_user(self.resp_user)._chain_facts()
        self.assertIn('people', facts)
        self.assertIn('audience', facts)

    def test_an_unfinished_announcement_cannot_be_scheduled(self):
        post = self._post(body_html=False)
        with self.assertRaises(UserError):
            post.action_schedule()

    def test_a_time_that_has_passed_is_refused(self):
        post = self._post()
        post.sudo().write({'send_at': datetime.now() - timedelta(days=1)})
        with self.assertRaises(UserError):
            post.action_schedule()


# =========================================================================
#  7. Who sees what
# =========================================================================
@tagged('post_install', '-at_install')
class TestVisibility(CommCase):

    def test_the_responsible_sees_their_own_and_nobody_elses(self):
        mine = self._post()
        theirs = self._post(subject='DEMO Somebody elses',
                            responsible_user_id=self.officer_user.id)
        seen = self.Post.with_user(self.resp_user).search([])
        self.assertIn(mine.id, seen.ids)
        self.assertNotIn(theirs.id, seen.ids)

    def test_the_hr_team_sees_them_all(self):
        mine = self._post()
        seen = self.Post.with_user(self.hr_user).search([])
        self.assertIn(mine.id, seen.ids)

    def test_somebody_with_nothing_sees_nothing(self):
        self._post()
        seen = self.Post.with_user(self.stranger_user).search([])
        self.assertFalse(seen)

    def test_the_calendar_refuses_a_post_the_reader_cannot_see(self):
        post = self._post(responsible_user_id=self.officer_user.id)
        answer = self.Board.with_user(self.stranger_user).get_post(post.id)
        self.assertFalse(answer['ok'])

    def test_a_record_argument_survives_the_wire(self):
        """R43 — a recordset does not survive JSON-RPC and arrives as an
        integer, so every public door coerces."""
        post = self._post()
        self.assertTrue(self.Board.get_post(post.id)['ok'])
        self.assertEqual(self.Board.open_post(post.id)['res_id'], post.id)


# =========================================================================
#  8. The calendar itself
# =========================================================================
@tagged('post_install', '-at_install')
class TestCalendar(CommCase):

    def test_the_grid_is_whole_weeks_and_knows_which_month_it_is_in(self):
        board = self.Board.with_user(self.hr_user).get_calendar(
            {'month': '2026-09'})
        self.assertTrue(board['allowed'])
        self.assertEqual(board['month'], '2026-09')
        self.assertEqual(board['month_label'], 'September 2026')
        for week in board['weeks']:
            self.assertEqual(len(week), 7)
        days = [day for week in board['weeks'] for day in week]
        self.assertEqual(len([d for d in days if d['in_month']]), 30)

    def test_an_announcement_lands_on_its_own_day(self):
        post = self._post(send_at=datetime(2026, 9, 14, 9, 0, 0))
        board = self.Board.with_user(self.hr_user).get_calendar(
            {'month': '2026-09'})
        found = [day for week in board['weeks'] for day in week
                 if any(p['id'] == post.id for p in day['posts'])]
        self.assertEqual(len(found), 1)

    def test_the_empty_month_teaches(self):
        board = self.Board.with_user(self.hr_user).get_calendar(
            {'month': '2019-01'})
        self.assertFalse(board['rows'])
        self.assertIn('Nothing is going out', board['headline'])

    def test_the_headline_does_the_arithmetic(self):
        when = datetime.now() + timedelta(days=2)
        post = self._post(send_at=when)
        post.action_check_audience()
        post._hc_move('scheduled')
        # THE MONTH IS NAMED and not left to the day this happens to run: a
        # test written on the 14th that passes and fails on the 30th is a test
        # nobody trusts.
        board = self.Board.with_user(self.hr_user).get_calendar(
            {'month': when.strftime('%Y-%m')})
        self.assertIn(post.subject, board['headline'])

    def test_the_scope_sentence_is_true_of_the_reader(self):
        self.assertIn('Every announcement',
                      self.Board.with_user(self.hr_user)._scope_sentence())
        self.assertIn('look after',
                      self.Board.with_user(self.resp_user)._scope_sentence())

    def test_the_search_box_is_accent_blind(self):
        post = self._post(subject='DEMO Thông báo',
                          send_at=datetime.now() + timedelta(days=2))
        board = self.Board.with_user(self.hr_user).get_calendar(
            {'q': 'thong bao'})
        self.assertIn(post.id, [row['id'] for row in board['rows']])

    def test_the_home_card_is_never_a_dead_end(self):
        card = self.env['pb.hr.comm.home'].with_user(
            self.stranger_user).get_home()
        self.assertIn('headline', card)
        self.assertTrue(card['headline'])
        self.assertIsInstance(card['rows'], list)
        self.assertIsInstance(card['celebrations'], list)

    def test_a_short_company_code_fits_in_a_day(self):
        self.assertEqual(self.Board._short('Payobook Vietnam JSC'), 'PVJ')
        self.assertEqual(self.Board._short('Payobook'), 'PAY')


# =========================================================================
#  9. The celebration cards
# =========================================================================
@tagged('post_install', '-at_install')
class TestCelebrationCards(CommCase):

    def test_the_card_is_this_modules_and_carries_the_name(self):
        emp = self.people[0]
        row = {'kind': 'birthday', 'years': 0, 'day_label': '14 September'}
        before = self.env['mail.mail'].sudo().search_count(
            [('email_to', '=', emp.work_email)])
        self.env['pb.rnr.celebration']._send_celebration(
            emp, row, emp.work_email)
        mails = self.env['mail.mail'].sudo().search(
            [('email_to', '=', emp.work_email)], order='id desc')
        self.assertEqual(len(mails), before + 1)
        body = mails[0].body_html or ''
        self.assertIn('Happy birthday', body)
        self.assertIn('DEMO Comm Co', body)
        self.assertNotIn('odoo', body.lower())

    def test_one_year_reads_one_year_and_not_one_years(self):
        """R46 — "1 years with us today" is how a screen announces it was
        written by a programme."""
        emp = self.people[1]
        row = {'kind': 'anniversary', 'years': 1, 'day_label': '3 March'}
        self.env['pb.rnr.celebration']._send_celebration(
            emp, row, emp.work_email)
        mail = self.env['mail.mail'].sudo().search(
            [('email_to', '=', emp.work_email)], order='id desc', limit=1)
        self.assertIn('1 year with us', mail.subject)
        self.assertNotIn('1 years', mail.subject)

    def test_the_switch_that_covers_both_kinds_is_still_off_here(self):
        """D17 — the cards ship OFF and this phase does not turn them on."""
        value = self.env['ir.config_parameter'].sudo().get_param(
            'pb_rnr.anniv_mail', '0')
        self.assertIn(str(value), ('0', 'False', ''),
                      'the celebration switch must ship off (D17)')


# =========================================================================
#  10. The gates
# =========================================================================
@tagged('post_install', '-at_install')
class TestGates(CommCase):

    # EVERY FILE THIS MODULE SHIPS, AND THE LIST IS THE GATE (R146). A gate
    # that names half the files checks half the files, and the half it misses
    # is the half that was written last.
    _JS = ('static/src/js/comm_calendar.js', 'static/src/js/comm_home.js',
           'static/src/js/comm_palette.js')
    _PY = ('models/comm_common.py', 'models/template.py',
           'models/responsible.py', 'models/delivery.py', 'models/post.py',
           'models/post_approval.py', 'models/sender.py',
           'models/celebration_ext.py', 'models/pb_hr_comm.py',
           'models/pb_hr_comm_home.py', 'hooks.py', '__manifest__.py')
    _XML = ('views/comm_views.xml', 'views/mail_templates.xml',
            'data/ir_cron.xml', 'data/approval_process.xml',
            'security/pb_hr_comm_security.xml',
            'security/pb_hr_comm_rules.xml',
            'static/src/xml/comm_calendar.xml',
            'static/src/xml/comm_home.xml')
    #: The OWL templates alone — three of the gates below are about the
    #: compiled template scope and not about XML in general.
    _OWL = ('static/src/xml/comm_calendar.xml',
            'static/src/xml/comm_home.xml')
    _SCSS = ('static/src/scss/comm.scss',)

    # ------------------------------------------------------------ the word
    def test_the_vendor_name_never_reaches_a_user_visible_string(self):
        """R118 — the gate strips COMMENTS before it greps. The rule binds
        user-visible STRINGS; an engineering comment must be able to say the
        real name."""
        for name in self._PY:
            tree = ast.parse(_src(*name.split('/')))
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

    def test_no_user_visible_xml_string_says_the_vendor_name(self):
        """The rule binds user-visible STRINGS, so the gate reads the TEXT and
        the attributes a person sees — never the tag names, which include the
        framework's own root element, and never the comments (R118)."""
        seen = ('string', 'help', 'placeholder', 'title', 'confirm', 'name',
                'label', 'sub', 'blurb')
        for name in self._XML:
            tree = etree.parse(_path(*name.split('/')))
            for node in tree.iter():
                if not isinstance(node.tag, str):        # a comment
                    continue
                for text in (node.text, node.tail):
                    if text and _RE_VENDOR.search(text):
                        self.fail('%s: a user-visible line says the vendor '
                                  'name: %r' % (name, text.strip()[:80]))
                for key, value in (node.attrib or {}).items():
                    if key in seen and value and _RE_VENDOR.search(value):
                        self.fail('%s: %s="%s" says the vendor name'
                                  % (name, key, value[:80]))

    def test_no_emoji_anywhere(self):
        for name in self._PY + self._JS + self._XML + self._SCSS:
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
        self.assertIn('megaphone', known,
                      'the shared registry on this server has no megaphone, '
                      'so every announcement icon draws a plain circle')
        used = set()
        for name in self._JS + self._OWL:
            source = _src(*name.split('/'))
            used |= set(re.findall(r"""\bic\(\s*['"]([A-Za-z0-9]+)['"]""",
                                   source))
            for block in re.findall(r'_ICON\s*=\s*\{(.*?)\}', source, re.S):
                used |= set(re.findall(r""":\s*["']([A-Za-z0-9]+)["']""",
                                       block))
            for block in re.findall(r"icon:\s*[\"']([A-Za-z0-9]+)[\"']",
                                    source):
                used.add(block)
        self.assertTrue(used)
        missing = sorted(used - known)
        self.assertFalse(
            missing,
            'these icons are not in the shared registry and will draw a '
            'plain circle with no error: %s' % ', '.join(missing))

    # -------------------------------------------------------------- the JS
    def test_no_adjacent_string_literals_in_the_js(self):
        """R2 — a Python habit (`"one " "two"`) is a SyntaxError that kills
        the ENTIRE backend asset bundle."""
        for name in self._JS:
            self.assertFalse(
                _RE_ADJACENT_STRINGS.search(_src(*name.split('/'))),
                '%s has two adjacent string literals' % name)

    def test_the_owl_template_calls_no_javascript_global(self):
        """R205 — a compiled OWL expression runs in a RESTRICTED SCOPE, and
        the whole component fails to render with the real cause two levels
        down an OwlError's `cause`."""
        for template in self._OWL:
            source = re.sub(r'<!--.*?-->', '', _src(*template.split('/')),
                            flags=re.S)
            for name in ('Boolean', 'Object.', 'JSON.', 'Number(', 'String(',
                         'parseInt', 'parseFloat', 'Array.'):
                self.assertNotIn(
                    name, source,
                    '%s: `%s` is a JavaScript global and an OWL template '
                    'cannot see it' % (template, name))

    def test_no_reserved_loop_variable_in_the_owl_template(self):
        """R1 — OWL reserves lt/gt/lte/gte as OPERATORS.

        R231/R118 — THE GATE STRIPS COMMENTS BEFORE IT GREPS, and this is the
        fourth time on this programme it has had to. The rule binds what the
        template COMPILES; the comment beside it is the sentence that stops
        the next contributor reintroducing the bug, and it has to be able to
        quote the thing it is warning about. The first version of this gate
        failed on its own warning, exactly as the emoji gate and the plural
        gate did in D1.
        """
        for template in self._OWL:
            source = re.sub(r'<!--.*?-->', '', _src(*template.split('/')),
                            flags=re.S)
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
        takes the whole file with it."""
        for name in self._XML:
            for body in re.findall(r'<!--(.*?)-->', _src(*name.split('/')),
                                   re.S):
                self.assertNotIn(
                    '--', body,
                    '%s: a comment ruled with hyphens is a parse error — '
                    'rule section comments with "=" (R35)' % name)

    def test_every_nolabel_field_in_a_group_carries_a_colspan(self):
        """R128 — an inner `<group>` is a two-column grid and a label-less
        field takes the NARROW cell."""
        tree = etree.parse(_path('views', 'comm_views.xml'))
        for field in tree.iter('field'):
            if field.get('nolabel') != '1':
                continue
            parent = field.getparent()
            if parent is not None and parent.tag == 'group':
                self.assertTrue(
                    field.get('colspan'),
                    'views/comm_views.xml: <field name="%s" nolabel="1"> '
                    'inside a <group> needs colspan="2"' % field.get('name'))

    def test_no_inherited_view_selects_by_string(self):
        """R213 — view inheritance may not select by `string`, and it is not
        a warning: it ABORTS THE WHOLE MODULE LOAD, naming the wrong line."""
        for name in self._XML:
            tree = etree.parse(_path(*name.split('/')))
            for node in tree.iter('xpath'):
                expr = node.get('expr') or ''
                self.assertNotIn('@string', expr, name)

    def test_no_search_group_carries_a_string_or_expand(self):
        """R129 — Odoo 19 search `<group>` takes NEITHER, and it does not
        warn: it fails RNG validation and ABORTS THE WHOLE MODULE LOAD."""
        tree = etree.parse(_path('views', 'comm_views.xml'))
        for search in tree.iter('search'):
            for group in search.iter('group'):
                self.assertIsNone(group.get('string'))
                self.assertIsNone(group.get('expand'))

    def test_no_cron_row_carries_a_removed_column(self):
        """`numbercall` and `doall` were REMOVED from `ir.cron` on Odoo 19 and
        including either aborts the whole module load."""
        source = re.sub(r'<!--.*?-->', '', _src('data', 'ir_cron.xml'),
                        flags=re.S)
        self.assertNotIn('numbercall', source)
        self.assertNotIn('doall', source)

    def test_the_mail_templates_use_no_owl_only_directive(self):
        """R5/R42 — `t-key` belongs to OWL and server-side QWeb logs it as an
        unknown directive on every render; a dict `t-att-class` renders the
        Python dict's REPR into the attribute and REPLACES the static class.

        R231 again — the comments come out first, because this file's own
        header explains both traps by name."""
        source = re.sub(r'<!--.*?-->', '', _src('views', 'mail_templates.xml'),
                        flags=re.S)
        self.assertNotIn('t-key', source)
        self.assertNotIn('t-att-class="{', source)

    # ------------------------------------------------------------ the doors
    def test_every_hand_built_window_action_carries_views(self):
        """R125 — `_preprocessAction` maps over `action.views`
        unconditionally, and a dict handed to `doAction` throws a TypeError
        the theme shows as a generic "something went wrong"."""
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
        the surface animates from invisible to invisible and stays there."""
        for name in self._SCSS:
            source = _src(*name.split('/'))
            for block in re.findall(r'@keyframes[^{]*\{(.*?)\n\}', source,
                                    re.S):
                self.assertIn('from', block)
                self.assertIn('to', block)

    def test_every_colour_has_a_literal_fallback(self):
        """R39/R134 — the pbim kit has no dark palette, so "validate in light
        AND dark" is satisfied by proving every colour RESOLVES."""
        source = _src('static', 'src', 'scss', 'comm.scss')
        bare = re.findall(r'var\(\s*(--pbim-[a-z-]+)\s*\)', source)
        self.assertFalse(bare,
                         'these tokens carry no literal fallback: %s'
                         % ', '.join(sorted(set(bare))))

    # ---------------------------------------------------------- the switches
    def test_every_switch_reads_through_the_fallback(self):
        """A database with no row at all has to behave identically, or a
        feature works on the box it was written on and nowhere else."""
        from odoo.addons.pb_hr_comm.models.comm_common import (
            DEFAULTS, flag, number)
        icp = self.env['ir.config_parameter'].sudo()
        for key in DEFAULTS:
            icp.search([('key', '=', key)]).unlink()
        self.assertTrue(flag(self.env, 'pb_hr_comm.send_mail'))
        self.assertFalse(flag(self.env, 'pb_hr_comm.signoff'))
        self.assertEqual(number(self.env, 'pb_hr_comm.edit_window_days'), 2)
        self.assertEqual(number(self.env, 'pb_hr_comm.burst_cap'), 500)

    def test_no_translated_sentence_says_bracket_s(self):
        """R46 — "9 person(s)" is how a screen announces it was written by a
        programme. LOG LINES KEEP THE SHORTHAND — nobody reads a log for its
        prose — so the gate looks only inside `_()`."""
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

    def test_every_leg_that_touches_the_database_is_under_a_savepoint(self):
        """R131 — a try/except is not enough when the thing that failed
        reached the database: Postgres aborts the whole transaction and every
        statement after it fails too, including the status write."""
        source = _src('models', 'comm_common.py')
        self.assertIn('with env.cr.savepoint():', source)
        sender = _src('models', 'sender.py')
        self.assertIn('with self.env.cr.savepoint():', sender)
