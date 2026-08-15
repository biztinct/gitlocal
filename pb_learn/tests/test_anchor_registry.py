# -*- coding: utf-8 -*-
"""The anchor lint.

Run as an Odoo test rather than a bespoke CI script, deliberately: it then
executes in the harness this repo already runs, so it cannot quietly stop
running the way a separate script does after the first person forgets it.

Four directions, because a one-way check rots from the other side:

 1. every registered anchor exists where the registry says it does
 2. every anchor the CONTENT names is registered
 3. every ``data-coach`` found in a scanned file is registered, or explicitly
    whitelisted as belonging to another module
 4. the registry never silently claims an anchor another module owns

(3) is the one that catches a typo: an unregistered anchor is nearly always a
misspelling of a real one, and without this direction it just silently points
at nothing.

(4) is Payobook-specific. Formula Studio, the payroll-formula wizards and PayAI
were all pointing at ``data-coach`` anchors years before this module existed.
Seven of Formula Studio's are PROMOTED — the registry owns the NAME while that
module owns the template — and everything else in ``foreign`` belongs to
somebody else and must stay that way; a registry entry that quietly adopts one
is how two modules end up believing they are allowed to rename the same
control.
"""
import json
import os
import re

from odoo.modules.module import get_module_path
from odoo.tests.common import TransactionCase, tagged

from .common import load_content, lesson_steps, mission_steps, scenario_steps

DATA_COACH_RE = re.compile(r'data-coach="([^"{}#]+)"')
ATTF_RE = re.compile(r't-attf-data-coach="([^"]*)"')
# Comments describe anchors as often as code declares them — this file's own
# header says data-coach="…". Strip commentary before scanning, or the lint
# fails on prose about itself.
JS_COMMENT_RE = re.compile(r'/\*.*?\*/|(?<!:)//[^\n]*', re.S)
XML_COMMENT_RE = re.compile(r'<!--.*?-->', re.S)

# Anchors the registry owns OUTRIGHT that a `foreign` WILDCARD still matches.
#
# All seven are in pb_formula_studio's studio.xml, all seven are named by L5 or
# by the sc_formula scenario, and pb_learn adds NOTHING to that template —
# promotion is a claim about ownership of a NAME, never an edit to somebody
# else's file. They have to be listed because the `fs-*` wildcard cannot be
# narrowed without copying pb_formula_studio's entire anchor set into this file,
# which would be a second, stale copy of their template.
#
# THE OTHER SET IS GONE. Until LEARNOS Phase 1b there was a `SHARED_WITH_PB_COACH`
# beside this one, meaning "the guided-tour module points at this too, so
# neither of us may rename it alone", and it held pw-division, pw-compute, three
# dash-* and six of the seven below. That module has been deleted and its tours
# are pb_learn scenarios now, so every one of those names has exactly one
# claimant and the `foreign` entries recording the shared claim went with it. A
# set whose name has stopped matching its contents is one nobody can reason
# about (ledger, Phase C review round 2) — so it was removed rather than
# renamed to mean something it never said.
PROMOTED_FROM_WILDCARD = {
    'fs-config', 'fs-components', 'fs-formula', 'fs-namesletters', 'fs-deps',
    'fs-preview', 'fs-simulate',
}


def _read(module_and_path):
    module, _, rel = module_and_path.partition('/')
    base = get_module_path(module)
    if not base:
        return None
    path = os.path.join(base, rel)
    if not os.path.exists(path):
        return None
    with open(path, encoding='utf-8') as fh:
        return fh.read()


@tagged('post_install', '-at_install')
class TestAnchorRegistry(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        raw = _read('pb_learn/static/src/anchors.json')
        cls.registry_json = json.loads(raw)
        cls.product = cls.registry_json['product']
        cls.patterns = cls.registry_json['pattern']
        cls.practice = cls.registry_json['practice']
        cls.foreign = cls.registry_json['foreign']
        cls.scan = cls.registry_json['scan']
        cls.content = load_content()

    # -- helpers ---------------------------------------------------------
    def _all_declared(self):
        return set(self.product) | set(self.practice)

    def _matches_pattern(self, key):
        return any(key.startswith(p) for p in self.patterns)

    def _is_foreign(self, key):
        """A whitelisted anchor owned elsewhere. Wildcard entries end in '*'."""
        for owned in self.foreign:
            if owned.endswith('*'):
                if key.startswith(owned[:-1]):
                    return True
            elif key == owned:
                return True
        return False

    # -- 1. every registered anchor exists where it says it does ----------
    def test_01_product_anchors_exist_in_templates(self):
        missing = []
        for key, spec in self.product.items():
            text = _read(spec['file'])
            if text is None:
                missing.append('%s -> file not found: %s' % (key, spec['file']))
            elif 'data-coach="%s"' % key not in text:
                missing.append('%s -> not in %s' % (key, spec['file']))
        self.assertFalse(missing, "Registered anchors the product template no longer has.\n"
                                  "A control was renamed or removed and the content still "
                                  "points at it:\n  " + "\n  ".join(missing))

    def test_01b_shared_anchors_name_every_screen_they_serve(self):
        """pb_payrun_ledgers renders three screens from one template.

        An entry that names one screen while the template serves three is a
        promise the Coach cannot keep: it would offer Retro's questions on the
        Proration Audit, from a registry that looked correct.
        """
        bad = []
        for key, spec in self.product.items():
            screens = spec['screen']
            if spec.get('shared'):
                if not isinstance(screens, list) or len(screens) < 2:
                    bad.append('%s is marked shared but names %r' % (key, screens))
            elif isinstance(screens, list):
                bad.append('%s names several screens without shared: true' % key)
        self.assertFalse(bad, "\n  ".join(bad))

    def test_02_pattern_anchors_are_emitted(self):
        """A pattern is emitted per record, so there is no literal to find.

        Two sources: a product template emits it with t-attf-data-coach, and
        the practice replica emits it from a template literal. Both are checked
        — a pattern nobody emits is an anchor the content can never reach.

        Phase A declares no patterns (see anchors.json on pk-card), so this
        passes vacuously. It stays because the FIRST per-record anchor added
        without an emitter is the one that would ship pointing at nothing.
        """
        missing = []
        replica_blob = "".join(_read(f) or "" for f in self.scan['replica'])
        for prefix, spec in self.patterns.items():
            if spec.get('replica'):
                if 'data-coach="%s' % prefix not in replica_blob:
                    missing.append('%s -> the replica does not emit it' % prefix)
                continue
            text = _read(spec['file'])
            if text is None:
                missing.append('%s -> file not found: %s' % (prefix, spec['file']))
                continue
            emitted = ATTF_RE.findall(text)
            if not any(e.startswith(prefix) for e in emitted):
                missing.append('%s -> no t-attf-data-coach emits it in %s'
                               % (prefix, spec['file']))
        self.assertFalse(missing, "Pattern anchors nothing emits:\n  " + "\n  ".join(missing))

    def test_03_practice_anchors_exist_in_replica(self):
        blob = "".join(_read(f) or "" for f in self.scan['replica'])
        missing = [k for k in self.practice if '"%s"' % k not in blob and k not in blob]
        self.assertFalse(missing, "Practice-only anchors the replica no longer draws:\n  "
                                  + "\n  ".join(missing))

    # -- 2. every anchor the content names is registered ------------------
    # LESSONS AND MISSIONS ONLY. A lesson runs over the replica and a mission
    # points at the replica's controls, so both may only name something this
    # module owns or draws. Scenarios are the exception and have their own
    # direction in test_09 — they walk the real product, including three other
    # modules' templates, where pointing is not owning.
    def test_04_content_anchors_are_registered(self):
        declared = self._all_declared()
        unknown = []
        for lesson, step in lesson_steps(self.content):
            for key in (step['anchor'], step['moment_from'], step['moment_to']):
                if key and key not in declared and not self._matches_pattern(key):
                    unknown.append('%s (lesson %s step %s)'
                                   % (key, lesson['key'], step['title']['en'][:30]))
        # Missions point at controls too, and this direction was blind to them.
        for mission, mstep in mission_steps(self.content):
            key = mstep['target']
            if key and key not in declared and not self._matches_pattern(key):
                unknown.append('%s (mission %s step %s)'
                               % (key, mission['key'], mstep['key']))
        self.assertFalse(unknown, "Content points at anchors nothing registers:\n  "
                                  + "\n  ".join(sorted(set(unknown))))

    # -- 3. every anchor in a scanned file is registered -------------------
    def test_05_no_stray_anchors(self):
        declared = self._all_declared()
        stray = []
        for rel in self.scan['templates'] + self.scan['replica']:
            text = _read(rel)
            if text is None:
                continue
            text = XML_COMMENT_RE.sub('', JS_COMMENT_RE.sub('', text))
            for key in DATA_COACH_RE.findall(text):
                # Skip the replica's template-literal interpolations — those
                # are fixture-driven and land as pattern keys at runtime.
                if '$' in key:
                    continue
                if key in declared or self._matches_pattern(key) or self._is_foreign(key):
                    continue
                stray.append('%s in %s' % (key, rel))
        self.assertFalse(stray, "Anchors in a template that the registry does not declare. "
                                "Usually a typo of a real one — if it belongs to another "
                                "module, whitelist it under `foreign`:\n  "
                                + "\n  ".join(sorted(set(stray))))

    # -- 4. the registry does not adopt another module's anchor ------------
    def test_06_registry_does_not_claim_a_foreign_anchor(self):
        claimed = []
        for key in self._all_declared():
            if key in PROMOTED_FROM_WILDCARD:
                continue
            if self._is_foreign(key):
                claimed.append('%s -> owned by %s' % (key, self.foreign.get(key, 'another module')))
        self.assertFalse(claimed,
                         "The registry claims anchors another module owns. Renaming one of "
                         "these breaks Formula Studio, a payroll wizard or PayAI without any "
                         "test in EITHER "
                         "module noticing:\n  " + "\n  ".join(claimed))

    # -- 5. an anchor is either used or declared unused ---------------------
    def test_08_every_product_anchor_is_referenced_or_reserved(self):
        """The convention added in the Phase C review, in both directions.

        Phase C1 anchored whole REGIONS of seven cockpits in one pass, because
        the alternative is a second edit to somebody else's template for every
        lesson written afterwards — and each of those is a chance for a tidy-up
        to delete an attribute nothing over there reads. So an anchor may be
        laid ahead of its content, and the registry has to SAY SO: `reserved`
        is the difference between "not written yet" and "a typo nobody caught".

        The flag comes off when content arrives. A reserved anchor that is now
        referenced fails just as loudly as an unreferenced one that is not
        reserved — otherwise the flag decays into a blanket exemption, which is
        the same as not having the check.
        """
        referenced = set()
        for _lesson, step in lesson_steps(self.content):
            referenced |= {a for a in (step['anchor'], step['moment_from'],
                                       step['moment_to']) if a}
        for intent in self.content['intents']:
            referenced |= {a for a in intent['show_me'] if a}
            for block in intent['blocks']:
                for istep in block['steps']:
                    if istep['anchor']:
                        referenced.add(istep['anchor'])
        # A MISSION STEP'S TARGET is a content reference too, and no test in
        # this module counted it — which is how `pw-result` and `st-effective`
        # read as unreferenced while m1 and m4 have been pointing at them since
        # Phase A. Found by executing this test rather than by writing it.
        for _mission, mstep in mission_steps(self.content):
            if mstep['target']:
                referenced.add(mstep['target'])
        # A SCENARIO STEP'S ANCHOR is a content reference on exactly the same
        # terms, and it arrived with the six ported tours in Phase 1b. Without
        # this loop a product anchor could be reserved AND spotlit by a
        # walkthrough at the same time, which is the flag decaying into an
        # exemption nobody granted — the failure the test's other direction
        # exists to prevent.
        for _scenario, step in scenario_steps(self.content):
            if step.get('anchor'):
                referenced.add(step['anchor'])

        undeclared, stale = [], []
        for key, spec in self.product.items():
            is_reserved = bool(spec.get('reserved'))
            if key in referenced and is_reserved:
                stale.append(key)
            elif key not in referenced and not is_reserved:
                undeclared.append(key)
        self.assertFalse(undeclared,
                         "Anchors no content points at and the registry does not declare "
                         "reserved. Either write the content, or say it is coming with "
                         '"reserved": true:\n  ' + "\n  ".join(sorted(undeclared)))
        self.assertFalse(stale,
                         "Anchors marked reserved that content now names. Drop the flag — "
                         "a reserved marker that survives its content is an exemption "
                         "nobody decided to grant:\n  " + "\n  ".join(sorted(stale)))

    def test_07_promoted_anchors_are_still_inside_their_wildcard(self):
        """The seven fs-* are ours by NAME and pb_formula_studio's by template.

        Both halves have to stay true or the exemption stops meaning anything:
        the registry has to own the key (`product`), and a `foreign` wildcard
        has to still match it — otherwise the name has left the family and the
        exemption is protecting nothing.

        `_is_foreign`, not a literal lookup: the claim is a WILDCARD. A
        literal-key assertion here reported seven perfectly-documented anchors
        as undeclared for two phases, and could not be seen because there is no
        odoo-bin on the authoring machine.
        """
        for key in PROMOTED_FROM_WILDCARD:
            self.assertIn(key, self.product,
                          "%s is promoted but the registry does not own it" % key)
            self.assertTrue(self._is_foreign(key),
                            "%s is exempted from the foreign check but no foreign "
                            "entry matches it — drop it from PROMOTED_FROM_WILDCARD"
                            % key)

    # -- 6. scenarios point at controls that are DECLARED somewhere ---------
    def test_09_scenario_anchors_are_declared(self):
        """A scenario step may point at an anchor this module does not own.

        Three of the six ported walkthroughs cross into pb_formula_studio's grid
        and pb_hr_payroll_formula's wizards, which are other people's templates
        — pointing is not owning, and requiring a `product` entry for each would
        make pb_learn claim the right to rename controls in four modules.

        What IS required is that the name is declared in SOME block, so a typo
        is a failure rather than a spotlight on nothing. The generator enforces
        the same rule at authoring time; this is the same comparison after
        generation, which is where a hand-edited content plane would show up.
        """
        unknown = []
        for scenario, step in scenario_steps(self.content):
            key = step.get('anchor')
            if not key:
                continue
            if (key in self._all_declared() or self._matches_pattern(key)
                    or self._is_foreign(key)):
                continue
            unknown.append('%s (scenario %s step %s)'
                           % (key, scenario['key'], step['key']))
        self.assertFalse(unknown,
                         "Scenario steps point at anchors nothing declares:\n  "
                         + "\n  ".join(sorted(set(unknown))))
