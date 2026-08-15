# -*- coding: utf-8 -*-
"""The egress seams, read off the source.

WHY SOURCE-LEVEL AND NOT BEHAVIOURAL
------------------------------------
Two of the three promises here are about the ABSENCE of something, and a
behavioural test can only ever sample the calls it thought to make:

  1. the payload reaches the prompt builder REDACTED and by no other route;
  2. the refusal short-circuit still runs before any of that;
  3. `get_provider_instance` — a method `payroll.ai.config` does not have — is
     gone from the pulse, and the call sites that remain are named, so a new
     one cannot appear without this list changing.

LEDGER RULE OBSERVED: a source-level assertion must be scoped to code, or be
written against a string the code has to contain and the prose cannot
plausibly repeat. The absent-token scan below is deliberately whole-file
(a commented-out call is a template), so `payroll_ai_pulse.py` may not name
the dead method even to explain it — and it does not.

Everything in this file runs without a database, which is why
`docs/tutorial_poc/author/tools/replay_tests.py` executes it too.
"""
import os
import re

from odoo.modules.module import get_module_path
from odoo.tests.common import TransactionCase, tagged

MODULE = 'pb_payroll_ai_insights'

# Written by concatenation so THIS file, which has to name it, is not a false
# positive if the same scan is ever pointed at the tests. Same idiom as
# test_data_access's ESCALATION.
DEAD_PROVIDER = 'get_provider' + '_instance'

# WHAT REMAINS, AND WHY — the Phase 4 grep-proof is "the pulse is clean and
# the rest is accounted for", not "the repository is clean".
#
#   payroll_ai_conversation.py  the VOICE path. Explicitly deferred to Phase 6
#                               by the handover; it is a Whisper call with its
#                               own audio egress question to argue.
#   payroll_ai_report.py x2     the PDF narratives and the executive summary.
#                               NOT fixed here on purpose: `_generate_section_
#                               narratives` puts `json.dumps(section['data'])`
#                               in a prompt, so repairing the provider lookup
#                               would switch on a THIRD unredacted egress path
#                               — the exact thing this phase closes — and the
#                               handover scopes the redaction to the two legacy
#                               paths. Dead is safer than live-and-leaking.
#                               Phase 6, with redaction, in one change.
EXPECTED_DEAD_CALLS = {
    'models/payroll_ai_conversation.py': 1,
    'models/payroll_ai_report.py': 2,
}


def _read(rel):
    base = get_module_path(MODULE)
    if not base:
        return None
    path = os.path.join(base, rel)
    if not os.path.exists(path):
        return None
    with open(path, encoding='utf-8') as fh:
        return fh.read()


def _region(text, marker, stop='\n    def '):
    body = text.split(marker)[1]
    return body.split(stop)[0]


@tagged('post_install', '-at_install')
class TestEgressSeams(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.engine_src = _read('models/payroll_ai_engine.py')
        cls.pulse_src = _read('models/payroll_ai_pulse.py')
        cls.redaction_src = _read('models/ai_redaction.py')

    # -- 1. the data-query path -------------------------------------------
    def test_01_the_prompt_builder_is_fed_the_redacted_variable(self):
        """Structural, because "the names are out" is a fact about which
        VARIABLE reaches the builder. `payroll_data` is the raw result and is
        still used afterwards — for `drilldown_model` and the gate note — so
        its mere presence in the method proves nothing; what matters is that
        the thing serialised into the prompt is the redacted copy."""
        body = _region(self.engine_src, 'def _process_data_query')
        self.assertIn('redacted_data, mapping = redact_names(payroll_data)', body,
                      "the data-query path no longer redacts before the prompt")
        self.assertIn('json.dumps(redacted_data', body)
        self.assertNotIn(
            'json.dumps(payroll_data', body,
            "the raw payload is serialised again — that string is the leak "
            "this phase closed")

    def test_01b_the_question_and_the_history_are_redacted_too(self):
        """A name that leaves in the question is as gone as one that leaves in
        the payload, and a conversation turn is an earlier answer with the
        names already put back into it."""
        body = _region(self.engine_src, 'def _process_data_query')
        self.assertIn('safe_message = redact_text(message, mapping)', body)
        self.assertIn("redact_text(msg.get('content', ''), mapping)", body,
                      "the conversation history goes out unredacted")
        self.assertIn('"content": data_prompt', body)
        self.assertNotIn('"content": message', body,
                         "the raw message is sent as a chat turn")

    def test_01c_the_reply_is_restored_on_both_return_paths(self):
        """Including the parse-failure fallback. A reader who was entitled to
        the names must not be handed "[person-1]" because the chart JSON did
        not parse — that branch is reached by a bad response, not a rare one."""
        body = _region(self.engine_src, 'def _process_data_query')
        self.assertIn('restore_deep(result, mapping)', body)
        self.assertIn('restore_names(raw_response, mapping)', body)

    def test_01d_the_refusal_still_short_circuits_before_any_of_it(self):
        """Phase D1's ordering, re-pinned against the new markers. The old
        test anchored on `json.dumps(payroll_data)`, which this phase deleted;
        a check that fails for a correct reason teaches the next author to
        delete checks, so it is rewritten to the new promise rather than
        dropped."""
        body = _region(self.engine_src, 'def _process_data_query')
        refusal_at = body.index("payroll_data.get('access_refused')")
        redact_at = body.index('redact_names(payroll_data)')
        prompt_at = body.index('data_query_prompt(')
        self.assertLess(refusal_at, redact_at,
                        "a refusal is redacted before it is recognised")
        self.assertLess(redact_at, prompt_at,
                        "the prompt is built before the redaction runs")

    def test_01e_the_prompt_builder_takes_only_what_it_is_given(self):
        """A builder that quietly cleans its own inputs is a builder whose
        caller stops thinking about them. This one must not redact."""
        body = _region(self.engine_src, 'def data_query_prompt', stop='\nclass ')
        for token in ('redact_names', 'redact_text', 'self.env', 'search('):
            self.assertNotIn(token, body,
                             "data_query_prompt does its own %s" % token)

    # -- 1f. THE CLASSIFIER, which ran before any of it -------------------
    def test_01f_the_intent_classifier_prompt_is_built_from_scrubbed_text(self):
        """THE SHIP-BLOCKER THE PHASE 4 REVIEW FOUND.

        `_classify_intent` is the FIRST provider call of every question, and
        it sent the raw message. All of the redaction work sat in
        `_process_data_query`, which runs afterwards — so the comment there
        claiming "three things are redacted" was describing a method that had
        already been beaten to the wire by the whole user message.

        There is no mapping at this point (nothing has been queried), so what
        is available is the generic scrub. Pinned structurally for the same
        reason as test_01: which VARIABLE reaches the builder is the fact.
        """
        body = _region(self.engine_src, 'def _classify_intent')
        self.assertIn('safe_message = generic_scrub(message)', body,
                      "the classifier no longer scrubs before it sends")
        self.assertIn('INTENT_CLASSIFICATION_PROMPT.format(message=safe_message)',
                      body)
        self.assertNotIn(
            'INTENT_CLASSIFICATION_PROMPT.format(message=message)', body,
            "the raw message is formatted into the classification prompt")
        scrub_at = body.index('generic_scrub(message)')
        send_at = body.index('provider.generate_text(')
        self.assertLess(scrub_at, send_at,
                        "the message is sent before it is scrubbed")

    def test_01g_every_history_turn_is_scrubbed_on_all_four_paths(self):
        """MAJOR-3. History is an earlier ANSWER with the names put back into
        it by `restore_deep` — the user did not type those names, this module
        re-inserted them, and then sent them back out on the next turn.

        Three of the four paths never build a mapping at all, so they get the
        generic scrub; the data path gets the mapping as well. What no path
        may do any more is pass `msg.get('content')` straight through.
        """
        paths = ('_process_data_query', '_process_knowledge_query',
                 '_process_onboarding_query', '_process_general_query')
        for name in paths:
            body = _region(self.engine_src, 'def %s' % name)
            self.assertIn('conversation_history[-6:]', body,
                          "%s no longer reads history — update this test" % name)
            self.assertNotIn(
                '"content": msg.get(\'content\', \'\')', body,
                "%s sends a history turn unscrubbed" % name)
            self.assertTrue(
                'generic_scrub(msg.get' in body or 'redact_text(msg.get' in body,
                "%s does not scrub its history turns" % name)
        # And the residual is disclosed where the mechanism is, not only in a
        # report somebody reads once (the ledger's standing rule).
        self.assertIn('PRIOR-TURN NAMES IN CONVERSATION HISTORY',
                      self.redaction_src,
                      "the history residual is not named in ai_redaction")
        self.assertIn('Phase 6', self.redaction_src,
                      "the residual names no owner and no next step")

    # -- 2. the pulse ------------------------------------------------------
    def test_02_the_pulse_no_longer_calls_a_method_that_does_not_exist(self):
        """Whole-file, comments included: a commented-out call is a template."""
        self.assertNotIn(
            DEAD_PROVIDER, self.pulse_src,
            "the pulse asks for a provider factory payroll.ai.config does not "
            "have, and the bare except around it makes that failure silent")
        self.assertIn('config.get_provider()', self.pulse_src)

    def test_02b_what_remains_is_named_rather_than_merely_absent_here(self):
        """A grep-proof that only says "this file is clean" lets the next one
        appear somewhere else. Every surviving call site is counted, so a new
        one fails this test and a fixed one does too."""
        base = get_module_path(MODULE)
        self.assertTrue(base)
        found = {}
        for root, _dirs, files in os.walk(base):
            for name in files:
                if not name.endswith('.py'):
                    continue
                path = os.path.join(root, name)
                rel = os.path.relpath(path, base)
                if rel.startswith('tests' + os.sep):
                    continue
                with open(path, encoding='utf-8') as fh:
                    count = fh.read().count(DEAD_PROVIDER)
                if count:
                    found[rel.replace(os.sep, '/')] = count
        self.assertEqual(
            found, EXPECTED_DEAD_CALLS,
            "the surviving dead-provider call sites changed. If one was fixed, "
            "drop it from EXPECTED_DEAD_CALLS; if one was added, it is a "
            "feature that will be silently off forever.")

    def test_02c_the_pulse_prompt_is_fed_redacted_details(self):
        body = _region(self.pulse_src, 'def _generate_ai_summaries')
        self.assertIn('redacted_details(alert.details)', body)
        self.assertIn('pulse_summary_prompt(', body)
        self.assertNotIn('alert.details or', body,
                         "the raw details string reaches the prompt again")
        self.assertIn('restore_names(summary.strip(), mapping)', body,
                      "the stored summary keeps the placeholders — the "
                      "database is inside the trust boundary and a per-call "
                      "mapping cannot be resolved later")

    # -- 3. the redaction module itself ------------------------------------
    def test_03_the_redaction_module_reaches_no_database(self):
        """It takes a structure and returns one. A helper that grew an ORM
        read would be a second, unaudited way for record data to be gathered
        for a prompt."""
        for token in ('from odoo', 'import odoo', 'self.env', '.search(',
                      '.browse(', 'cr.execute'):
            self.assertNotIn(
                token, self.redaction_src,
                "ai_redaction.py contains %r — it is meant to be pure" % token)

    def test_03b_the_pointer_to_the_other_copy_is_on_both_ends(self):
        """The scrub family exists twice on purpose (pb_learn does not depend
        on this module and must not). A duplication nobody can find from
        either end is a duplication that drifts."""
        self.assertIn('learn_intent.py', self.redaction_src,
                      "ai_redaction.py does not point at the pb_learn copy")
        learn = _read('../pb_learn/models/learn_intent.py')
        if learn is None:                       # pb_learn absent: nothing to pin
            self.skipTest('pb_learn is not installed beside this module')
        self.assertIn('ai_redaction.py', learn,
                      "the pb_learn copy does not point back here")

    def test_03c_the_placeholder_shape_is_pinned(self):
        """`restore_names` and both prompt builders describe the same shape to
        the model. If the format changes in one place, the model is told about
        a shape the parser will not recognise, and the names never come back."""
        self.assertIn("_PERSON_FMT = '[person-%d]'", self.redaction_src)
        self.assertIn(r"_PERSON_RE = re.compile(r'\[person-(\d+)\]')",
                      self.redaction_src)
        for src in (self.engine_src, self.pulse_src):
            self.assertTrue(
                re.search(r'\[person-1\]', src),
                "a prompt no longer tells the model what the placeholders are")
