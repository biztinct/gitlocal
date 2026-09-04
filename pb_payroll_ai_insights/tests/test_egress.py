# -*- coding: utf-8 -*-
"""The egress seams, read off the source.

WHY SOURCE-LEVEL AND NOT BEHAVIOURAL
------------------------------------
Two of the three promises here are about the ABSENCE of something, and a
behavioural test can only ever sample the calls it thought to make:

  1. the payload reaches the prompt builder REDACTED and by no other route —
     on the chat path, on the PULSE and, since LEARNOS Phase 6, on the PDF
     report;
  2. the refusal short-circuit still runs before any of that;
  3. `get_provider_instance` — a method `payroll.ai.config` does not have — is
     gone from every file in the module, and the counting mechanism stays so
     that a new one cannot appear without this test failing;
  4. the voice path transcribes and RETURNS. It cannot submit, and the two
     gates in front of it are re-asked server-side, in order, before a byte of
     audio is decoded.

LEDGER RULE OBSERVED: a source-level assertion must be scoped to code, or be
written against a string the code has to contain and the prose cannot
plausibly repeat. The absent-token scan below is deliberately whole-file
(a commented-out call is a template), so `payroll_ai_pulse.py` may not name
the dead method even to explain it — and it does not.

Everything in this file runs without a database, which is why
`docs/tutorial_poc/author/tools/replay_tests.py` executes it too.
"""
import ast
import os
import re

from odoo.modules.module import get_module_path
from odoo.tests.common import TransactionCase, tagged

MODULE = 'pb_payroll_ai_insights'

# Written by concatenation so THIS file, which has to name it, is not a false
# positive if the same scan is ever pointed at the tests. Same idiom as
# test_data_access's ESCALATION.
DEAD_PROVIDER = 'get_provider' + '_instance'

# NOTHING REMAINS — and the empty dict is the assertion, not an omission.
#
# Phase 4 left three call sites deliberately dead and counted them here,
# because repairing a dead provider call is switching an egress path ON and
# the redaction had not been written yet. Phase 6 repaired all three IN THE
# SAME CHANGE as their redaction:
#
#   payroll_ai_report.py x2     `_generate_section_narratives` and
#                               `_generate_executive_summary` now look up
#                               `get_provider()` and send `redact_names`d
#                               section data, restoring the narrative for the
#                               reader (test_05 below).
#   payroll_ai_conversation.py  the voice path. `rpc_send_voice_message` is
#                               replaced by `rpc_transcribe_voice`, which is
#                               double-gated, uses `get_provider()`, and
#                               CANNOT send (test_04b).
#
# Keeping the mechanism with an empty expectation is deliberate: a fourth call
# site appearing anywhere in this module still fails this test, which is the
# property that was worth having in the first place.
EXPECTED_DEAD_CALLS = {}


def _read(rel):
    base = get_module_path(MODULE)
    if not base:
        return None
    path = os.path.join(base, rel)
    if not os.path.exists(path):
        return None
    with open(path, encoding='utf-8') as fh:
        return fh.read()


def _po_map(text):
    """msgid -> msgstr, single-line entries — which is how ours are written.

    A COPY of the helper in test_data_access, and the duplication is
    deliberate: this file must run with no database (the offline harness
    executes it) and that one's setUpClass reaches for a model, so importing
    across would drag the database requirement in with it.
    """
    out = {}
    pat = re.compile(r'^msgid ("(?:[^"\\]|\\.)*")\nmsgstr ("(?:[^"\\]|\\.)*")$', re.M)
    for raw_id, raw_str in pat.findall(text or ''):
        out[ast.literal_eval(raw_id)] = ast.literal_eval(raw_str)
    return out


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
        cls.report_src = _read('models/payroll_ai_report.py')
        cls.conversation_src = _read('models/payroll_ai_conversation.py')
        cls.po_src = _read('i18n/vi_VN.po')

    # -- 1. the data-query path -------------------------------------------
    def test_01_the_prompt_builder_is_fed_the_redacted_variable(self):
        """Structural, because "the names are out" is a fact about which
        VARIABLE reaches the builder. `payroll_data` is the raw result and is
        still used afterwards — for `drilldown_model` and the gate note — so
        its mere presence in the method proves nothing; what matters is that
        the thing serialised into the prompt is the redacted copy."""
        body = _region(self.engine_src, 'def _process_data_query')
        self.assertIn(
            'redacted_data, mapping = redact_names(payroll_data, mapping=mapping)',
            body, "the data-query path no longer redacts before the prompt")
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
        redact_at = body.index('redact_names(payroll_data')
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
            # LEARNOS Phase 6 TIGHTENED THIS. It used to accept either the
            # generic scrub or the mapping, because three of the four paths
            # had no mapping to use. All four are handed the conversation's
            # mapping now, so all four must use it: with an empty mapping
            # `redact_text` IS the generic scrub, and with a real one it is
            # the thing that removes a name an earlier turn restored.
            self.assertIn(
                "redact_text(msg.get('content', ''), mapping)", body,
                "%s does not redact its history turns with the conversation "
                "mapping" % name)
            self.assertIn('mapping', _region(self.engine_src, 'def %s' % name),
                          "%s does not take a mapping" % name)
        # And the closure is disclosed where the mechanism is, not only in a
        # report somebody reads once (the ledger's standing rule).
        self.assertIn('PRIOR-TURN NAMES IN CONVERSATION HISTORY',
                      self.redaction_src,
                      "the history residual is not named in ai_redaction")
        self.assertIn('CLOSED IN LEARNOS PHASE 6', self.redaction_src,
                      "ai_redaction still describes the history residual as open")
        self.assertIn('redaction_map', self.redaction_src,
                      "the closure names no mechanism — a reader cannot find "
                      "the column that holds the mapping")

    def test_01h_the_mapping_is_the_conversations_and_is_saved_before_the_send(self):
        """LEARNOS Phase 6. Three facts, and the ORDER of two of them.

        The table is LOADED from the conversation, EXTENDED by the query
        result, and SAVED — and saved before the prompt goes out, because a
        provider timeout must not lose the association that the reply's
        placeholders will need on the next turn.
        """
        top = _region(self.engine_src, 'def process_message')
        self.assertIn('mapping = self._conversation_mapping(context)', top,
                      "process_message no longer loads the conversation's mapping")
        body = _region(self.engine_src, 'def _process_data_query')
        self.assertIn('redact_names(payroll_data, mapping=mapping)', body,
                      "the data path builds a fresh mapping again — a name "
                      "from an earlier turn is then unrecognisable")
        persist_at = body.index('self._persist_mapping(context, mapping)')
        prompt_at = body.index('data_query_prompt(')
        self.assertLess(persist_at, prompt_at,
                        "the mapping is saved after the prompt is built")

    def test_01i_the_mapping_dies_with_the_conversation_and_with_a_clear(self):
        """Retention, asserted rather than described. `redaction_map` is an
        ordinary column (so `unlink` takes it) and `action_clear` — the
        drawer's "clear chat" — must drop it too: keeping the table that
        decodes the placeholders after deleting the messages that used them is
        keeping the worse half."""
        body = _region(self.conversation_src, 'def action_clear')
        self.assertIn("'redaction_map': False", body,
                      "clearing the chat leaves the placeholder table behind")
        self.assertIn('MAP_CAP', self.conversation_src,
                      "the mapping is unbounded")
        self.assertIn('retention', self.conversation_src.lower(),
                      "the retention rule is not stated where the mechanism is")

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

    def test_02d_no_pulse_detector_keys_a_map_on_a_person(self):
        """THE HALF THE KEY-SUBSTITUTION CANNOT REACH.

        `redact_names` now rewrites KEYS as well as values, so a name that is
        also a value somewhere is removed from a key too. What it still cannot
        do is FIND a name that appears only as a key: there is no honest
        heuristic for "is this dict key a person", and the one that suggests
        itself ("two capitalised words") blanks `Retail Division`.

        So the origin is fenced instead, where it can be. Two detectors key a
        map on a record value today — the leave TYPE's name and the
        DEPARTMENT's — and neither is a person. This parses the pulse and
        refuses any detector that keys a map on anything derived from an
        employee.

        NEGATIVE CONTROL, EXECUTED: changing `type_counts[lt]` to
        `type_counts[lv.employee_id.name]` fails this test; changing it back
        passes. Both runs are in the Phase 6 report.
        """
        import ast
        tree = ast.parse(self.pulse_src)
        offenders = []
        for func in ast.walk(tree):
            if not (isinstance(func, ast.FunctionDef)
                    and func.name.startswith('_detect_')):
                continue
            keys = []
            for node in ast.walk(func):
                # `d[k] = v` and `d[k] += v`
                if isinstance(node, (ast.Assign, ast.AugAssign)):
                    targets = (node.targets if isinstance(node, ast.Assign)
                               else [node.target])
                    keys += [t.slice for t in targets
                             if isinstance(t, ast.Subscript)]
                # `d.get(k, default)`
                if (isinstance(node, ast.Call)
                        and isinstance(node.func, ast.Attribute)
                        and node.func.attr == 'get' and node.args):
                    keys.append(node.args[0])
            for key in keys:
                src = ast.unparse(key)
                if 'employee' in src or 'partner' in src:
                    offenders.append('%s: [%s]' % (func.name, src))
        self.assertFalse(
            offenders,
            "a pulse detector keys a map on a person, which `redact_names` "
            "cannot see: %s" % offenders)
        # And the scan must have found something, or it is broken rather than
        # passing — the same rule the model-scope checker uses.
        self.assertIn('type_counts[lt]', self.pulse_src,
                      "the keyed map this test was written for is gone; "
                      "re-point the scan rather than deleting it")

    # -- 2e/2f. the report, repaired and redacted in one change -------------
    def test_02e_the_report_asks_for_a_provider_that_exists(self):
        """Half one of the Phase-4 ruling. The lookup is repaired — and the
        other half is the next test, because either alone is the bad outcome:
        dead means four features silently off, repaired-without-redaction
        means employee names in a prompt."""
        self.assertNotIn(DEAD_PROVIDER, self.report_src)
        self.assertIn('config.get_provider()', self.report_src)
        body = _region(self.report_src, 'def _narrative_provider')
        self.assertIn('get_active_config()', body)

    def test_02f_the_report_prompt_is_fed_redacted_section_data(self):
        """Half two. Structural, because "the names are out" is a fact about
        which VARIABLE reaches the builder — and `section['data']` is still
        used afterwards (it is what the PDF's own tables are drawn from), so
        its presence in the file proves nothing."""
        for method in ('_generate_section_narratives',
                       '_generate_executive_summary'):
            body = _region(self.report_src, 'def %s' % method)
            self.assertIn('redact_sections(sections, mapping)', body,
                          "%s serialises a section without redacting it" % method)
            self.assertNotIn("json.dumps(section['data']", body,
                             "%s dumps the raw section data again — that "
                             "string is the leak" % method)
            self.assertNotIn("json.dumps(s['data']", body,
                             "%s dumps the raw section data again" % method)
            self.assertIn('restore_names(', body,
                          "%s hands the reader placeholders" % method)
        helper = _region(self.report_src, 'def redact_sections', stop='\ndef ')
        self.assertIn("redact_names(section.get('data') or {},", helper)

    def test_02f2_one_mapping_spans_the_whole_document(self):
        """THE CLAIM THE FIRST PHASE 6 DRAFT MADE AND DID NOT KEEP. Each
        method built its own table, so an employee could be [person-1] in the
        salary narrative and [person-4] in the executive summary. Nothing
        leaked; the promise was simply false. The accumulator is now created
        once, in `action_generate_report`, and every pass UPDATES it."""
        top = _region(self.report_src, 'def action_generate_report')
        self.assertIn('mapping = {}', top,
                      "the report no longer creates one accumulator")
        self.assertIn('self._build_report_sections(mapping)', top)
        self.assertIn('self._generate_executive_summary(sections, mapping)', top)
        for method in ('_generate_section_narratives',
                       '_generate_executive_summary'):
            body = _region(self.report_src, 'def %s' % method)
            self.assertIn('mapping.update(extended)', body,
                          "%s drops what it learned instead of sharing it"
                          % method)

    def test_02h_an_alert_summary_never_carries_a_name_it_cannot_map(self):
        """THE SECOND SHIP-BLOCKER THE PHASE 6 REVIEW FOUND.

        An alert's `summary` is prose a model wrote and this module then put
        the names BACK into (`payroll_ai_pulse` restores before storing, which
        is right — the database is inside the trust boundary). `summary` is not
        a person key, so `collect_names` never saw it and the whole Anomaly
        Alerts section went out with the week's joiners named in full.

        Provenance is the fix: every name a generated summary can contain came
        from that alert's own `details`, so the details are redacted into the
        report's mapping FIRST and the summary is redacted against it. Where
        the provenance cannot be checked the summary is dropped rather than
        guessed at.
        """
        body = _region(self.report_src, 'def alert_rows', stop='\ndef ')
        details_at = body.index("alert_names(raw.get('details'))")
        extend_at = body.index('extend_mapping(names, mapping)')
        redact_at = body.index('redact_text(summary, mapping)')
        self.assertLess(details_at, extend_at,
                        "the summary is redacted before its details are read")
        self.assertLess(extend_at, redact_at)
        self.assertIn('summary_is_traceable(', body,
                      "an untraceable summary is sent anyway")
        self.assertIn("summary = ''", body,
                      "there is no fallback that drops the summary")
        self.assertNotIn("'summary': a.summary", self.report_src,
                         "the raw stored summary reaches the payload again")
        self.assertNotIn("'summary': raw.get('summary')", self.report_src,
                         "the raw stored summary reaches the payload again")
        self.assertIn("PERSON_KEYS - {'name'}", body,
                      "the alert TITLE is being collected as a person")

    def test_02g_the_report_prompt_builders_take_only_what_they_are_given(self):
        """Same rule as `data_query_prompt`: a builder that quietly cleans its
        own inputs is a builder whose caller stops thinking about them."""
        for name in ('report_section_prompt', 'report_executive_prompt'):
            # STOP AT THE CLASS, not at the next `def`: these two builders are
            # the last top-level functions in the file, so a `\ndef ` stop runs
            # to EOF and reads the model's methods as part of the region. A
            # `within` that silently scopes to the wrong region is the most
            # expensive kind of green (ledger, Phase 1b).
            body = _region(self.report_src, 'def %s' % name, stop='\nclass ')
            for token in ('redact_names', 'restore_names', 'self.env', 'search('):
                self.assertNotIn(token, body, "%s does its own %s" % (name, token))
            self.assertIn('{_PLACEHOLDER_NOTE}', body,
                          "%s does not tell the model what the placeholders "
                          "are" % name)
        self.assertIn('[person-1]', _region(self.report_src, '_PLACEHOLDER_NOTE = ',
                                            stop='\n\ndef '),
                      "the note the two prompts share no longer describes the "
                      "placeholder shape")

    # -- 4. the voice path -------------------------------------------------
    def test_04_the_voice_path_is_double_gated_before_anything_is_decoded(self):
        """Tenant flag, then this user's consent, then the provider — and all
        three BEFORE `b64decode`. Both gates are re-asked here rather than
        trusted from the browser, because this endpoint is reachable by RPC
        from anything holding a session."""
        body = _region(self.conversation_src, 'def rpc_transcribe_voice')
        flag_at = body.index('flag_on(self.env, VOICE_FLAG)')
        consent_at = body.index('Consent.voice_granted()')
        ceiling_at = body.index('len(audio_base64) > MAX_AUDIO_B64')
        decode_at = body.index('b64decode')
        send_at = body.index('provider.transcribe_audio')
        self.assertLess(flag_at, consent_at, "consent is asked before the flag")
        self.assertLess(consent_at, ceiling_at,
                        "a payload is measured before consent is checked")
        # THE CEILING BEFORE THE DECODE. Measuring the string costs nothing;
        # decoding it is what allocates, and this endpoint is reachable by RPC
        # from anything holding a session — the browser's sixty-second stop is
        # a courtesy, not a control.
        self.assertLess(ceiling_at, decode_at,
                        "the payload is decoded before it is measured")
        self.assertLess(decode_at, send_at)
        self.assertIn('MAX_AUDIO_B64 = ', self.conversation_src,
                      "the ceiling is a magic number rather than a constant")

    def test_04b_the_transcriber_cannot_send_anything(self):
        """THE PROPERTY, not a promise about it. The old
        `rpc_send_voice_message` transcribed and then CALLED the send path, so
        a mis-heard sentence reached a language model before the person who
        said it had seen it. The replacement returns text; there is no branch
        in it that sends, and this is what stops one being added.

        NEGATIVE CONTROL, EXECUTED: adding
        `self.rpc_send_message(text)` inside the method fails this test.
        """
        body = _region(self.conversation_src, 'def rpc_transcribe_voice')
        for token in ('rpc_send_message', 'process_message', 'add_message',
                      'generate_chat', 'text_to_speech'):
            self.assertNotIn(token, body,
                             "the transcriber calls %s — a transcription must "
                             "never auto-submit" % token)
        self.assertIn("return {'text':", body,
                      "the transcriber no longer returns the text to the "
                      "person who spoke it")
        # And the retired endpoint is GONE, not merely unused: an old browser
        # tab calling it gets a clean error rather than the old behaviour.
        self.assertNotIn('def rpc_send_voice_message', self.conversation_src)

    def test_04b2_a_closed_drawer_cannot_post_the_audio_it_was_holding(self):
        """M2. `MediaRecorder.stop()` fires `onstop` ASYNCHRONOUSLY, so a
        drawer closed mid-recording used to release the microphone and then
        run the transcription callback for a component that no longer exists —
        an audio POST nobody has a window open for.

        The discard flag is set and the buffer emptied BEFORE the stream is
        released, and both the recorder callback and the transcriber re-ask
        it. Pinned in ORDER, because a flag set after the release is a flag
        the callback can beat."""
        js = _read('../pb_payroll_ai_insights/static/src/components/'
                   'ai_insight_chat/ai_insight_chat.js')
        self.assertTrue(js)
        unmount = js.split('onWillUnmount(')[1].split('});')[0]
        discard_at = unmount.index('this._discarded = true')
        empty_at = unmount.index('this._audioChunks = []')
        release_at = unmount.index('this._releaseMicrophone()')
        self.assertLess(discard_at, release_at,
                        "the microphone is released before the discard flag "
                        "is set")
        self.assertLess(empty_at, release_at)
        onstop = js.split('this._mediaRecorder.onstop = ')[1].split('};')[0]
        self.assertIn('if (this._discarded)', onstop,
                      "the recorder callback does not check the discard flag")
        transcribe = js.split('async _transcribe()')[1].split('\n    }')[0]
        self.assertIn('this._discarded', transcribe,
                      "the transcriber does not re-ask the discard flag")

    def test_04c_the_audio_residual_is_named_where_the_mechanism_is(self):
        """Audio cannot be redacted. That is not a reason to leave it
        undisclosed — the ledger's standing rule is that a residual is stated
        where the mechanism lives, not only in a report somebody reads once."""
        self.assertIn('RAW AUDIO LEAVES THIS SERVER ON THE VOICE PATH',
                      self.redaction_src)
        self.assertIn('payai.voice_enabled', self.redaction_src,
                      "the residual does not name the flag that gates it")

    def test_04d_the_voice_copy_ships_in_vietnamese_too(self):
        """LEARNOS Phase 6. The consent card is the one place a user is asked
        to agree to their own recording leaving the server, and a consent
        somebody could not read is not consent. Same AST re-derivation as
        test_06 — the list is computed from the source on every run, so
        rewording a sentence fails the suite rather than losing its
        Vietnamese."""
        self.assertTrue(self.conversation_src)
        catalogue = _po_map(self.po_src or '')
        tree = ast.parse(self.conversation_src)
        literals = []
        for node in ast.walk(tree):
            if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                    and node.func.id == '_' and node.args
                    and isinstance(node.args[0], ast.Constant)
                    and isinstance(node.args[0].value, str)):
                literals.append(node.args[0].value)
        self.assertTrue(literals, "no translatable strings found — the scan is broken")
        self.assertGreaterEqual(
            len(literals), 10,
            "the voice copy shrank — if a sentence went, say so in the report")
        missing = [s for s in literals if not catalogue.get(s)]
        self.assertFalse(missing, "voice copy with no Vietnamese: %r" % (missing[:3],))
        english = [s for s in literals if catalogue.get(s) == s]
        self.assertFalse(english, "Vietnamese identical to English: %r" % (english[:3],))

    def test_04e_the_consent_copy_names_what_actually_leaves(self):
        """A consent that does not name the thing being consented to is a
        button. Four claims, and the third and fourth are the ones the fix
        round added:

          1. the RECORDING is what is sent — not "your voice input", not "the
             audio feature";
          2. it goes to an OUTSIDE COMPANY, named as one rather than as "the
             provider set up for this company", which reads like us;
          3. WE CANNOT REDACT AUDIO. Every other egress in this module can be,
             and a reader who knows that would reasonably assume this one is;
          4. "nothing is sent until you press send" is scoped to the TEXT. The
             first draft said it flat, which is true of the transcript and
             false of the recording — the audio goes when the button is
             released, which is the whole reason the card exists. A notice
             that is reassuring about the wrong half is worse than none.
        """
        catalogue = _po_map(self.po_src or '')
        body = [s for s in catalogue if 'Hold the microphone and speak' in s]
        self.assertTrue(body, "the voice consent body is not in the catalogue")
        english = body[0]
        for claim in ('When you let go, the recording goes',
                      "outside company's speech service",
                      'cannot take names out of it',
                      'The text then waits in the box'):
            self.assertIn(claim, english,
                          "the consent card no longer says: %s" % claim)
        self.assertNotIn('Nothing is sent until', english,
                         "the card promises nothing is sent, which is false "
                         "of the recording")
        # Case-folded: the sentence opens with "Bản ghi âm", capitalised, and
        # an assertion that only knows the lower-case form is a test about
        # where the full stops are.
        vietnamese = catalogue[english].lower()
        for claim in ('khi bạn thả tay, bản ghi âm sẽ được gửi',
                      'công ty bên ngoài',
                      'không thể bỏ tên riêng',
                      'nằm chờ trong ô nhập'):
            self.assertIn(claim, vietnamese,
                          "the Vietnamese consent card no longer says: %s" % claim)
        # ONE NAME FOR THE THIRD PARTY. Two names for one thing in a consent
        # notice is a reader wondering how many there are.
        phrases = [v for v in catalogue.values()
                   if 'giọng nói' in v or 'nhận dạng' in v]
        self.assertTrue(phrases)
        for phrase in phrases:
            self.assertNotIn('nhận dạng giọng nói', phrase,
                             "a second name for the speech service: %r" % phrase)

    def test_04f_the_voice_copy_passes_the_register_gate(self):
        """M4 RULING: PayAI's hand-maintained .po is held to the same register
        rules as pb_learn's generated content.

        pb_learn's copy goes through `tools/jargon.py` at generation time;
        this module has no generator, so the gate has to live where the
        strings do. The rules mirrored here are the ones that apply to a
        sentence a learner reads: no sentence over 28 words, no banned jargon
        term, and the two Vietnamese rulings the pb_learn gate enforces —
        `trình duyệt` as a noun (browser), and `vòng` outside its allowed
        compounds (the tier word is `cấp`).

        MIRRORED, NOT IMPORTED: `tools/jargon.py` lives in docs/ and is not
        importable from an addon. That is a real weakness — the two copies can
        drift — and the mitigation is that this list is SHORT and pinned to
        the rules, not to the vocabulary.
        """
        catalogue = _po_map(self.po_src or '')
        tree = ast.parse(self.conversation_src)
        literals = []
        for node in ast.walk(tree):
            if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                    and node.func.id == '_' and node.args
                    and isinstance(node.args[0], ast.Constant)
                    and isinstance(node.args[0].value, str)):
                literals.append(node.args[0].value)
        self.assertTrue(literals, "no translatable strings found — the scan is broken")

        # The banned-jargon subset that can plausibly appear in THIS copy.
        # Kept short on purpose: a long mirrored list drifts, and the rule
        # being enforced is "write it the way somebody says it".
        BANNED = ('utilise', 'leverage', 'facilitate', 'commence',
                  'terminate', 'in order to', 'as per', 'kindly')
        long_ones, jargon, vi_problems = [], [], []
        for english in literals:
            for text, lang in ((english, 'en'), (catalogue.get(english, ''), 'vi')):
                for sentence in re.split(r'(?<=[.!?])\s+', text or ''):
                    words = [w for w in sentence.split() if w.strip()]
                    if len(words) > 28:
                        long_ones.append((lang, len(words), sentence[:60]))
            low = english.lower()
            jargon += [t for t in BANNED if t in low]
            vi = catalogue.get(english, '')
            if re.search(r'(?<!phê )trình\s+duyệt(?!\s+web)', vi, re.I):
                vi_problems.append('trình duyệt as a noun: %r' % vi[:50])
            # `vòng` is the tier word that was ruled OUT of this program in
            # Phase 2 (`cấp` is the one). Allowed only inside the compounds
            # the ruling left standing.
            for hit in re.finditer(r'\bvòng\b', vi, re.I):
                tail = vi[hit.start():hit.start() + 20].lower()
                if not any(tail.startswith(ok) for ok in
                           ('vòng đời', 'vòng lặp', 'vòng quay')):
                    vi_problems.append('vòng outside its compounds: %r' % vi[:50])
        self.assertFalse(long_ones, "sentences over 28 words: %r" % (long_ones[:3],))
        self.assertFalse(jargon, "banned jargon in the voice copy: %r" % (jargon[:3],))
        self.assertFalse(vi_problems, "Vietnamese register: %r" % (vi_problems[:3],))

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
        for src in (self.engine_src, self.pulse_src, self.report_src):
            self.assertTrue(
                re.search(r'\[person-1\]', src),
                "a prompt no longer tells the model what the placeholders are")
