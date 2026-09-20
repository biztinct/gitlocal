# -*- coding: utf-8 -*-
"""The content plane: completeness, bilingual parity, and no unresolved tokens.

Phase 1a retarget. These assertions used to run over
`learn.station.get_bundle()`, which built the payload out of the ORM on every
call. The payload is now a generated asset and the runtime half is one small
RPC, so each test reads whichever of the two actually owns the property:

  * shape, completeness, bilingual parity, tokens  -> the content plane
  * visibility, slots, progress, who is asking     -> learn.runtime.bootstrap()

The one thing that got STRONGER: bilingual parity used to be checked against a
bundle assembled from the session's own translation lookups, so a missing .po
entry showed up here. There is no .po in this path any more — the generator
refuses to write a leaf with no Vietnamese (exit 4) and this is the second
fence, over the emitted bytes.
"""
import re

from odoo.tests.common import TransactionCase, tagged

from .common import load_content, walk_all_pairs as _walk_all_pairs, walk_pairs

TOKEN_RE = re.compile(r"\{\{([a-zA-Z][a-zA-Z0-9_]*)\}\}")

# Strings that are legitimately identical in both languages. Proper nouns and
# acronyms — anything added here must be a name or an abbreviation, never a
# sentence. A sentence in this set is a translation gap being papered over.
SAME_IN_BOTH = {
    "Payobook", "BHXH", "BHYT", "BHTN", "Hoa Sen Retail Co.", "Hà Nội",
    "TPHCM", "F&B", "HOASEN_RETAIL_END", "Excel", "SFTP", "Zoho People",
    # The Explorer's own name. pb_sidebar ships it untranslated and the cockpit
    # prints it untranslated, so translating it in the Journey would send a
    # learner looking for a leaf that says something else. A product name, not
    # a sentence — which is the only thing this set is for.
    "Explorer",
}

# Subtrees that are FACTS rather than prose, so "same in both languages" is the
# expected state, not a gap: a company's standard working days and its bank
# file format do not have an English and a Vietnamese version.
NOT_PROSE = (".tokens.",)


@tagged('post_install', '-at_install')
class TestBundle(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.content = load_content()
        cls.runtime = cls.env['learn.runtime'].bootstrap()

    # ------------------------------------------------------------- shape
    def test_01_shape(self):
        for key in ('version', 'stations', 'chrome', 'glossary', 'missions',
                    'intents', 'screens', 'columns', 'global_suggest'):
            self.assertIn(key, self.content, "content plane is missing %s" % key)
            self.assertTrue(self.content[key], "%s is empty" % key)
        for key in ('visible_stations', 'screens_runtime', 'tokens', 'progress',
                    'confidence', 'user', 'collect_questions', 'content_version'):
            self.assertIn(key, self.runtime, "bootstrap is missing %s" % key)

    def test_01b_the_server_and_the_browser_read_the_same_asset(self):
        """learn.content resolves the file through odoo.tools.file_open and the
        browser fetches it over /pb_learn/static/. Two paths to one file — and
        a deploy that copied only one of them would be invisible from either
        side, so the version digest is compared rather than assumed."""
        self.assertEqual(self.env['learn.content'].version(),
                         self.content['version'])
        self.assertEqual(self.runtime['content_version'], self.content['version'])

    def test_01c_every_station_is_answered_by_the_bootstrap(self):
        """A station the runtime does not report on renders with no visibility
        at all, which the map draws as available — the wrong way to be wrong."""
        missing = [s['key'] for s in self.content['stations']
                   if s['key'] not in self.runtime['visible_stations']]
        self.assertFalse(missing, "Stations with no visibility verdict: %s" % missing)
        absent = [s['key'] for s in self.content['screens']
                  if s['key'] not in self.runtime['screens_runtime']]
        self.assertFalse(absent, "Screens the Coach cannot detect: %s" % absent)

    # ------------------------------------------------------- completeness
    def test_02_every_station_has_content(self):
        thin = []
        for s in self.content['stations']:
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
        """Was an ORM constraint on learn.quiz. The constraint went with the
        model, so the invariant it enforced has to be asserted over the emitted
        content — which is where it can be checked once for every tenant rather
        than once per database."""
        bad = []
        for s in self.content['stations']:
            for lesson in s['lessons']:
                for q in lesson['quizzes']:
                    right = [o for o in q['options'] if o['correct']]
                    if len(right) != 1:
                        bad.append('%s: %d correct options' % (lesson['key'], len(right)))
                    for o in q['options']:
                        # Every option explains itself, right or wrong. A wrong
                        # option with no recovery text is a rejection.
                        self.assertTrue(o['feedback'] and o['feedback']['en'],
                                        "%s: an option has no explanation" % lesson['key'])
        self.assertFalse(bad, "\n  ".join(bad))

    def test_04_empty_translatables_stay_falsy(self):
        """An empty optional field must not arrive as {"en": "", "vi": ""}.

        Every optional block in the player is rendered with `field ? card : ""`,
        so a truthy-but-empty pair draws a heading with nothing under it. That
        is what shipped a blank "Before you do this" panel on steps that have
        no consequence.
        """
        empties = [path for path, pair in walk_pairs(self.content)
                   if not (pair.get('en') or '').strip()]
        self.assertFalse(empties, "Empty strings shipped as bilingual pairs:\n  "
                                  + "\n  ".join(empties[:20]))

    def test_04b_every_chrome_string_is_bilingual(self):
        """A chrome value that arrives as a bare string never got paired.

        The parity check below cannot see this: it walks {en, vi} pairs, so a
        value that never became a pair is invisible to it. That is how three
        labels whose names collide with structural keys — required, correct,
        after — once shipped as English beside translated neighbours.
        """
        bare = [k for k, v in self.content['chrome'].items()
                if not isinstance(v, dict)]
        self.assertFalse(bare, "Chrome strings that are not bilingual pairs: %s" % bare)

    def test_04c_the_only_non_prose_pair_is_a_glossary_match(self):
        """`walk_pairs` skips `{en, vi}` leaves whose values are not strings.
        This is the check that keeps that skip honest.

        Exactly one structure in the corpus legitimately wears the pair shape
        without being prose: a glossary entry's `match`, which carries the
        alias LIST for each language. Anything else that arrives non-string is
        a prose field that lost its sentence, and it would otherwise leave the
        walk — and therefore every invariant built on the walk — in silence.
        """
        strays = []
        for path, pair in _walk_all_pairs(self.content):
            if isinstance(pair.get('en'), str) and isinstance(pair.get('vi'), str):
                continue
            if re.fullmatch(r'\.glossary\[\d+\]\.match', path):
                for lang in ('en', 'vi'):
                    self.assertTrue(
                        isinstance(pair[lang], list)
                        and all(isinstance(a, str) for a in pair[lang]),
                        "%s [%s] is not a list of alias strings" % (path, lang))
                continue
            strays.append('%s -> en=%s vi=%s' % (path, type(pair.get('en')).__name__,
                                                 type(pair.get('vi')).__name__))
        self.assertFalse(strays, "Bilingual pairs that are not strings and are not a "
                                 "glossary match list. These are INVISIBLE to every other "
                                 "bundle check:\n  " + "\n  ".join(strays))

    def test_05_no_unresolved_tokens(self):
        tokens = self.runtime['tokens']
        leaked = []
        for path, pair in walk_pairs(self.content):
            for lang in ('en', 'vi'):
                for key in TOKEN_RE.findall(pair.get(lang) or ""):
                    if key not in tokens:
                        leaked.append('%s [%s] -> {{%s}}' % (path, lang, key))
        self.assertFalse(leaked, "Content names tenant slots that do not exist. These render "
                                 "as the key itself to a learner:\n  " + "\n  ".join(leaked))

    def test_06_bilingual_parity(self):
        """Nothing translatable may ship as English on the Vietnamese side."""
        untranslated = []
        for path, pair in walk_pairs(self.content):
            en = (pair.get('en') or "").strip()
            vi = (pair.get('vi') or "").strip()
            if not en or path.startswith(NOT_PROSE):
                continue
            # A step's typed VALUE is data, not prose — a person's name is
            # identical in both languages by definition (deploy finding,
            # sc_people's Nguyễn Văn An).
            if path.endswith('.value'):
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
        the bootstrap reports that station as `missing` rather than pretending.
        """
        broken = []
        installed = set(self.env['ir.module.module'].sudo().search(
            [('state', '=', 'installed')]).mapped('name'))
        for station in self.content['stations']:
            key = station['sidebar_key']
            if not key:
                continue
            module = key.split('.')[0]
            if module not in installed:
                continue
            if not self.env.ref(key, raise_if_not_found=False):
                broken.append('%s -> %s' % (station['key'], key))
            elif self.runtime['visible_stations'][station['key']]['missing']:
                broken.append('%s -> %s reported missing though the leaf exists'
                              % (station['key'], key))
        self.assertFalse(broken, "Stations pointing at a sidebar leaf that no longer exists:\n  "
                                 + "\n  ".join(broken))

    def test_08_selections_use_the_callable_form(self):
        """Static Selection lists do not translate in this codebase.

        Measured, and documented in the repo's gotcha ledger. Asserted by
        reflection so a future field cannot quietly reintroduce it. The list is
        shorter than it was because ten content models went with Phase 1a —
        every selection they carried is now a plain string in a generated file,
        which has no translation problem to have.
        """
        offenders = []
        models = ('learn.progress', 'learn.event', 'learn.consent')
        for name in models:
            for fname, field in self.env[name]._fields.items():
                if field.type != 'selection':
                    continue
                if not callable(field.selection):
                    offenders.append('%s.%s' % (name, fname))
        self.assertFalse(offenders,
                         "Selection fields declared as a static list — these will NOT "
                         "translate:\n  " + "\n  ".join(offenders))

    def test_10_vietnamese_never_says_web_browser(self):
        """`trình duyệt` is Vietnamese for "web browser".

        Used as a noun for the act of submitting — "mọi đợt đã trình duyệt" — it
        reads as a piece of software, and it is the SHORTER form, so it is the
        one a writer reaches for under time pressure. It has now been written
        three times across the module's life and caught twice by review, which
        is exactly when a rule becomes a test.

        THE MATCH HAS TO BE NARROW. `trình phê duyệt` (the act of submitting for
        approval) and `trình duyệt lên` do not contain the standalone noun, and
        `trình duyệt web` legitimately does — so the check looks for the two
        words with nothing but whitespace between them and no `phê` in front,
        then allows the handful of forms where the noun is genuinely meant.
        """
        # Case-insensitive: the noun is just as wrong at the start of a
        # sentence, where it is also capitalised and hardest to spot.
        bad_form = re.compile(r'(?<!phê )trình\s+duyệt(?!\s+web)', re.I)
        offenders = []
        for path, pair in walk_pairs(self.content):
            vi = (pair.get('vi') or '')
            for m in bad_form.finditer(vi):
                start = max(0, m.start() - 30)
                offenders.append('%s: …%s…' % (path, vi[start:m.end() + 30]))
        self.assertFalse(
            offenders,
            "%d Vietnamese string(s) use `trình duyệt` — which means WEB BROWSER. "
            "The act of submitting is `trình phê duyệt`, and submitting a run is "
            "`trình đợt lương lên duyệt`:\n  %s"
            % (len(offenders), "\n  ".join(offenders[:20])))

    def test_09_every_station_line_has_a_label(self):
        """A line with no chrome string renders its own key as a heading.

        health_learn shipped exactly that when its selection was extended
        without the matching UI strings: two headings reading their own keys.
        The map is the first thing a learner sees, so this is not a cosmetic
        miss — and Payobook adds lines section by section, which is precisely
        when it would happen again.

        The line vocabulary used to be a Selection on two models that had to be
        kept identical (`test_mission::test_13`). It is now whatever the content
        declares, which is one source instead of three.
        """
        chrome = self.content['chrome']
        missing = []
        for line in sorted({s['line'] for s in self.content['stations']}
                           | {m['line'] for m in self.content['missions']}):
            key = 'lines.%s' % line
            value = chrome.get(key)
            if not value or not (value.get('en') if isinstance(value, dict) else value):
                missing.append(key)
        self.assertFalse(missing, "Journey lines with no heading string: %s" % missing)
