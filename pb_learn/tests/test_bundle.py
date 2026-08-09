# -*- coding: utf-8 -*-
"""The bundle: completeness, bilingual parity, and no unresolved tokens."""
import re

from odoo.tests.common import TransactionCase, tagged

TOKEN_RE = re.compile(r"\{\{([a-zA-Z][a-zA-Z0-9_]*)\}\}")

# Strings that are legitimately identical in both languages. Proper nouns and
# acronyms — anything added here must be a name or an abbreviation, never a
# sentence. A sentence in this set is a translation gap being papered over.
SAME_IN_BOTH = {
    "Payobook", "BHXH", "BHYT", "BHTN", "Hoa Sen Retail Co.", "Hà Nội",
    "TPHCM", "F&B", "HOASEN_RETAIL_END", "Excel", "SFTP", "Zoho People",
}

# Subtrees that are FACTS rather than prose, so "same in both languages" is the
# expected state, not a gap: a company's standard working days and its bank
# file format do not have an English and a Vietnamese version.
NOT_PROSE = (".tokens.",)


def walk_strings(node, path=""):
    """Yield (path, {en, vi}) for every bilingual leaf in the bundle."""
    if isinstance(node, dict):
        if set(node.keys()) == {"en", "vi"}:
            yield path, node
            return
        for k, v in node.items():
            yield from walk_strings(v, "%s.%s" % (path, k))
    elif isinstance(node, list):
        for i, v in enumerate(node):
            yield from walk_strings(v, "%s[%d]" % (path, i))


@tagged('post_install', '-at_install')
class TestBundle(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.bundle = cls.env['learn.station'].get_bundle()

    def test_01_shape(self):
        for key in ('version', 'stations', 'chrome', 'glossary', 'tokens', 'progress', 'user'):
            self.assertIn(key, self.bundle, "bundle is missing %s" % key)
        self.assertTrue(self.bundle['stations'], "no stations shipped")

    def test_02_every_station_has_content(self):
        thin = []
        for s in self.bundle['stations']:
            o = s['outline']
            if s['kind'] == 'lesson':
                if not s['lessons'] or not s['lessons'][0]['steps']:
                    thin.append('%s: kind=lesson but no steps' % s['key'])
            # An outline with no "what" is a node on the map that teaches
            # nothing, which is worse than not drawing it.
            if not o['what'] or not o['why']:
                thin.append('%s: outline missing what/why' % s['key'])
        self.assertFalse(thin, "Stations with nothing to teach:\n  " + "\n  ".join(thin))

    def test_03_each_check_has_exactly_one_right_answer(self):
        bad = []
        for s in self.bundle['stations']:
            for lesson in s['lessons']:
                for q in lesson['quizzes']:
                    right = [o for o in q['options'] if o['correct']]
                    if len(right) != 1:
                        bad.append('%s: %d correct options' % (lesson['key'], len(right)))
                    for o in q['options']:
                        # Every option explains itself, right or wrong. A wrong
                        # option with no recovery text is a rejection.
                        self.assertTrue(o['feedback']['en'],
                                        "%s: an option has no explanation" % lesson['key'])
        self.assertFalse(bad, "\n  ".join(bad))

    def test_04_empty_translatables_stay_falsy(self):
        """An empty optional field must not arrive as {"en": "", "vi": ""}.

        Every optional block in the player is rendered with `field ? card : ""`,
        so a truthy-but-empty pair draws a heading with nothing under it. That
        is what shipped a blank "Before you do this" panel on steps that have
        no consequence.
        """
        empties = [path for path, pair in walk_strings(self.bundle)
                   if not (pair.get('en') or '').strip()]
        self.assertFalse(empties, "Empty strings shipped as bilingual pairs:\n  "
                                  + "\n  ".join(empties[:20]))

    def test_04b_every_chrome_string_is_bilingual(self):
        """A chrome value that arrives as a bare string never got zipped.

        The parity check below cannot see this: it walks {en, vi} pairs, so a
        value that never became a pair is invisible to it. That is how three
        labels whose names collide with structural keys — required, correct,
        after — shipped as English beside translated neighbours.
        """
        bare = [k for k, v in self.bundle['chrome'].items()
                if isinstance(v, str) and v]
        self.assertFalse(bare, "Chrome strings that are not bilingual pairs: %s" % bare)

    def test_05_no_unresolved_tokens(self):
        tokens = self.bundle['tokens']
        leaked = []
        for path, pair in walk_strings(self.bundle):
            for lang in ('en', 'vi'):
                for key in TOKEN_RE.findall(pair.get(lang) or ""):
                    if key not in tokens:
                        leaked.append('%s [%s] -> {{%s}}' % (path, lang, key))
        self.assertFalse(leaked, "Content names tenant slots that do not exist. These render "
                                 "as the key itself to a learner:\n  " + "\n  ".join(leaked))

    def test_06_bilingual_parity(self):
        """Nothing translatable may ship as English in the Vietnamese bundle.

        This is the check that catches a missing .po entry, which otherwise
        looks completely normal to an English-speaking reviewer.
        """
        untranslated = []
        for path, pair in walk_strings(self.bundle):
            en = (pair.get('en') or "").strip()
            vi = (pair.get('vi') or "").strip()
            if not en or path.startswith(NOT_PROSE):
                continue
            if en == vi and en not in SAME_IN_BOTH:
                # Pure figures and times are the same in both languages.
                if re.fullmatch(r"[\d\s:.,%₫+\-–—/]+", en):
                    continue
                untranslated.append('%s: %s' % (path, en[:70]))
        self.assertFalse(untranslated,
                         "%d string(s) reach a Vietnamese reader in English:\n  %s"
                         % (len(untranslated), "\n  ".join(untranslated[:40])))

    def test_07_station_sidebar_links_resolve(self):
        """A station whose leaf does not exist is a dead node on the map.

        Only asserted for modules that are actually installed — a tenant
        without pb_payrun_ledgers legitimately has no Proration Audit leaf, and
        get_bundle reports that station as missing rather than pretending.
        """
        broken = []
        installed = set(self.env['ir.module.module'].sudo().search(
            [('state', '=', 'installed')]).mapped('name'))
        for station in self.env['learn.station'].sudo().search([]):
            key = station.sidebar_key
            if not key:
                continue
            module = key.split('.')[0]
            if module not in installed:
                continue
            if not self.env.ref(key, raise_if_not_found=False):
                broken.append('%s -> %s' % (station.key, key))
        self.assertFalse(broken, "Stations pointing at a sidebar leaf that no longer exists:\n  "
                                 + "\n  ".join(broken))

    def test_08_selections_use_the_callable_form(self):
        """Static Selection lists do not translate in this codebase.

        Measured, and documented in the repo's gotcha ledger. Asserted by
        reflection so a future field cannot quietly reintroduce it.
        """
        offenders = []
        models = ('learn.station', 'learn.step', 'learn.step.line', 'learn.quiz',
                  'learn.progress', 'learn.event', 'learn.mission',
                  'learn.mission.note', 'learn.intent', 'learn.intent.block')
        for name in models:
            for fname, field in self.env[name]._fields.items():
                if field.type != 'selection':
                    continue
                if not callable(field.selection):
                    offenders.append('%s.%s' % (name, fname))
        self.assertFalse(offenders,
                         "Selection fields declared as a static list — these will NOT "
                         "translate:\n  " + "\n  ".join(offenders))

    def test_09_every_station_line_has_a_label(self):
        """A line with no chrome string renders its own key as a heading.

        health_learn shipped exactly that when its selection was extended
        without the matching UI strings: two headings reading their own keys.
        The map is the first thing a learner sees, so this is not a cosmetic
        miss — and Payobook adds lines section by section, which is precisely
        when it would happen again.
        """
        chrome = self.bundle['chrome']
        missing = []
        for line in set(self.env['learn.station'].sudo().search([]).mapped('line')):
            key = 'lines.%s' % line
            value = chrome.get(key)
            if not value or not (value.get('en') if isinstance(value, dict) else value):
                missing.append(key)
        self.assertFalse(missing, "Journey lines with no heading string: %s" % missing)
