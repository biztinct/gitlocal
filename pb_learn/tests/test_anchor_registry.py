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

(4) is Payobook-specific. pb_coach's tours and PayAI were pointing at
``data-coach`` anchors years before this module existed. Two of them —
``pw-division`` and ``pw-compute`` — are genuinely shared, and the registry
owns those. Everything else in ``foreign`` belongs to somebody else and must
stay that way; a registry entry that quietly adopts one is how two modules end
up believing they are allowed to rename the same control.
"""
import json
import os
import re

from odoo.modules.module import get_module_path
from odoo.tests.common import TransactionCase, tagged

DATA_COACH_RE = re.compile(r'data-coach="([^"{}#]+)"')
ATTF_RE = re.compile(r't-attf-data-coach="([^"]*)"')
# Comments describe anchors as often as code declares them — this file's own
# header says data-coach="…". Strip commentary before scanning, or the lint
# fails on prose about itself.
JS_COMMENT_RE = re.compile(r'/\*.*?\*/|(?<!:)//[^\n]*', re.S)
XML_COMMENT_RE = re.compile(r'<!--.*?-->', re.S)

# Anchors the registry is ALLOWED to own even though a `foreign` entry also
# matches them. Everything else in anchors.json's `foreign` map is someone
# else's, and (4) below fails if the registry quietly adopts one.
#
# Two groups, for two different reasons:
#
#   pw-division / pw-compute  are pointed at by pb_coach's tour_payrun AND by
#   this module. Genuinely shared; neither may rename one alone.
#
#   the seven fs-*            were PROMOTED out of the `fs-*` wildcard in Phase
#   B1, because L5 names them and an anchor a lesson points at has to be one a
#   test can check. Six are also in pb_coach's hero_path and tour_formula, so
#   they are shared on exactly the pw-* terms; fs-simulate is in studio.xml and
#   no tour uses it. pb_learn adds NOTHING to studio.xml — promotion is a claim
#   about ownership of a name, not a change to somebody else's template.
#
#   the four dash-*           were promoted in Phase C1 on the same terms. LW is
#   hero_path's successor and names all four; hero_path itself still points at
#   dash-hero, dash-kpis and dash-formula, so those three are genuinely shared
#   and neither module may rename one alone. dash-runpayroll is the fs-simulate
#   case: in the template, named by a lesson, pointed at by no tour. pb_learn
#   adds NOTHING to pb_dashboard.xml either.
SHARED_WITH_PB_COACH = {
    'pw-division', 'pw-compute',
    'fs-config', 'fs-components', 'fs-formula', 'fs-namesletters', 'fs-deps',
    'fs-preview', 'fs-simulate',
    'dash-hero', 'dash-kpis', 'dash-formula', 'dash-runpayroll',
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
    def test_04_content_anchors_are_registered(self):
        declared = self._all_declared()
        unknown = []
        for step in self.env['learn.step'].sudo().search([]):
            for key in (step.anchor, step.moment_from, step.moment_to):
                if key and key not in declared and not self._matches_pattern(key):
                    unknown.append('%s (lesson %s step %s)'
                                   % (key, step.lesson_id.key, step.sequence))
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
            if key in SHARED_WITH_PB_COACH:
                continue
            if self._is_foreign(key):
                claimed.append('%s -> owned by %s' % (key, self.foreign.get(key, 'another module')))
        self.assertFalse(claimed,
                         "The registry claims anchors another module owns. Renaming one of "
                         "these breaks a pb_coach tour or PayAI without any test in EITHER "
                         "module noticing:\n  " + "\n  ".join(claimed))

    def test_07_shared_anchors_are_declared_shared_in_both_directions(self):
        """pw-division and pw-compute are ours AND pb_coach's.

        Written down in both places or it is written down in neither: the next
        person to touch that template needs to see both claims from either
        side.
        """
        for key in SHARED_WITH_PB_COACH:
            self.assertIn(key, self.product,
                          "%s is shared with pb_coach but the registry does not own it" % key)
            # `_is_foreign`, not a literal lookup: a foreign claim may be a
            # WILDCARD. The seven fs-* are covered by the `fs-*` entry, whose
            # description names them one by one — a literal-key assertion here
            # said they were undeclared while the registry documented them
            # perfectly well, and it could not be caught before this run because
            # there is no odoo-bin on the authoring machine.
            self.assertTrue(self._is_foreign(key),
                            "%s is owned by pb_coach too but `foreign` does not say so" % key)
