# -*- coding: utf-8 -*-
"""The real-tenant welcome card — LEARNOS Phase 3.

pb_learn now has TWO first-run greetings and they are for two different
people. `test_retirement` owns the demo one; this file owns the other, and the
assertion that matters most is the one about the boundary between them: a demo
world may never draw the welcome card and a real tenant may never be sent into
the Journey map by itself.

The rest is the small set of properties that have each been a bug in this
program before:

  * a card that offers and does not start (the Phase C2 ruling, applied again)
  * "Later" is a real answer and is remembered forever
  * keydown on `document`, never `window` — Odoo's hotkey service stops
    propagation before the window bubble, so a window listener is silently
    dead (Phase 1 validation)
  * every string is a generated chrome record in both languages, never a
    literal in the JS (the Phase B ruling: a bilingual dict in code is not a
    translation, and an English literal is not either)
"""
import os
import re

from odoo.modules.module import get_module_path
from odoo.tests.common import TransactionCase, tagged

from .common import load_content

FIRST_LOGIN = 'static/src/coach/first_login.js'
COACH_JS = 'static/src/coach/coach.js'
COACH_SCSS = 'static/src/coach/coach.scss'

# The four chrome keys the card is built out of, and nothing else may reach the
# reader from this surface.
WELCOME_KEYS = ('welcomeTitle', 'welcomeBody', 'welcomeGo', 'welcomeLater')


def _read(rel):
    with open(os.path.join(get_module_path('pb_learn'), rel), encoding='utf-8') as fh:
        return fh.read()


def _strip_comments(src):
    src = re.sub(r'/\*.*?\*/', '', src, flags=re.S)
    return re.sub(r'(?m)^\s*//.*$', '', src)


@tagged('post_install', '-at_install')
class TestWelcomeCard(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.js = _read(FIRST_LOGIN)
        cls.code = _strip_comments(cls.js)
        cls.coach = _read(COACH_JS)
        cls.scss = _read(COACH_SCSS)

    # -- the boundary between the two greetings -----------------------------
    def test_01_the_two_greetings_cannot_both_fire(self):
        """One returns unless the session is a demo one; the other returns
        unless the DATABASE is not the demo world. Nobody can be shown both,
        and that is a property of the code rather than of an agreement between
        two functions."""
        greet = self.code.split('export async function maybeGreet')[1]
        self.assertIn('if (!isDemo) {', greet,
                      "the demo greeting no longer stands down for a real tenant")
        welcome = self.code.split('export async function maybeWelcome')[1] \
                           .split('export async function maybeGreet')[0]
        self.assertIn('if (demoWorld) {', welcome,
                      "the welcome card does not stand down on the demo world")
        self.assertIn('await user.hasGroup(DEMO_GROUP)', welcome,
                      "the welcome card does not stand down for a demo user")

    def test_02_the_demo_world_is_a_database_fact_from_the_server(self):
        """NOT a user-level probe. An administrator poking around the demo
        world is not a new tenant, and a group test would have welcomed them to
        a product they are running."""
        runtime = _read('models/learn_runtime.py')
        self.assertIn("'demo_world': self.env['learn.live'].world_is_demo()", runtime,
                      "the bootstrap no longer carries the demo-world fact")
        live = _read('models/learn_live.py')
        self.assertIn('def world_is_demo(self):', live)
        # A DATABASE fact is a search over the database. `env.company` is the
        # ACTIVE company — a session fact — and pinning it here is what let an
        # apex admin switched to company 2 be greeted as a new tenant
        # (Phase-3 review MAJOR-3).
        self.assertIn("self.env['res.company'].sudo().search_count", live,
                      "world_is_demo stopped being a database-level probe")
        self.assertIn("[('name', '=', DEMO_COMPANY_NAME)]", live,
                      "the demo world stopped being identified by company name")
        self.assertNotIn('self.env.company.name == DEMO_COMPANY_NAME', live,
                         "the active-company (session) probe is back")
        self.assertIn('demo_world: !!runtime.demo_world', self.coach,
                      "the Coach drops the fact before it reaches the card")

    def test_02b_the_card_is_not_drawn_without_a_bundle(self):
        """A failed bootstrap means no chrome, and a card built out of missing
        chrome renders its own key names at somebody on their first login.
        Fails closed."""
        self.assertIn('if (this.bundle) {', self.coach)
        self.assertLess(self.coach.index('if (this.bundle) {'),
                        self.coach.index('maybeWelcome(this.env'),
                        "maybeWelcome is called outside the bundle guard")

    # -- it offers, it does not start ---------------------------------------
    def test_03_the_card_offers_and_never_autoplays(self):
        """Same ruling as the demo greeting: a greeting has no business
        deciding somebody has two minutes right now. The walkthrough starts
        only from the press, and only in `watch`."""
        welcome = self.code.split('export async function maybeWelcome')[1] \
                           .split('export async function maybeGreet')[0]
        self.assertIn('const choice = await askWelcome();', welcome,
                      "the card starts something before it is answered")
        self.assertIn("if (choice === \"go\" && sc) {", welcome,
                      "the walkthrough is not conditional on the press")
        self.assertIn('WELCOME_MODE = "watch"', self.js,
                      "the card offers a mode other than Watch")

    def test_04_later_is_a_real_answer_and_is_remembered(self):
        """TWO keys, because they answer two questions. A single key would
        either nag somebody who said Later or forget somebody who closed the
        tab — and this module has shipped a stale-flag bug of exactly this
        family before (`pb_coach_login_seen` read by truthiness)."""
        self.assertIn('WELCOME_ANSWERED = "pbLearnWelcomeAnswered"', self.js)
        self.assertIn('WELCOME_LOGIN = "pbLearnWelcomeLogin"', self.js)
        self.assertIn('setLs(WELCOME_ANSWERED, choice);', self.code,
                      "the answer is not recorded, so the card comes back")
        self.assertIn('if (ls(WELCOME_ANSWERED)) {', self.code,
                      "the recorded answer is not read")
        # It must not share the demo greeting's keys: the two systems have to
        # be able to disagree about whether they have greeted.
        welcome = self.code.split('export async function maybeWelcome')[1] \
                           .split('export async function maybeGreet')[0]
        for key in ('LOGIN_KEY', 'SESSION_KEY'):
            self.assertNotIn('setLs(%s' % key, welcome,
                             "the welcome card writes the demo greeting's flag")

    def test_05_escape_is_bound_on_the_document(self):
        """Odoo's hotkey service stops propagation before the window-bubble
        phase, so a `window` keydown listener is silently dead. Found in Chrome
        in the Phase 1 validation round; it costs one word to get wrong."""
        self.assertIn('document.addEventListener("keydown", onKey)', self.js)
        self.assertNotIn('window.addEventListener("keydown"', self.js)
        self.assertIn('document.removeEventListener("keydown", onKey)', self.js,
                      "the listener outlives the card it belongs to")

    def test_06_the_card_cannot_break_the_product(self):
        """It runs inside the Coach's onMounted, and the Coach is on every
        screen in the product."""
        # Stripped copy, like every other assertion here: a COMMENT that
        # says "catch" must not satisfy a check about failure paths.
        welcome = self.code.split('export async function maybeWelcome')[1] \
                          .split('export async function maybeGreet')[0]
        self.assertGreaterEqual(welcome.count('catch'), 2,
                                "the welcome card has unguarded failure paths")
        self.assertIn('return false;', welcome.rsplit('catch', 1)[1],
                      "the outer catch does not return false")

    # -- the words -----------------------------------------------------------
    def test_07_every_string_is_a_generated_bilingual_record(self):
        chrome = load_content()['chrome']
        for key in WELCOME_KEYS:
            pair = chrome.get(key)
            self.assertTrue(pair, "the card's %s string was never generated" % key)
            for lang in ('en', 'vi'):
                self.assertTrue((pair.get(lang) or '').strip(),
                                "%s has no %s value" % (key, lang))
            self.assertNotEqual(pair['en'], pair['vi'],
                                "%s reaches a Vietnamese reader in English" % key)

    def test_08_the_card_reads_those_keys_and_holds_no_prose_of_its_own(self):
        """A sentence in the JS is a sentence no translator ever sees. Both
        directions: every key is read, and no key is read that was not
        generated."""
        read = set(re.findall(r'T\("(welcome[A-Za-z]+)"\)', self.js))
        self.assertEqual(read, set(WELCOME_KEYS),
                         "the card and the content plane disagree about its "
                         "strings: %s" % sorted(read.symmetric_difference(WELCOME_KEYS)))
        card = self.js.split('export function welcomeCardHTML')[1].split('\n}')[0]
        # Every value that reaches innerHTML is escaped. There is no authored
        # BODY here — no <b>, no tokens — so there is no raw position and
        # therefore no `gtx`, which is the one raw-insertion wrapper.
        self.assertEqual(card.count('${esc(T('), len(WELCOME_KEYS),
                         "a string reaches the card without being escaped")
        self.assertNotIn('gtx(', card)

    def test_09_the_launcher_stack_rules_still_win_in_the_right_order(self):
        """The welcome card's stylesheet was appended to this file, and two
        same-specificity rules are decided by ORDER. `test_retirement::test_14`
        asserts the launcher pair; this asserts that the new block did not land
        between them."""
        desktop = self.scss.find('body.pb-coach-absent .lrn-fab { bottom: 92px; }')
        mobile = self.scss.find('body.pb-coach-absent .lrn-fab { bottom: 86px; }')
        welcome = self.scss.find('.lrn-welcome {')
        self.assertNotEqual(welcome, -1, "the card has no stylesheet")
        self.assertGreater(welcome, mobile,
                           "the welcome block was inserted between the two "
                           "launcher offsets")
        self.assertLess(desktop, mobile)

    def test_10_no_css_min_or_max_in_the_new_block(self):
        """`min(400px, calc(100vw - 44px))` takes the WHOLE bundle down —
        Bootstrap's Sass intercepts it and Odoo keeps serving the previous
        stylesheet, so the only symptom is a screen that looks unstyled. This
        file has hit it twice.

        COMMENTS ARE STRIPPED FIRST, and that is not a detail: the comment in
        the stylesheet explaining why the function is not used contains the
        function's name, so the first version of this assertion failed on its
        own documentation. Seventh occurrence in this program of "a
        source-level assertion greped its own prose"; the rule is written down
        in the ledger and it still caught this.
        """
        block = re.sub(r'/\*.*?\*/', '', self.scss.split('.lrn-welcome {')[1], flags=re.S)
        self.assertNotIn('min(', block)
        self.assertNotIn('max(', block)
