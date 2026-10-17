# -*- coding: utf-8 -*-
"""PAYAI FIX-1 — a lesson step about an optional feature shows only where it is.

P4:crit-2. The content plane is ONE file that every database serves, with no
upgrade and no restart in between. P4 added two PayAI moments to it — the Runs
lesson step "Or ask PayAI, and read its plan first" and the Approvals lesson
tip "type APPROVE" — and they reached databases where PayAI is not installed or
may not prepare/decide for the company. Learners there were taught a Do it
button and a typed word that do not exist for them.

The gate: a step carries `requires: "<feature>"` (the whole step) or
`tip_requires: "<feature>"` (only its tip); `learn.runtime.bootstrap()` answers
`features` for the reader's company; the browser drops what is off
(`content_loader.js::gateSteps`) and so does the composer's material
(`learn_intent.build_corpus(..., features=)`).

P4:link-6. The ten minutes are how long Withdraw/Undo is OFFERED, not how long
Draft or the deletion lasts. The lesson now says it the way the card does.

Most of this is pure and runs in `docs/tutorial_poc/author/tools/replay_tests.py`
with no database; the two methods that need an `env` report SKIP there.
"""
import os
import re

from odoo.modules.module import get_module_path
from odoo.tests.common import TransactionCase, tagged

from odoo.addons.pb_learn.models.learn_intent import build_corpus
from odoo.addons.pb_learn.models.learn_runtime import (
    FEATURE_ANY_COMPANY, FEATURE_LOOK_SWITCH, FEATURE_SWITCHES, gate_steps, step_shown,
)

from .common import load_content

PROSE = ('kicker', 'title', 'body', 'consequence',
         # LEARNREV P4 — a rewritten step says it in four lines, not a body.
         'look', 'means', 'affects', 'press')
ALL_ON = {k: True for k in FEATURE_SWITCHES}
ALL_OFF = {k: False for k in FEATURE_SWITCHES}

# ONECHAT OC4 — the ONE lesson step that may name PayAI without a gate. The
# helper drawer is called PayAI on every database (owner decision Q3,
# 2026-10-14), so the welcome lesson's "how to get help" step names it
# everywhere; it teaches asking and practising only. What PayAI DOES for you
# (the plan, Do it) is the next step, which carries `requires`. Listed by
# exact English title so any NEW ungated PayAI step still fails test_01.
UNGATED_PAYAI_STEPS = {('dashboard', 'PayAI is on every screen')}
# Words that would mean an ungated step promises an optional feature.
ACTING_WORDS = re.compile(r'\b(Do it|the plan|prepares?|prepared|approves?|computes?)\b')


def _en(pair):
    return (pair or {}).get('en', '') if isinstance(pair, dict) else (pair or '')


def _said(step, lang='en', fields=('body', 'look', 'means', 'affects', 'press', 'tip')):
    """Everything a step says in one language (LEARNREV P4: the four lines
    as well as a legacy body)."""
    return ' '.join((step.get(f) or {}).get(lang, '') if isinstance(step.get(f), dict) else ''
                    for f in fields)


def _lesson_steps(tree, station_key):
    station = next(s for s in tree['stations'] if s['key'] == station_key)
    return station['lessons'][0]['steps']


@tagged('post_install', '-at_install')
class TestFeatureGate(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.tree = load_content()

    # -- 1. the content: every PayAI moment is gated, with a known name ----
    def test_01_every_payai_moment_in_a_lesson_is_gated(self):
        """The finding's two steps, and any later one written the same way."""
        seen = 0
        for station in self.tree['stations']:
            for lesson in station.get('lessons') or []:
                for i, step in enumerate(lesson.get('steps') or []):
                    where = '%s step %d' % (station['key'], i)
                    if (station['key'], _en(step.get('title'))) in UNGATED_PAYAI_STEPS:
                        continue
                    if any('PayAI' in _en(step.get(f)) for f in PROSE):
                        seen += 1
                        self.assertTrue(
                            step.get('requires'),
                            "%s teaches PayAI with no `requires` — it shows on "
                            "every database, PayAI or not" % where)
                    if 'PayAI' in _en(step.get('tip')):
                        seen += 1
                        self.assertTrue(
                            step.get('requires') or step.get('tip_requires'),
                            "%s has a PayAI tip with no gate" % where)
        self.assertGreaterEqual(seen, 2, "the P4 PayAI steps are gone — "
                                "this test is no longer checking anything")

    def test_02_the_two_p4_moments_carry_the_right_switch(self):
        runs = [s for s in _lesson_steps(self.tree, 'payruns')
                if _en(s['title']).startswith('Or ask PayAI')]
        self.assertEqual(len(runs), 1)
        self.assertEqual(runs[0].get('requires'), 'payai_prepare')
        appr = [s for s in _lesson_steps(self.tree, 'approvals')
                if 'PayAI' in _en(s.get('tip'))]
        self.assertEqual(len(appr), 1)
        self.assertEqual(appr[0].get('tip_requires'), 'payai_decide')
        # Only the tip: the step itself (Approve is a signature) is for all.
        self.assertFalse(appr[0].get('requires'))

    def test_02b_the_welcome_help_step_is_split_by_the_switch(self):
        """ONECHAT OC4 (handover §10, test 4.2). LW's last step said "It
        explains — you act. It never computes a run…", false where PayAI may
        prepare work, and promised "what to do next" (the drawer's retired
        "Your next step"). Now: one step for every database, one gated."""
        steps = _lesson_steps(self.tree, 'dashboard')
        help_ = [s for s in steps if _en(s['title']) == 'PayAI is on every screen']
        self.assertEqual(len(help_), 1)
        self.assertFalse(help_[0].get('requires'))
        for f in PROSE:
            self.assertFalse(ACTING_WORDS.search(_en(help_[0].get(f))),
                             "the ungated help step promises acting: %s" % f)
        for old in ('It explains', 'what to do next', 'never computes a run'):
            self.assertNotIn(old, _said(help_[0]))
        self.assertIn('speak', _said(help_[0]))
        act = [s for s in steps if s.get('requires') == 'payai_prepare']
        self.assertEqual(len(act), 1)
        self.assertIn('Do it', _said(act[0]))
        self.assertIn('Thực hiện', _said(act[0], 'vi'))
        # The acting step follows the help step, and only it goes when off.
        self.assertEqual(steps.index(act[0]), steps.index(help_[0]) + 1)
        for feats in (None, ALL_OFF):
            shown = gate_steps(steps, feats)
            self.assertEqual(len(shown), len(steps) - 1)
            self.assertIn(help_[0], shown)
            self.assertNotIn(act[0], shown)
        self.assertEqual(gate_steps(steps, ALL_ON), steps)

    def test_02c_the_tour_step_promises_nothing_it_cannot_gate(self):
        """Scenario steps have no `requires`, so the tour's last step (it
        plays on every database) names PayAI and never "prepares the work"
        (handover §10: "else keep it without that clause")."""
        tour = next(sc for sc in self.tree['scenarios'] if sc['key'] == 'sc_welcome')
        step = next(st for st in tour['steps'] if st['key'] == 'copilot')
        self.assertNotIn('requires', step)
        for f in ('title', 'body'):
            en, vi = step[f]['en'], step[f]['vi']
            self.assertIn('PayAI', en)
            self.assertIn('PayAI', vi)
            self.assertFalse(ACTING_WORDS.search(en), en)
            self.assertNotRegex(en.lower(), r'\bhelper\b|tab (guide|ask|practice)')
        self.assertIn('speak', step['body']['en'])
        self.assertEqual(tour['name']['vi'], 'Đi một vòng Payobook')

    def test_03_every_gate_names_a_feature_the_server_answers(self):
        """A typo would hide a step on every database, silently."""
        for station in self.tree['stations']:
            for lesson in station.get('lessons') or []:
                for step in lesson.get('steps') or []:
                    for key in ('requires', 'tip_requires'):
                        if step.get(key):
                            self.assertIn(step[key], FEATURE_SWITCHES,
                                          "%s: unknown feature %r"
                                          % (station['key'], step[key]))

    def test_03b_the_generator_knows_the_same_names(self):
        """gen_learn_data.STEP_FEATURES is the authoring half of the list."""
        repo = os.path.dirname(get_module_path('pb_learn'))
        gen = os.path.join(repo, 'docs', 'tutorial_poc', 'author', 'tools',
                           'gen_learn_data.py')
        if not os.path.exists(gen):
            self.skipTest("authoring tools are not on this machine")
        with open(gen, encoding='utf-8') as fh:
            src = fh.read()
        m = re.search(r"^STEP_FEATURES = \(([^)]*)\)", src, re.M)
        self.assertTrue(m, "STEP_FEATURES left the generator")
        names = set(re.findall(r"'([a-z_]+)'", m.group(1)))
        self.assertEqual(names, set(FEATURE_SWITCHES))

    # -- 2. the gate itself (pure) ----------------------------------------
    def test_04_gate_drops_the_step_and_the_tip_when_off(self):
        runs = _lesson_steps(self.tree, 'payruns')
        appr = _lesson_steps(self.tree, 'approvals')
        for feats in (None, {}, ALL_OFF):
            shown = gate_steps(runs, feats)
            self.assertEqual(len(shown), len(runs) - 1, feats)
            self.assertFalse(any('PayAI' in _en(s['title']) for s in shown))
            shown = gate_steps(appr, feats)
            self.assertEqual(len(shown), len(appr), "the Approve step itself "
                             "must stay; only its tip goes")
            self.assertFalse(any('PayAI' in _en(s.get('tip')) for s in shown))

    def test_05_gate_keeps_both_when_on_and_never_writes_the_tree(self):
        runs = _lesson_steps(self.tree, 'payruns')
        appr = _lesson_steps(self.tree, 'approvals')
        self.assertEqual(gate_steps(runs, ALL_ON), runs)
        self.assertEqual(gate_steps(appr, ALL_ON), appr)
        gate_steps(appr, ALL_OFF)
        self.assertTrue(any('PayAI' in _en(s.get('tip')) for s in appr),
                        "gating rewrote the shared content tree")
        # One switch on, the other off: each moment follows its own switch.
        mixed = {'payai_prepare': True, 'payai_decide': False}
        self.assertEqual(len(gate_steps(runs, mixed)), len(runs))
        self.assertFalse(any('PayAI' in _en(s.get('tip'))
                             for s in gate_steps(appr, mixed)))
        self.assertTrue(step_shown({'title': 'x'}, None),
                        "an ungated step must never depend on features")

    def test_06_the_composer_material_follows_the_gate(self):
        off = build_corpus(self.tree, 'payruns', 'en_US', features=ALL_OFF)
        on = build_corpus(self.tree, 'payruns', 'en_US', features=ALL_ON)
        self.assertNotIn('Or ask PayAI', off)
        self.assertIn('Or ask PayAI', on)
        self.assertNotIn('Or ask PayAI',
                         build_corpus(self.tree, 'payruns', 'en_US'),
                         "no features answer must fail closed")

    def test_07_the_browser_applies_the_same_gate(self):
        """content_loader.js is the one funnel the Journey's lessons pass."""
        path = os.path.join(get_module_path('pb_learn'), 'static', 'src',
                            'content', 'content_loader.js')
        with open(path, encoding='utf-8') as fh:
            src = fh.read()
        body = src.split('export function composeStations(')[1].split('\n}')[0]
        self.assertIn('runtime.features', body)
        self.assertIn('gateStation(', body)
        self.assertIn('export function gateSteps(', src)
        self.assertIn('st.tip_requires', src)
        self.assertIn('step.requires', src)

    # -- 3. P4:link-6 — the ten minutes belong to the offer ----------------
    def test_08_ten_minutes_is_the_offer_not_the_draft(self):
        bad_en = re.compile(r'(Draft|draft run) for 10 minutes')
        bad_vi = re.compile(r'(Nháp|nháp) trong 10 phút')
        step = next(s for s in _lesson_steps(self.tree, 'payruns')
                    if s.get('requires') == 'payai_prepare')
        # LEARNREV P4 — the step's lines (its "It affects" says the ten
        # minutes now) and its tip, each read in both languages.
        for f in ('body', 'means', 'affects', 'tip'):
            if not isinstance(step.get(f), dict):
                continue
            self.assertFalse(bad_en.search(step[f]['en']), step[f]['en'])
            self.assertFalse(bad_vi.search(step[f]['vi']), step[f]['vi'])
        for f in ('affects', 'tip'):
            self.assertIn('10 minutes', step[f]['en'])
            self.assertIn('10 phút', step[f]['vi'])

    # -- 4. the runtime answer (needs a database) -------------------------
    def test_09_bootstrap_answers_features_for_the_company(self):
        user = self.env['res.users'].create({
            'name': 'Learn feature gate 2031',
            'login': 'learn.feature.gate.2031@example.com',
            'group_ids': [(6, 0, [self.env.ref('base.group_user').id])],
        })
        self.assertEqual(set(self.env['learn.runtime'].bootstrap()['features']),
                         set(FEATURE_SWITCHES))
        # Read as a plain internal user: every learner opens Learn, so the
        # answer must never need more than they have.
        Runtime = self.env['learn.runtime'].with_user(user)
        feats = Runtime.features()
        self.assertEqual(set(feats), set(FEATURE_SWITCHES))
        self.assertTrue(all(isinstance(v, bool) for v in feats.values()))
        company = user.company_id
        if FEATURE_LOOK_SWITCH in company._fields:
            company.sudo()[FEATURE_LOOK_SWITCH] = True
        for key, field in FEATURE_SWITCHES.items():
            if field not in company._fields:
                # The module that owns the switch is not installed: off.
                self.assertFalse(feats[key], key)
                continue
            company.sudo()[field] = False
            self.assertFalse(Runtime.features()[key], key)
            company.sudo()[field] = True
            self.assertTrue(Runtime.features()[key], key)

    def test_09b_features_agree_with_payais_own_gate(self):
        """Final review: the lesson and PayAI never disagree.

        (a) "PayAI can look" off → PayAI's chat answers no request, so no
        PayAI step or tip shows, whatever the other switches say.
        (b) Deciding is judged on the request's company: the switch on in
        ANY company the reader works in shows the "type APPROVE" tip, even
        when the top-bar company has it off."""
        company = self.env.company
        if FEATURE_LOOK_SWITCH not in company._fields:
            self.skipTest('PayAI is not installed here.')
        other = self.env['res.company'].create({'name': 'Learn feature gate other 2031'})
        user = self.env['res.users'].create({
            'name': 'Learn feature gate two companies 2031',
            'login': 'learn.feature.gate.two.2031@example.com',
            'company_id': company.id, 'company_ids': [(6, 0, [company.id, other.id])],
            'group_ids': [(6, 0, [self.env.ref('base.group_user').id])],
        })
        Runtime = self.env['learn.runtime'].with_user(user).with_company(company)
        all_on = {FEATURE_LOOK_SWITCH: True}
        all_on.update({field: True for field in FEATURE_SWITCHES.values()})
        company.sudo().write(dict(all_on, **{FEATURE_LOOK_SWITCH: False}))
        self.assertEqual(Runtime.features(), {k: False for k in FEATURE_SWITCHES})
        company.sudo().write(all_on)
        decide = [k for k in FEATURE_SWITCHES if k in FEATURE_ANY_COMPANY]
        for key in decide:
            field = FEATURE_SWITCHES[key]
            company.sudo()[field] = False
            other.sudo()[field] = False
            self.assertFalse(Runtime.features()[key], key)
            other.sudo()[field] = True
            self.assertTrue(Runtime.features()[key], key)
        for key, field in FEATURE_SWITCHES.items():
            if key in FEATURE_ANY_COMPANY:
                continue
            other.sudo()[field] = True
            company.sudo()[field] = False
            self.assertFalse(Runtime.features()[key], key)

    def test_10_the_composer_reads_the_answer(self):
        field = FEATURE_SWITCHES['payai_prepare']
        company = self.env.company
        if FEATURE_LOOK_SWITCH in company._fields:
            company[FEATURE_LOOK_SWITCH] = True
        if field in company._fields:
            company[field] = False
        corpus = self.env['learn.intent']._corpus('payruns', 'en_US')
        self.assertNotIn('Or ask PayAI', corpus)
        if field in company._fields:
            company[field] = True
            corpus = self.env['learn.intent']._corpus('payruns', 'en_US')
            self.assertIn('Or ask PayAI', corpus)
