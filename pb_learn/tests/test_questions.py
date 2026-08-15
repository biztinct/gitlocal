# -*- coding: utf-8 -*-
"""Question mining (Phase D2): two gates, a scrub, and a way out.

WHAT THIS FILE IS PROTECTING
----------------------------
Phase A2 made a ruling that this module has kept for four phases: the Coach
does not log the learner's question text, because on a payroll help box that
text is "why is <a colleague>'s net only 4.2m" — a named person and their pay,
landing in a table with no retention policy and no way for that person to know
it is there.

`learn.question` does not overturn that ruling; it carves an opening in it that
somebody has to walk through twice. These tests are the shape of the opening:

  * nothing is stored unless the TENANT switched collection on;
  * and nothing is stored unless THIS LEARNER agreed;
  * both re-asked on the server, because the browser's checks are a courtesy
    and this method is reachable by RPC;
  * the text is scrubbed even after consent, so a name typed into the box does
    not become a row;
  * a learner can delete their own rows, and an author can delete anyone's —
    consent that cannot be walked back is not consent;
  * and it expires.

The last one matters most in the long run, and is the easiest to let rot.
"""
from datetime import timedelta

from odoo import fields
from odoo.exceptions import AccessError
from odoo.tests.common import TransactionCase, new_test_user, tagged

from .common import load_content

FLAG = 'pb_learn.collect_questions'


@tagged('post_install', '-at_install')
class TestQuestionMining(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Question = cls.env['learn.question']
        cls.Consent = cls.env['learn.consent']
        cls.Param = cls.env['ir.config_parameter'].sudo()

    def _collect(self, on):
        self.Param.set_param(FLAG, 'True' if on else 'False')

    def _consent(self, granted):
        self.Consent.set_questions(granted)

    # -- 1. neither gate, one gate, both ----------------------------------
    def test_01_nothing_is_recorded_with_both_gates_shut(self):
        self._collect(False)
        self.Question.search([]).unlink()
        self.assertFalse(self.Question.record('how do I submit a run', 'payruns'))
        self.assertFalse(self.Question.search_count([]))

    def test_02_the_tenant_flag_alone_is_not_enough(self):
        self._collect(True)
        self._consent(False)
        self.Question.search([]).unlink()
        self.assertFalse(self.Question.record('how do I submit a run', 'payruns'))
        self.assertFalse(self.Question.search_count([]),
                         "a declined learner's question was stored")

    def test_02b_consent_alone_is_not_enough(self):
        self._collect(False)
        self._consent(True)
        self.Question.search([]).unlink()
        self.assertFalse(self.Question.record('how do I submit a run', 'payruns'))
        self.assertFalse(self.Question.search_count([]),
                         "a question was stored on a tenant that never switched "
                         "collection on")

    def test_03_both_gates_open_records_one_row(self):
        self._collect(True)
        self._consent(True)
        self.Question.search([]).unlink()
        self.assertTrue(self.Question.record(
            'how do I submit a run', 'payruns', matched=True, lang='en'))
        row = self.Question.search([], limit=1)
        self.assertEqual(row.question, 'how do I submit a run')
        self.assertEqual(row.screen, 'payruns')
        self.assertTrue(row.matched)
        self.assertEqual(row.user_id, self.env.user)

    def test_03b_an_unset_learner_is_not_a_consenting_one(self):
        """The default is 'unset', and unset must behave exactly like declined
        until somebody answers. A gate that opens while nobody is looking is
        not a gate."""
        self._collect(True)
        self.Consent.search([('user_id', '=', self.env.uid)]).unlink()
        self.assertEqual(self.Consent.questions_state(), 'unset')
        self.Question.search([]).unlink()
        self.assertFalse(self.Question.record('how do I submit a run', 'payruns'))
        self.assertFalse(self.Question.search_count([]))

    # -- 1b. create() is the control, not record() ------------------------
    def test_03c_a_direct_create_is_refused_when_either_gate_is_shut(self):
        """`record()` was a convenience with the gates in it, which left
        `create` reachable by RPC and gated by nothing.

        Every internal user has `perm_create` on this model — they must, the
        learner creates their own row — so "call create instead of record" was
        a complete bypass of the tenant flag, the learner's consent and the
        scrub. The gate lives in `create` now.
        """
        self._collect(False)
        self._consent(True)
        with self.assertRaises(AccessError,
                               msg="create() stored a question on a tenant "
                                   "that never switched collection on"):
            self.Question.create({'question': 'straight past record()',
                                  'screen': 'payruns'})
        self._collect(True)
        self._consent(False)
        with self.assertRaises(AccessError,
                               msg="create() stored a declined learner's "
                                   "question"):
            self.Question.create({'question': 'straight past record()',
                                  'screen': 'payruns'})

    def test_03d_a_direct_create_is_scrubbed_when_the_gates_are_open(self):
        """The scrub was in `record()` too, so the bypass carried a name into
        the table verbatim."""
        self._collect(True)
        self._consent(True)
        self.Question.search([]).unlink()
        self.Question.create({
            'question': "why is Nguyễn Thị Mai's net only 4.200.000",
            'screen': 'payslips'})
        stored = self.Question.search([], limit=1).question
        self.assertNotIn('Nguyễn Thị Mai', stored)
        self.assertNotIn('4.200.000', stored)
        self.assertIn('[name]', stored)

    def test_03e_a_create_that_scrubs_to_nothing_is_refused(self):
        self._collect(True)
        self._consent(True)
        with self.assertRaises(AccessError):
            self.Question.create({'question': '   ', 'screen': 'payruns'})

    # -- 2. the prompt is asked once --------------------------------------
    def test_04_the_drawer_is_only_told_to_ask_when_there_is_something_to_ask(self):
        self.Consent.search([('user_id', '=', self.env.uid)]).unlink()
        self._collect(False)
        self.assertFalse(self.Consent.should_ask_questions(),
                         "a consent prompt for a collection that is switched off "
                         "costs attention and implies the collection is happening")
        self._collect(True)
        self.assertTrue(self.Consent.should_ask_questions())

    def test_04b_a_decision_is_remembered_in_both_directions(self):
        self._collect(True)
        for granted, expected in ((False, 'declined'), (True, 'granted')):
            self.Consent.set_questions(granted)
            self.assertEqual(self.Consent.questions_state(), expected)
            self.assertFalse(self.Consent.should_ask_questions(),
                             "the drawer would ask again after a decision")
        self.assertEqual(
            self.Consent.search_count([('user_id', '=', self.env.uid)]), 1,
            "a second decision created a second consent row")

    def test_04c_the_consent_copy_ships_in_both_languages(self):
        chrome = load_content()['chrome']
        for key in ('consentTitle', 'consentBody', 'consentYes', 'consentNo'):
            pair = chrome.get(key)
            self.assertTrue(pair, "consent string %s is missing" % key)
            self.assertTrue(pair['en'] and pair['vi'],
                            "%s is not filled in both languages" % key)
            self.assertNotEqual(
                pair['en'], pair['vi'],
                "%s reaches a Vietnamese reader in English" % key)

    def test_04e_the_bundle_carries_the_tenant_switch(self):
        """The server half of the short-circuit.

        Without it the drawer has to ASK whether asking is allowed, which is
        the round trip the short-circuit exists to remove. It rode on
        `learn.intent.coach_bundle` until Phase 1a; it rides on the one runtime
        call now, which is the same promise with one fewer round trip.
        """
        Runtime = self.env['learn.runtime']
        self._collect(False)
        bundle = Runtime.bootstrap()
        self.assertIn('collect_questions', bundle,
                      "the bootstrap does not carry the tenant switch, so the "
                      "drawer has to ask for it")
        self.assertFalse(bundle['collect_questions'])
        self._collect(True)
        self.assertTrue(Runtime.bootstrap()['collect_questions'])

    def test_04f_the_drawer_returns_before_any_rpc_when_collection_is_off(self):
        """The client half, asserted on the source — the server cannot observe
        a round trip the browser chose not to make.

        Two RPCs after every answer, on every tenant, forever, to discover
        each time that a feature nobody switched on is still off, is not
        "behaves exactly as it did in Phase C" by any reading of it.
        """
        import os
        from odoo.modules.module import get_module_path
        with open(os.path.join(get_module_path('pb_learn'), 'static', 'src',
                               'coach', 'coach.js'), encoding='utf-8') as fh:
            src = fh.read()
        body = src.split('async _maybeStore(')[1].split('\n    async ')[0]
        self.assertLess(
            body.index('collect_questions'), body.index('this.orm.call('),
            "the drawer asks the server before checking the flag it was "
            "already given")

    def test_04d_the_consent_body_states_what_it_promises(self):
        """The prompt makes three promises the code has to keep: the text is
        scrubbed, the rows expire, and they can be deleted. A prompt that
        promises less than the code does undersells it; one that promises more
        is a lie the tests should catch."""
        body = load_content()['chrome']['consentBody']['en']
        self.assertIn('180', body, "the retention window is not stated")
        from odoo.addons.pb_learn.models.learn_question import RETENTION_DAYS
        self.assertIn(str(RETENTION_DAYS), body,
                      "the promised window and the coded one disagree")
        for promise in ('remove', 'delete'):
            self.assertIn(promise, body.lower(),
                          "the prompt does not mention: %s" % promise)
        # The row carries user_id, and the prompt has to say so. The delete-own
        # affordance the prompt offers is only possible BECAUSE of the
        # attribution — a consent notice that describes the storage as
        # anonymous while the table names you is the wrong kind of reassuring.
        self.assertIn('your name', body.lower(),
                      "the prompt does not disclose that the stored question "
                      "is attributed to the learner")
        self.assertTrue(self.Question._fields['user_id'].required,
                        "the prompt promises attribution the model does not keep")

    # -- 3. the scrub applies after consent too ---------------------------
    def test_05_a_name_or_an_amount_never_becomes_a_row(self):
        """Consent is to store the QUESTION, not the colleague.

        Somebody who agrees to help improve the guide has not agreed to put a
        named person's pay in a table, and would not expect to have.
        """
        self._collect(True)
        self._consent(True)
        self.Question.search([]).unlink()
        self.Question.record("why is Nguyễn Thị Mai's net only 4.200.000", 'payslips')
        stored = self.Question.search([], limit=1).question
        self.assertIn('[name]', stored)
        self.assertIn('[amount]', stored)
        self.assertNotIn('Nguyễn Thị Mai', stored)
        self.assertNotIn('4.200.000', stored)

    def test_05b_a_question_that_scrubs_to_nothing_is_not_stored(self):
        self._collect(True)
        self._consent(True)
        self.Question.search([]).unlink()
        self.assertFalse(self.Question.record('   ', 'payslips'))
        self.assertFalse(self.Question.search_count([]))

    def test_05c_the_stored_text_is_bounded(self):
        self._collect(True)
        self._consent(True)
        self.Question.search([]).unlink()
        self.Question.record('why ' * 400, 'payslips')
        self.assertLessEqual(len(self.Question.search([], limit=1).question), 200)

    # -- 4. deletable, by the learner and by an author --------------------
    def test_06_a_learner_deletes_their_own_and_sees_no_one_elses(self):
        self._collect(True)
        author = new_test_user(self.env, login='learn_q_a', groups='base.group_user')
        other = new_test_user(self.env, login='learn_q_b', groups='base.group_user')
        for user in (author, other):
            self.Consent.with_user(user).set_questions(True)
            self.Question.with_user(user).record('a question from %s' % user.login,
                                                 'payruns')
        mine = self.Question.with_user(author).search([])
        self.assertEqual(len(mine), 1, "a learner can see somebody else's questions")
        self.assertEqual(mine.user_id, author)
        mine.unlink()
        self.assertFalse(self.Question.with_user(author).search_count([]))
        self.assertTrue(
            self.Question.with_user(other).search_count([]),
            "deleting one learner's rows removed another's")

    def test_06b_an_author_reads_and_deletes_everything_but_writes_nothing(self):
        self._collect(True)
        author = new_test_user(self.env, login='learn_q_author',
                               groups='base.group_user,pb_learn.group_learn_author')
        learner = new_test_user(self.env, login='learn_q_learner',
                                groups='base.group_user')
        self.Consent.with_user(learner).set_questions(True)
        self.Question.with_user(learner).record('a learner question', 'payruns')
        rows = self.Question.with_user(author).search([])
        self.assertTrue(rows, "an author cannot see the table they triage")
        with self.assertRaises(AccessError,
                               msg="an author can edit a question into one "
                                   "nobody asked"):
            rows.with_user(author).write({'question': 'something else entirely'})
        rows.with_user(author).unlink()
        self.assertFalse(self.Question.with_user(author).search_count([]))

    def test_06c_consent_is_not_an_author_signal(self):
        """Deliberately unlike progress, events and confidence, all of which
        authors read. Who agreed to be recorded is not a content signal, and a
        list of everyone who declined is one nobody should assemble."""
        author = new_test_user(self.env, login='learn_q_author2',
                               groups='base.group_user,pb_learn.group_learn_author')
        learner = new_test_user(self.env, login='learn_q_learner2',
                                groups='base.group_user')
        self.Consent.with_user(learner).set_questions(False)
        self.assertFalse(
            self.Consent.with_user(author).search_count(
                [('user_id', '=', learner.id)]),
            "an author can read another learner's consent decision")

    # -- 5. retention ------------------------------------------------------
    def test_07_the_retention_job_deletes_past_the_window(self):
        from odoo.addons.pb_learn.models.learn_question import RETENTION_DAYS
        self._collect(True)
        self._consent(True)
        self.Question.search([]).unlink()
        self.Question.record('a recent question', 'payruns')
        self.Question.record('an ancient question', 'payruns')
        old = self.Question.search([('question', '=', 'an ancient question')])
        old.sudo().write({
            'occurred_at': fields.Datetime.now() - timedelta(days=RETENTION_DAYS + 1),
        })
        deleted = self.Question._gc_questions()
        self.assertEqual(deleted, 1)
        remaining = self.Question.search([]).mapped('question')
        self.assertEqual(remaining, ['a recent question'])

    def test_07b_the_cron_exists_and_points_at_the_job(self):
        cron = self.env.ref('pb_learn.cron_learn_question_gc',
                            raise_if_not_found=False)
        self.assertTrue(cron, "the retention job has no cron — rows would live "
                              "forever while the prompt promises 180 days")
        self.assertTrue(cron.active)
        self.assertIn('_gc_questions', cron.code)
        self.assertEqual(cron.model_id.model, 'learn.question')

    # -- 6. the log stayed clean ------------------------------------------
    def test_08_learn_event_still_carries_no_question_text(self):
        """The Phase A2 ruling, still standing.

        The whole reason `learn.question` is a separate model is that
        `learn.event` must remain a thing that cannot hold this. If somebody
        ever routes question text through `log`, `detail` is where it lands.
        """
        base = self.env['learn.event']
        self.assertEqual(base._fields['detail'].size, 64,
                         "learn.event.detail grew — it is bounded so that a "
                         "question cannot fit in it")
        import os
        from odoo.modules.module import get_module_path
        with open(os.path.join(get_module_path('pb_learn'), 'static', 'src',
                               'coach', 'coach.js'), encoding='utf-8') as fh:
            src = fh.read()
        call = src.split('this._log(answer.matched')[1].split(')')[0]
        self.assertNotIn('q', call.replace('answer.key', ''),
                         "the question text is being passed to the event log")
