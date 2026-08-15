# -*- coding: utf-8 -*-
"""Practice missions.

The structural invariants live here rather than in ORM constraints. That was
already true — a data file created a step before its options existed, so a
constraint fired on content that was correct but not yet fully loaded — and
Phase 1a makes it the only place they CAN live: learn.mission and its four
satellites are gone, and with them `_check_full_missions_are_complete`,
`_check_one_decision` and `_check_wrong_options_recover`. Every rule those
three enforced is asserted below, over the emitted content, where it is checked
once for the product rather than once per database.
"""
import json
import os
import re

from odoo.modules.module import get_module_path
from odoo.tests.common import TransactionCase, tagged

from .common import load_content, one

TOKEN_RE = re.compile(r"\{\{([a-zA-Z][a-zA-Z0-9_]*)\}\}")


@tagged('post_install', '-at_install')
class TestMission(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Content = cls.env['learn.content']
        cls.content = load_content()
        cls.missions = cls.content['missions']
        cls.full = [m for m in cls.missions if m['kind'] == 'full']
        cls.live = [m for m in cls.missions if m['kind'] == 'live']

    @staticmethod
    def _blobs(mission, lang):
        """Every prose leaf a mission renders, in one language."""
        out = [one(mission.get(f), lang) for f in
               ('summary', 'outline_note')]
        out += [one(mission['consequence'].get(f), lang)
                for f in ('title', 'scope', 'reversible', 'verify')]
        out += [one(mission['anomaly'].get(f), lang) for f in ('title', 'body')]
        for step in mission['steps']:
            out += [one(step.get(f), lang) for f in ('instruction', 'detail', 'hint')]
            for opt in step['options']:
                out += [one(opt.get(f), lang) for f in ('label', 'recovery')]
        out += [one(n, lang) for n in mission['did'] + mission['check']]
        return out

    def test_01_flagship_missions_exist(self):
        self.assertTrue(self.missions, "no missions shipped")
        self.assertGreaterEqual(len(self.full), 2,
                                "fewer than two full missions — the content plan ships m1 and m2")

    def test_02_every_decision_has_exactly_one_right_answer(self):
        bad = []
        for m in self.full:
            for step in m['steps']:
                if not step['is_decision']:
                    # The inverse half of the retired ORM constraint: options
                    # on a step that is not a decision are options nothing can
                    # ever render.
                    if step['options']:
                        bad.append('%s/%s has options but is not a decision'
                                   % (m['key'], step['key']))
                    continue
                right = [o for o in step['options'] if o['correct']]
                if len(step['options']) < 2:
                    bad.append('%s/%s: %d options'
                               % (m['key'], step['key'], len(step['options'])))
                if len(right) != 1:
                    bad.append('%s/%s: %d correct' % (m['key'], step['key'], len(right)))
        self.assertFalse(bad, "\n  ".join(bad))

    def test_03_every_wrong_option_recovers_in_both_languages(self):
        """A wrong choice met with silence is a rejection.

        Checked in both languages: a recovery that exists only in English
        rejects the Vietnamese reader, which is the harder failure to notice.
        """
        bad = []
        for m in self.full:
            for step in m['steps']:
                for opt in step['options']:
                    if opt['correct']:
                        continue
                    for lang in ('en', 'vi'):
                        if not one(opt['recovery'], lang).strip():
                            bad.append('%s/%s/%s [%s]'
                                       % (m['key'], step['key'], opt['key'], lang))
        self.assertFalse(bad, "Wrong options with no way back:\n  " + "\n  ".join(bad))

    def test_04_full_missions_intercept_their_risky_step(self):
        """The consequence card is the mission's whole reason for existing on a
        practice surface: the learner meets the cost BEFORE the action."""
        for m in self.full + self.live:
            if m['kind'] == 'full':
                self.assertTrue([s for s in m['steps'] if s['is_consequence']],
                                "%s has no intercepted step" % m['key'])
            # A live mission is held to the consequence card too, and more
            # strictly in spirit: a fixture mission's worst outcome is a wrong
            # answer and a live one's is a real record.
            for f in ('title', 'scope', 'reversible', 'verify'):
                self.assertTrue(one(m['consequence'][f]).strip(),
                                "%s consequence card is missing %s" % (m['key'], f))

    def test_05_full_missions_seed_exactly_one_anomaly(self):
        for m in self.full:
            self.assertTrue(one(m['anomaly']['title']).strip(),
                            "%s has no anomaly title" % m['key'])
            self.assertTrue(one(m['anomaly']['body']).strip(),
                            "%s has no anomaly" % m['key'])
        # A LIVE mission is deliberately NOT held to one: a seeded anomaly is a
        # fact about a fixture, and live data has whatever it has.

    def test_06_full_missions_end_on_an_undo(self):
        """Reversibility is taught by DOING it once, not by being told."""
        for m in self.full:
            self.assertTrue([s for s in m['steps'] if s['is_undo']],
                            "%s never demonstrates the reversal" % m['key'])

    def test_07_debrief_has_both_halves(self):
        for m in self.full:
            self.assertTrue(m['did'], "%s debrief does not say what you did" % m['key'])
            self.assertTrue(m['check'],
                            "%s debrief has no before-you-do-this-for-real list" % m['key'])

    def test_08_every_target_is_a_registered_anchor(self):
        base = get_module_path('pb_learn')
        with open(os.path.join(base, 'static/src/anchors.json'), encoding='utf-8') as fh:
            reg = json.load(fh)
        declared = set(reg['product']) | set(reg['practice'])
        patterns = tuple(reg['pattern'])
        unknown = []
        for m in self.missions:
            for step in m['steps']:
                t = (step['target'] or '').strip()
                if t and t not in declared and not t.startswith(patterns):
                    unknown.append('%s/%s -> %s' % (m['key'], step['key'], t))
        self.assertFalse(unknown, "Mission steps pointing at unregistered anchors:\n  "
                                  + "\n  ".join(unknown))

    def test_09_no_unresolved_tokens(self):
        tokens = self.env['learn.tenant.override'].resolved_tokens()
        leaked = []
        for lang in ('en', 'vi'):
            for m in self.missions:
                for b in self._blobs(m, lang):
                    for key in TOKEN_RE.findall(b or ''):
                        if key not in tokens:
                            leaked.append('%s [%s] {{%s}}' % (m['key'], lang, key))
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

        got_clean = self.env(user=clean)['learn.confidence'].award(m['key'], False)
        got_messy = self.env(user=messy)['learn.confidence'].award(m['key'], True)
        self.assertGreater(got_clean, got_messy,
                           "being talked out of a mistake scores the same as never making it")
        self.assertEqual(
            self.env(user=clean)['learn.confidence'].my_scores()[m['confidence_key']],
            got_clean)
        # And one learner's score is invisible to another.
        self.assertNotIn(m['confidence_key'],
                         {k: v for k, v in
                          self.env(user=messy)['learn.confidence'].my_scores().items()
                          if v == got_clean})
        # An unknown mission awards nothing rather than creating a score for a
        # competence the content does not declare.
        self.assertFalse(
            self.env(user=clean)['learn.confidence'].award('not_a_mission', False))

    def test_11_mission_progress_is_namespaced(self):
        """Missions and stations share one progress map, so the frontend has one
        shape to read. The `mission:` prefix is what keeps them apart."""
        Users = self.env['res.users'].with_context(no_reset_password=True)
        user = Users.create({'name': 'Prog Run', 'login': 'mission_prog_test',
                             'group_ids': [(6, 0, [self.env.ref('base.group_user').id])]})
        env = self.env(user=user)
        m = self.full[0]
        key = 'mission:' + m['key']
        self.assertTrue(env['learn.progress'].record(key, {'state': 'done'}))
        self.assertEqual(env['learn.progress'].my_progress()[key]['state'], 'done')
        # An unknown mission is refused rather than silently creating a row.
        # The foreign key used to do this; `_declared` asks the content plane.
        self.assertFalse(env['learn.progress'].record('mission:not_a_mission',
                                                      {'state': 'done'}))
        self.assertFalse(env['learn.progress'].record('not_a_station',
                                                      {'state': 'done'}))

    def test_12_missions_never_call_a_product_method(self):
        """A practice surface whose actions have real consequences is not a
        practice surface. The mission runner may only touch learner state."""
        path = os.path.join(get_module_path('pb_learn'),
                            'static/src/journey/journey.js')
        with open(path, encoding='utf-8') as fh:
            src = fh.read()
        # CODE only: a docstring showing `orm.call("literal"` as an example
        # defeated this scan on the deploy clone — 10th occurrence of the
        # family; the rule is in the ledger.
        src = re.sub(r'/\*.*?\*/', '', src, flags=re.S)
        src = re.sub(r'(?<!:)//[^\n]*', '', src)
        calls = set(re.findall(r'orm\.call\(\s*"([a-z_.]+)"', src))
        allowed = {'learn.runtime', 'learn.progress', 'learn.event', 'learn.confidence'}
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
        live = self.live
        self.assertTrue(live, "the live capstone content is missing")

        Users = self.env['res.users'].with_context(no_reset_password=True)
        outsider = Users.create({'name': 'Not A Prospect', 'login': 'live_outsider_test',
                                 'group_ids': [(6, 0, [self.env.ref('base.group_user').id])]})
        env = self.env(user=outsider)
        self.assertFalse(env['learn.live'].gate_open(),
                         "a non-demo user was told live missions are open to them")
        step = next((s for s in live[0]['steps'] if s['check_key']), None)
        self.assertTrue(step, "the live capstone has no server-checked step")
        res = env['learn.live'].live_check(live[0]['key'], step['key'])
        self.assertFalse(res['ok'], "a non-demo session passed a live check")
        for lang in ('en', 'vi'):
            self.assertTrue((res['note'] or {}).get(lang),
                            "the refusal says nothing in %s" % lang)

        # THE OTHER HALF OF THE GATE, and the half a group check alone would
        # miss: the demo GROUP is not enough, the active company has to be the
        # demo company too. Without this a customer tenant that had installed
        # pb_demo and handed somebody the group would run live missions against
        # its own payroll records.
        demo_group = self.env.ref('pb_demo.group_payobook_demo',
                                  raise_if_not_found=False)
        if demo_group:
            other = self.env['res.company'].create({'name': 'Not The Demo Co'})
            grouped = Users.create({
                'name': 'Grouped Elsewhere', 'login': 'live_wrongco_test',
                'company_id': other.id, 'company_ids': [(6, 0, [other.id])],
                'group_ids': [(6, 0, [self.env.ref('base.group_user').id,
                                      demo_group.id])]})
            env2 = self.env(user=grouped)
            self.assertFalse(env2['learn.live'].gate_open(),
                             "the demo group alone opened live missions in a "
                             "company that is not the demo company")
            res2 = env2['learn.live'].live_check(live[0]['key'], step['key'])
            self.assertFalse(res2['ok'],
                             "a demo-group user in another company passed a live check")

    def test_12c_a_fixture_mission_can_never_be_checked_on_the_server(self):
        """The inverse isolation, and it matters as much as the gate.

        A fixture mission runs on a JavaScript replica with no server behind
        it. The moment one of its steps could ask the database a question it
        has stopped being a practice surface — so live_check refuses a
        non-live mission by name, whoever is asking.
        """
        for m in self.full:
            step = m['steps'][0]
            res = self.env['learn.live'].live_check(m['key'], step['key'])
            self.assertFalse(res['ok'],
                             "%s is a fixture mission and the server answered a check "
                             "for it" % m['key'])
            self.assertIn('practice mission', res['note']['en'],
                          "%s was refused for the wrong reason" % m['key'])
        # And a step nobody wrote is refused by name rather than by silence.
        unknown = self.env['learn.live'].live_check(self.full[0]['key'], 'no_such_step')
        self.assertFalse(unknown['ok'])

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
        for m in self.live:
            for step in m['steps']:
                check = step['check_key']
                if check and check not in LIVE_PREDICATES:
                    bad.append('%s/%s -> no predicate %s'
                               % (m['key'], step['key'], check))
                if check and step['is_ack']:
                    bad.append('%s/%s is both checked and acked'
                               % (m['key'], step['key']))
                if step['options']:
                    bad.append('%s/%s is a live step with decision options'
                               % (m['key'], step['key']))
        self.assertFalse(bad, "Live steps that cannot complete:\n  " + "\n  ".join(bad))

    def test_12e_a_live_mission_never_asserts_an_amount(self):
        """Live numbers belong to the learner, not to us.

        Every figure in a real run is on the screen in front of them and
        changes the next time the demo world is regenerated. A mission that
        printed one would be confidently wrong on a schedule — so no live
        step, note or consequence field may carry a money-shaped number.
        """
        # The separators are what make a number money-shaped, so they have to
        # be inside the pattern — but a TRAILING one is punctuation, not part
        # of the figure. Without the strip, "June 2026," matched as "2026,":
        # five characters, and the sentence naming the demo world's open month
        # read as an asserted amount. Strip the trailing separators, then a
        # number is money-shaped only if five or more characters survive —
        # which a four-digit year never is, and "12,500,000" always is.
        money = re.compile(r'\d[\d.,]{4,}')
        offenders = []
        for m in self.live:
            for lang in ('en', 'vi'):
                for b in self._blobs(m, lang):
                    for hit in money.findall(b or ''):
                        figure = hit.rstrip('.,')
                        if len(figure) < 5:
                            continue
                        offenders.append('%s [%s] %s' % (m['key'], lang, figure))
        self.assertFalse(offenders, "A live mission asserts amounts:\n  "
                                    + "\n  ".join(sorted(set(offenders))))

    def test_15_the_live_surface_only_reads(self):
        """The capstone's safety argument, asserted as an ABSENCE.

        Same shape as contract.json::coach-answers-from-writing-only, and for the same reason:
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
        allowed = {'learn.runtime', 'learn.live', 'learn.progress', 'learn.confidence'}
        self.assertFalse(calls - allowed,
                         "The live runner calls models outside the learning spine: %s"
                         % (calls - allowed))
        # And the poll is bounded: one interval, one place it is cleared.
        self.assertIn('POLL_MS = 10000', src, "the poll interval is not 10s")
        self.assertIn('_stopPolling', src, "the runner never stops polling")

    def test_13_mission_lines_exist_on_the_map(self):
        """A mission on a line the Journey does not draw is unreachable.

        This used to compare two Selection lists on two models, which could
        drift apart silently. There is one vocabulary now — whatever the content
        declares — so what is left to check is the half that still matters: a
        mission on a line no STATION uses draws under a heading with nothing
        else beneath it, and `test_bundle::test_09` is what proves every line
        in play has a heading string at all.
        """
        station_lines = {s['line'] for s in self.content['stations']}
        mission_lines = {m['line'] for m in self.missions}
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
        section_of = {s['key']: s['section'] for s in self.content['stations']}
        # The import wizard is a sub-screen of the Import station and has no
        # station of its own, so it borrows its owner's section.
        section_of.setdefault('importwizard', section_of.get('import'))
        stray = []
        for m in self.full:
            navs = [s['nav'] for s in m['steps'] if s['nav']]
            if not navs:
                continue
            unknown = [n for n in navs if n not in section_of]
            if unknown:
                stray.append('%s navigates to screens with no station: %s'
                             % (m['key'], unknown))
                continue
            sections = {section_of[n] for n in navs}
            if len(sections) > 1:
                stray.append('%s spans %s' % (m['key'], sorted(sections)))
        self.assertFalse(stray, "Missions that wander into another section:\n  "
                                + "\n  ".join(stray))
