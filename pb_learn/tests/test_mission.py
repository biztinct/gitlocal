# -*- coding: utf-8 -*-
"""Practice missions.

The structural invariants live here rather than in ORM constraints, because a
data file creates a step before its options exist — a constraint would fire on
content that is correct but not yet fully loaded. These see the finished data.
"""
import json
import os
import re

from odoo.modules.module import get_module_path
from odoo.tests.common import TransactionCase, tagged

TOKEN_RE = re.compile(r"\{\{([a-zA-Z][a-zA-Z0-9_]*)\}\}")


@tagged('post_install', '-at_install')
class TestMission(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Mission = cls.env['learn.mission']
        cls.missions = cls.Mission.search([])
        cls.full = cls.missions.filtered(lambda m: m.kind == 'full')

    def test_01_flagship_missions_exist(self):
        self.assertTrue(self.missions, "no missions shipped")
        self.assertGreaterEqual(len(self.full), 2,
                                "fewer than two full missions — the content plan ships m1 and m2")

    def test_02_every_decision_has_exactly_one_right_answer(self):
        bad = []
        for m in self.full:
            for step in m.step_ids.filtered('is_decision'):
                right = step.option_ids.filtered('is_correct')
                if len(step.option_ids) < 2:
                    bad.append('%s/%s: %d options' % (m.key, step.key, len(step.option_ids)))
                if len(right) != 1:
                    bad.append('%s/%s: %d correct' % (m.key, step.key, len(right)))
        self.assertFalse(bad, "\n  ".join(bad))

    def test_03_every_wrong_option_recovers_in_both_languages(self):
        """A wrong choice met with silence is a rejection.

        Checked in both languages: a recovery that exists only in English
        rejects the Vietnamese reader, which is the harder failure to notice.
        """
        bad = []
        for m in self.full:
            for step in m.step_ids:
                for opt in step.option_ids.filtered(lambda o: not o.is_correct):
                    for lang in ('en_US', 'vi_VN'):
                        text = opt.with_context(lang=lang).recovery
                        if not (text or '').strip():
                            bad.append('%s/%s/%s [%s]' % (m.key, step.key, opt.key, lang))
        self.assertFalse(bad, "Wrong options with no way back:\n  " + "\n  ".join(bad))

    def test_04_full_missions_intercept_their_risky_step(self):
        """The consequence card is the mission's whole reason for existing on a
        practice surface: the learner meets the cost BEFORE the action."""
        for m in self.full:
            self.assertTrue(m.step_ids.filtered('is_consequence'),
                            "%s has no intercepted step" % m.key)
            for f in ('consequence_title', 'consequence_scope',
                      'consequence_reversible', 'consequence_verify'):
                self.assertTrue((m[f] or '').strip(),
                                "%s consequence card is missing %s" % (m.key, f))

    def test_05_full_missions_seed_exactly_one_anomaly(self):
        for m in self.full:
            self.assertTrue((m.anomaly_title or '').strip(), "%s has no anomaly title" % m.key)
            self.assertTrue((m.anomaly_body or '').strip(), "%s has no anomaly" % m.key)

    def test_06_full_missions_end_on_an_undo(self):
        """Reversibility is taught by DOING it once, not by being told."""
        for m in self.full:
            self.assertTrue(m.step_ids.filtered('is_undo'),
                            "%s never demonstrates the reversal" % m.key)

    def test_07_debrief_has_both_halves(self):
        for m in self.full:
            self.assertTrue(m.note_ids.filtered(lambda n: n.kind == 'did'),
                            "%s debrief does not say what you did" % m.key)
            self.assertTrue(m.note_ids.filtered(lambda n: n.kind == 'check'),
                            "%s debrief has no before-you-do-this-for-real list" % m.key)

    def test_08_every_target_is_a_registered_anchor(self):
        base = get_module_path('pb_learn')
        with open(os.path.join(base, 'static/src/anchors.json'), encoding='utf-8') as fh:
            reg = json.load(fh)
        declared = set(reg['product']) | set(reg['practice'])
        patterns = tuple(reg['pattern'])
        unknown = []
        for step in self.env['learn.mission.step'].search([]):
            t = (step.target or '').strip()
            if t and t not in declared and not t.startswith(patterns):
                unknown.append('%s/%s -> %s' % (step.mission_id.key, step.key, t))
        self.assertFalse(unknown, "Mission steps pointing at unregistered anchors:\n  "
                                  + "\n  ".join(unknown))

    def test_09_no_unresolved_tokens(self):
        tokens = self.env['learn.tenant.override'].resolved_tokens()
        leaked = []
        for lang in ('en_US', 'vi_VN'):
            for m in self.Mission.with_context(lang=lang).search([]):
                blobs = [m.summary, m.outline_note, m.consequence_scope,
                         m.consequence_verify, m.anomaly_body]
                blobs += [s.instruction for s in m.step_ids]
                blobs += [s.detail for s in m.step_ids]
                blobs += [s.hint for s in m.step_ids]
                blobs += [n.body for n in m.note_ids]
                for o in self.env['learn.mission.option'].with_context(lang=lang).search(
                        [('step_id.mission_id', '=', m.id)]):
                    blobs += [o.label, o.recovery]
                for b in blobs:
                    for key in TOKEN_RE.findall(b or ''):
                        if key not in tokens:
                            leaked.append('%s [%s] {{%s}}' % (m.key, lang, key))
        self.assertFalse(leaked, "Undeclared slots in mission content:\n  "
                                 + "\n  ".join(sorted(set(leaked))))

    def test_10_a_recovery_scores_lower_than_a_clean_run(self):
        """Without this asymmetry, 'confidence' only measures completion —
        which the learner can already see as a tick."""
        Users = self.env['res.users'].with_context(no_reset_password=True)
        base = self.env.ref('base.group_user').id
        clean = Users.create({'name': 'Clean Run', 'login': 'mission_clean_test',
                              'group_ids': [(6, 0, [base])]})
        messy = Users.create({'name': 'Messy Run', 'login': 'mission_messy_test',
                              'group_ids': [(6, 0, [base])]})
        m = self.full[0]

        got_clean = self.env(user=clean)['learn.confidence'].award(m.key, False)
        got_messy = self.env(user=messy)['learn.confidence'].award(m.key, True)
        self.assertGreater(got_clean, got_messy,
                           "being talked out of a mistake scores the same as never making it")
        self.assertEqual(self.env(user=clean)['learn.confidence'].my_scores()[m.confidence_key],
                         got_clean)
        # And one learner's score is invisible to another.
        self.assertNotIn(m.confidence_key,
                         {k: v for k, v in
                          self.env(user=messy)['learn.confidence'].my_scores().items()
                          if v == got_clean})

    def test_11_mission_progress_is_namespaced(self):
        """Missions and stations share one progress map, so the frontend has one
        shape to read. The `mission:` prefix is what keeps them apart."""
        Users = self.env['res.users'].with_context(no_reset_password=True)
        user = Users.create({'name': 'Prog Run', 'login': 'mission_prog_test',
                             'group_ids': [(6, 0, [self.env.ref('base.group_user').id])]})
        env = self.env(user=user)
        m = self.full[0]
        self.assertTrue(env['learn.progress'].record('mission:' + m.key, {'state': 'done'}))
        self.assertEqual(env['learn.progress'].my_progress()['mission:' + m.key]['state'], 'done')
        # An unknown mission is refused rather than silently creating a row.
        self.assertFalse(env['learn.progress'].record('mission:not_a_mission', {'state': 'done'}))

    def test_12_missions_never_call_a_product_method(self):
        """A practice surface whose actions have real consequences is not a
        practice surface. The mission runner may only touch learner state."""
        path = os.path.join(get_module_path('pb_learn'),
                            'static/src/journey/journey.js')
        with open(path, encoding='utf-8') as fh:
            src = fh.read()
        calls = set(re.findall(r'orm\.call\(\s*"([a-z_.]+)"', src))
        allowed = {'learn.station', 'learn.progress', 'learn.event', 'learn.confidence'}
        self.assertFalse(calls - allowed,
                         "The Journey calls models outside the learning spine: %s"
                         % (calls - allowed))

    def test_12b_a_live_mission_is_refused_outside_the_demo_world(self):
        """The capstone's gate, asserted on the SERVER.

        Phase A had nothing to run, so this test asserted that no live mission
        shipped. Phase B ships one, and the property worth pinning changed with
        it: a live mission must refuse a session that is not in the demo world,
        and refuse it by NAME rather than by returning a quiet False that reads
        like "not yet".

        Asserted with a real user holding no demo group — the frontend also
        hides the mission, and that is decoration. This is the gate.
        """
        kinds = {k for k, _label in self.Mission._selection_kind()}
        self.assertIn('live', kinds, "the live capstone kind was dropped from the selection")
        live = self.missions.filtered(lambda m: m.kind == 'live')
        self.assertTrue(live, "the live capstone content is missing")

        Users = self.env['res.users'].with_context(no_reset_password=True)
        outsider = Users.create({'name': 'Not A Prospect', 'login': 'live_outsider_test',
                                 'group_ids': [(6, 0, [self.env.ref('base.group_user').id])]})
        env = self.env(user=outsider)
        self.assertFalse(env['learn.live'].gate_open(),
                         "a non-demo user was told live missions are open to them")
        step = live[0].step_ids.filtered('check')[:1]
        self.assertTrue(step, "the live capstone has no server-checked step")
        res = env['learn.mission'].live_check(live[0].key, step.key)
        self.assertFalse(res['ok'], "a non-demo session passed a live check")
        for lang in ('en', 'vi'):
            self.assertTrue((res['note'] or {}).get(lang),
                            "the refusal says nothing in %s" % lang)

    def test_12c_a_fixture_mission_can_never_be_checked_on_the_server(self):
        """The inverse isolation, and it matters as much as the gate.

        A fixture mission runs on a JavaScript replica with no server behind
        it. The moment one of its steps could ask the database a question it
        has stopped being a practice surface — so live_check refuses a
        non-live mission by name, whoever is asking.
        """
        for m in self.full:
            step = m.step_ids[:1]
            res = self.env['learn.mission'].live_check(m.key, step.key)
            self.assertFalse(res['ok'],
                             "%s is a fixture mission and the server answered a check "
                             "for it" % m.key)
            self.assertIn('practice mission', res['note']['en'],
                          "%s was refused for the wrong reason" % m.key)

    def test_12d_every_live_step_is_verified_acked_or_instructional(self):
        """A live step the learner can never complete is a dead mission.

        Three shapes and no fourth: the server answers it (`check`), the
        learner answers it (`is_ack` / the consequence card), or Next moves it
        on. What this catches is a `check` naming a predicate nothing
        implements — which renders as a step that waits forever and says
        nothing about why.
        """
        from odoo.addons.pb_learn.models.learn_live import LIVE_PREDICATES
        bad = []
        for m in self.missions.filtered(lambda x: x.kind == 'live'):
            for step in m.step_ids:
                if step.check and step.check not in LIVE_PREDICATES:
                    bad.append('%s/%s -> no predicate %s' % (m.key, step.key, step.check))
                if step.check and step.is_ack:
                    bad.append('%s/%s is both checked and acked' % (m.key, step.key))
                if step.option_ids:
                    bad.append('%s/%s is a live step with decision options' % (m.key, step.key))
        self.assertFalse(bad, "Live steps that cannot complete:\n  " + "\n  ".join(bad))

    def test_12e_a_live_mission_never_asserts_an_amount(self):
        """Live numbers belong to the learner, not to us.

        Every figure in a real run is on the screen in front of them and
        changes the next time the demo world is regenerated. A mission that
        printed one would be confidently wrong on a schedule — so no live
        step, note or consequence field may carry a money-shaped number.
        """
        money = re.compile(r'\d[\d.,]{4,}')
        offenders = []
        for m in self.missions.filtered(lambda x: x.kind == 'live'):
            for lang in ('en_US', 'vi_VN'):
                rec = m.with_context(lang=lang)
                blobs = [rec.summary, rec.consequence_scope, rec.consequence_reversible,
                         rec.consequence_verify, rec.anomaly_body]
                blobs += [s.instruction for s in rec.step_ids]
                blobs += [s.detail for s in rec.step_ids]
                blobs += [s.hint for s in rec.step_ids]
                blobs += [n.body for n in rec.note_ids]
                for b in blobs:
                    for hit in money.findall(b or ''):
                        offenders.append('%s [%s] %s' % (m.key, lang, hit))
        self.assertFalse(offenders, "A live mission asserts amounts:\n  "
                                    + "\n  ".join(sorted(set(offenders))))

    def test_15_the_live_surface_only_reads(self):
        """The capstone's safety argument, asserted as an ABSENCE.

        Same shape as contract.json::coach-cannot-act, and for the same reason:
        the promise is that nothing here acts, and the way a promise like that
        breaks is by somebody adding a convenience. The contract checker makes
        this claim at authoring time; this makes it in the test suite, so it
        holds on a server where nobody ran the checker.
        """
        path = os.path.join(get_module_path('pb_learn'), 'models/learn_live.py')
        with open(path, encoding='utf-8') as fh:
            src = fh.read()
        for token in ('.create(', '.write(', '.unlink(', 'cr.execute'):
            self.assertNotIn(token, src,
                             "learn_live.py contains %r — the live surface must only "
                             "read" % token)

    def test_16_the_live_runner_intercepts_nothing(self):
        """It instructs and observes. It does not act, and it does not block.

        Three things would change that and none of them is here: patching a
        product component, synthesising a click, or disabling a control that is
        not its own. The runner's only orm calls are to the learning spine —
        one of them read-only by construction — and its only product-facing
        gesture is a deep link the learner can ignore.
        """
        base = get_module_path('pb_learn')
        with open(os.path.join(base, 'static/src/live/live_mission.js'),
                  encoding='utf-8') as fh:
            src = fh.read()
        for token in ('patch(', '.click()', 'dispatchEvent', 'preventDefault',
                      'stopPropagation'):
            self.assertNotIn(token, src,
                             "the live runner uses %r — it must never intercept or "
                             "perform a product action" % token)
        calls = set(re.findall(r'orm\.call\(\s*"([a-z_.]+)"', src))
        allowed = {'learn.station', 'learn.intent', 'learn.mission',
                   'learn.progress', 'learn.confidence'}
        self.assertFalse(calls - allowed,
                         "The live runner calls models outside the learning spine: %s"
                         % (calls - allowed))
        # And the poll is bounded: one interval, one place it is cleared.
        self.assertIn('POLL_MS = 10000', src, "the poll interval is not 10s")
        self.assertIn('_stopPolling', src, "the runner never stops polling")

    def test_13_mission_lines_exist_on_the_map(self):
        """A mission on a line the Journey does not draw is unreachable.

        The two selections are separate fields on separate models, so they can
        drift apart silently — and the symptom is a mission that simply never
        appears rather than an error.
        """
        station_lines = {k for k, _l in self.env['learn.station']._selection_line()}
        mission_lines = {m.line for m in self.missions}
        orphans = mission_lines - station_lines
        self.assertFalse(orphans, "Missions on lines the map has no heading for: %s" % orphans)

    def test_14_a_mission_never_leaves_its_own_section(self):
        """Every step of a mission stands on a screen from its own section.

        A step with no `nav` — a decision, a consequence card — does not move
        the learner, so the runner has to hold the screen it was already on.
        In health_learn it fell back to a hard-coded screen instead, which was
        invisibly right for the missions that start there and wrong for the
        rest: a decision was asked over a screen from another section entirely.

        Asserted against the station keys rather than the runner, so it holds
        whatever the JS does — a mission that navigates outside its section is
        a content bug even when the code is right.

        Phase A has one section, so this passes trivially today. It is written
        now because the moment a second section exists, this is the bug.
        """
        section_of = {s.key: s.section
                      for s in self.env['learn.station'].sudo().search([])}
        # The import wizard is a sub-screen of the Import station and has no
        # station of its own, so it borrows its owner's section.
        section_of.setdefault('importwizard', section_of.get('import'))
        stray = []
        for m in self.full:
            navs = [s.nav for s in m.step_ids if s.nav]
            if not navs:
                continue
            unknown = [n for n in navs if n not in section_of]
            if unknown:
                stray.append('%s navigates to screens with no station: %s' % (m.key, unknown))
                continue
            sections = {section_of[n] for n in navs}
            if len(sections) > 1:
                stray.append('%s spans %s' % (m.key, sorted(sections)))
        self.assertFalse(stray, "Missions that wander into another section:\n  "
                                + "\n  ".join(stray))
