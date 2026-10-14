# -*- coding: utf-8 -*-
"""ONECHAT OC2 — the one chat, asserted on the shipped source.

One stream, one composer, no tabs, no "Your next step" (owner ruling
2026-10-14); the chat is called PayAI (owner decision Q3). The behaviour runs
in node (`pb_payai_actions/tests/js/onechat_oc2.test.mjs`, run by
`pb_payai_actions/tests/test_onechat_client.py`); these are the static facts
that must stay true whatever a later edit does to the behaviour:

  2.1  the older source pins this program must not break, mirrored here so
       they also run on a machine with no database (replay_tests.py);
  2.2  what is GONE stays gone (tabs, the next-step card, the Ask-tab
       hand-off), `openSuggested` stays (the moment card), no Font Awesome in
       the one chat, every sprite icon exists, no read of the page's session
       info for the language;
  2.9  the composer and microphone anchors are registered;
  2.10 no "Odoo" in anything the one chat shows or says.

Source-only: nothing here touches the database, so the whole class runs in
docs/tutorial_poc/author/tools/replay_tests.py too.
"""
import json
import os
import re

from odoo.modules.module import get_module_path
from odoo.tests.common import TransactionCase, tagged

from .common import load_content


def _read(module, rel):
    base = get_module_path(module)
    if not base:
        return None
    path = os.path.join(base, rel)
    if not os.path.exists(path):
        return None
    with open(path, encoding='utf-8') as fh:
        return fh.read()


def _code(src):
    """JS / XML without its comments: a word in a comment is not shipped."""
    src = re.sub(r'/\*.*?\*/', '', src, flags=re.S)
    src = re.sub(r'<!--.*?-->', '', src, flags=re.S)
    return re.sub(r'(?<!:)//[^\n]*', '', src)


COACH_JS = 'static/src/coach/coach.js'
COACH_XML = 'static/src/coach/coach.xml'
CHAT = 'static/src/components/ai_insight_chat/ai_insight_chat'


@tagged('post_install', '-at_install', 'onechat')
class TestOneChatUI(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.coach = _read('pb_learn', COACH_JS)
        cls.coach_xml = _read('pb_learn', COACH_XML)
        cls.chat_js = _read('pb_payroll_ai_insights', CHAT + '.js')
        cls.chat_xml = _read('pb_payroll_ai_insights', CHAT + '.xml')
        cls.patch_js = _read('pb_payai_actions', 'static/src/js/chat_patch.js') or ''
        cls.cpatch_js = _read('pb_payai_actions', 'static/src/js/coach_patch.js') or ''
        cls.sprite = _read('pb_learn', 'static/src/journey/icons.xml')
        cls.icons = set(re.findall(r'symbol id="lrn-i-([a-z0-9-]+)"', cls.sprite))
        cls.content = load_content()

    def _embedded_template(self):
        xml = self.chat_xml
        start = xml.index('t-name="pb_payroll_ai_insights.AiInsightChatEmbedded"')
        end = xml.find('<t t-name=', start + 10)
        return xml[start:end if end != -1 else len(xml)]

    # ------------------------------------------------------------------ 2.1
    def test_01_the_older_pins_still_hold(self):
        coach = self.coach
        declared = set(re.findall(r'"(c-[a-z-]+)"',
                                  coach.split('COACH_ACTIONS = new Set([')[1].split('])')[0]))
        emitted = set(re.findall(r'data-act="(c-[a-z-]+)"', coach + self.coach_xml))
        self.assertFalse(emitted - declared, 'undeclared data-act: %s' % (emitted - declared))
        answer = coach.split('_answerHTML(')[1].split('\n    }')[0]
        self.assertNotIn('doAction', answer)
        for literal in ('this._offers(a["try"], "try")', 'this._offers(a.watch, "watch")',
                        '"learn.intent", "explain_screen"', '"c-explain"',
                        'data-act="c-practice"', 'openLearn(this.action, "practice")',
                        '"c-practice"', 'markLauncherStack', '_offers(key, mode)',
                        '(sc.modes || []).includes(mode)'):
            self.assertIn(literal, coach)
        explain = coach.split('async explainScreen()')[1].split('\n    async ')[0]
        self.assertNotIn('_maybeStore', explain)
        self.assertNotIn('learn.question', explain)
        call = coach.split('this._log(answer.matched')[1].split(')')[0]
        self.assertNotIn('q', call.replace('answer.key', ''))
        self.assertIn('this.state.lang', coach.split('get bodyHTML() {')[1].split('\n    /**')[0])
        self.assertIn('this.state.lang', coach.split('get langLabel() {')[1].split('\n    }')[0])
        self.assertLess(coach.index('if (this.bundle) {'), coach.index('maybeWelcome(this.env'))
        self.assertIn('pb_learn.IconSprite', self.coach_xml)
        # test_assets test_06 — the Escape ladder, with its two new rungs.
        key = _code(coach).split('_onKey(ev)', 1)[1].split('\n    }', 1)[0]
        self.assertIn('glossaryOpen()', key)
        chunks = key.split('stopPropagation')[1:]
        self.assertGreaterEqual(len(chunks), 3, 'the menu and recording rungs are missing')
        for chunk in chunks:
            self.assertTrue(any(w in chunk[:220] for w in ('Exit(', 'exitLesson(', 'onLeave(', 'close(')))
        self.assertLess(key.index('this.menu.open'), key.index('isRecording()'),
                        'the menu closes before a recording is cancelled')
        self.assertLess(key.index('isRecording()'), key.rindex('this.close()'))

    def test_01b_the_voice_discard_order_is_untouched(self):
        """pb_payroll_ai_insights test_egress test_04b2, mirrored."""
        js = self.chat_js
        unmount = js.split('onWillUnmount(')[1].split('});')[0]
        self.assertLess(unmount.index('this._discarded = true'), unmount.index('this._releaseMicrophone()'))
        self.assertLess(unmount.index('this._audioChunks = []'), unmount.index('this._releaseMicrophone()'))
        onstop = js.split('this._mediaRecorder.onstop = ')[1].split('};')[0]
        self.assertIn('if (this._discarded)', onstop)
        self.assertIn('this._discarded', js.split('async _transcribe()')[1].split('\n    }')[0])

    # ------------------------------------------------------------------ 2.2
    def test_02_the_tabs_and_the_next_step_are_gone(self):
        sources = {
            'coach.js': self.coach, 'coach.xml': self.coach_xml,
            'chat_patch.js': self.patch_js, 'coach_patch.js': self.cpatch_js,
            'ai_insight_chat.js': self.chat_js, 'ai_insight_chat.xml': self.chat_xml,
        }
        for name, src in sources.items():
            code = _code(src)
            for gone in ('lrn-dtabs', 'c-tab', 'c-askdata', 'c-continue', '_nextStepHTML',
                         '_continueHTML', 'state.tab', 'TAB_ORDER', 'setTab(', 'askData(',
                         'lrn-dask-tab'):
                self.assertNotIn(gone, code, '%s still carries %s' % (name, gone))
        scss = _read('pb_learn', 'static/src/coach/coach.scss')
        for gone in ('.lrn-dtabs', '.lrn-dtab', '.lrn-dask-tab', '.lrn-cnext'):
            self.assertNotIn(gone, scss)
        self.assertIn('.lrn-drawer.lrn-has-chat', scss)

    def test_02b_open_suggested_stays_for_the_moment_card(self):
        coach = self.coach
        self.assertIn('    openSuggested(key) {', coach)
        moment = coach.split('async _momentAct(act) {')[1].split('\n    }')[0]
        self.assertIn('this.openSuggested(m.station)', moment)
        # …and its Explain goes through the queue, not straight to the RPC.
        self.assertIn('this.openHelper({ explain: true })', moment)
        self.assertNotIn('this.explainScreen()', moment)

    def test_02c_no_font_awesome_in_the_one_chat(self):
        tmpl = self._embedded_template()
        self.assertNotRegex(tmpl, r'\bfa-[a-z]', 'Font Awesome in the one chat')
        self.assertNotRegex(tmpl, r'<i class="fa\b')

    def test_02d_every_sprite_icon_the_one_chat_uses_exists(self):
        used = set(re.findall(r'href="#lrn-i-([a-z0-9-]+)"', self.chat_xml + self.coach_xml))
        used |= set(re.findall(r'\bic\("([a-z0-9-]+)"', self.coach))
        missing = sorted(used - self.icons)
        self.assertFalse(missing, 'icons the sprite does not have: %s' % missing)
        for name in ('mic', 'square', 'volume-2', 'volume-x', 'ellipsis', 'trash-2', 'scan-text'):
            self.assertIn(name, self.icons)
        for src in (self.coach, self.coach_xml, self.chat_js, self.chat_xml):
            self.assertNotIn('bar-chart-3', src)

    def test_02e_the_language_never_comes_from_the_pages_session_info(self):
        """It is deleted on load on this version: the read always found
        nothing, so a Vietnamese user started in English (ledger OC5)."""
        for module, rel in (('pb_learn', COACH_JS), ('pb_learn', 'static/src/journey/journey.js'),
                            ('pb_learn', 'static/src/hub/learn_palette.js'),
                            ('pb_payroll_ai_insights', CHAT + '.js'),
                            ('pb_payai_actions', 'static/src/js/chat_patch.js'),
                            ('pb_payai_actions', 'static/src/js/coach_patch.js')):
            self.assertNotIn('session_info', _code(_read(module, rel) or ''), '%s/%s' % (module, rel))

    def test_02f_the_one_seam(self):
        self.assertIn('HELPER_CHAT = "pb_helper_chat"', self.coach)
        self.assertIn('registry.category("pb_helper_chat").add("main"', self.chat_js)
        self.assertIn('<t t-component="chat.Component" helper="helper" lang="state.lang"', self.coach_xml)
        # cards.xml extends these two anchors; both must survive.
        tmpl = self._embedded_template()
        self.assertIn('class="payai-embed-text"', tmpl)
        self.assertRegex(tmpl, r'<t t-foreach="state\.messages"[^>]*>\s*<div ')

    def test_02g_the_router_is_never_told_how_the_words_arrived(self):
        """OC-R1: `route()` has no voice argument, and the client sends none."""
        call = self.chat_js.split('async _route(text) {')[1].split('\n    }')[0]
        self.assertNotIn('spoken', call)
        self.assertNotIn('voice', call)

    def test_02h_card_chips_bypass_the_router(self):
        """OC-R4: a pending card answer goes straight to PayAI."""
        self.assertIn('_bypassRouter()', self.chat_js.split('async sendText(text')[1].split('\n    }')[0])
        self.assertIn('Boolean(this._payaiResolve)', self.patch_js)
        self.assertNotIn('_payaiVoice', self.patch_js)
        self.assertNotIn('async _transcribe()', self.patch_js)

    def test_02i_only_the_composer_decides_spoken(self):
        """§6.3: `_takeSpoken` is called only from the composer's submit —
        never from a chip, a suggestion or a hand-off."""
        lines = self.chat_js.split('\n')
        owners = []
        for i, line in enumerate(lines):
            if 'this._takeSpoken(' not in line:
                continue
            for j in range(i, -1, -1):
                m = re.match(r'^    (?:async )?([A-Za-z_$][\w$]*)\(', lines[j])
                if m:
                    owners.append(m.group(1))
                    break
        self.assertTrue(owners, 'the spoken mark is never read')
        self.assertEqual(set(owners), {'submitComposer'}, owners)

    # ------------------------------------------------------------------ 2.9
    def test_09_the_composer_and_microphone_anchors_are_registered(self):
        reg = json.loads(_read('pb_learn', 'static/src/anchors.json'))['product']
        for key in ('helper-composer', 'helper-mic'):
            self.assertIn(key, reg)
            self.assertIn('data-coach="%s"' % key, self.chat_xml)
        self.assertIn('data-coach="helper-composer"', self.coach_xml)
        self.assertIn('data-coach="helper-orb"', self.coach_xml)

    # ----------------------------------------------------------------- 2.10
    def test_10_no_odoo_in_anything_the_one_chat_shows(self):
        chrome = self.content['chrome']
        new_keys = (
            'coachName', 'orbLabel', 'orbHint', 'honestAct', 'honestAsk', 'honestGuide',
            'askAny', 'askAnyNoAct', 'send', 'close', 'more', 'readAloud', 'clearConv',
            'clearConvConfirm', 'clearConvYes', 'clearConvNo', 'useVoice', 'micStart',
            'recording', 'answering', 'fromGuide', 'fromPayData', 'aboutScreen',
            'aboutColumn', 'practiseThis', 'letMePractise', 'openingPractice', 'openingWatch',
            'practiceChipsLead', 'whatCanYouDo', 'showAgain', 'composedAgain', 'jumpLatest',
            'spoken', 'routeFailed', 'pinDashboard', 'figuresOnScreen', 'helperFailed', 'scPractise',
            'swVoiceTitle', 'swVoiceBody')
        for key in new_keys:
            pair = chrome.get(key)
            self.assertTrue(pair and pair.get('en') and pair.get('vi'), 'chrome %s is missing a language' % key)
            for lang in ('en', 'vi'):
                self.assertNotRegex(pair[lang], r'(?i)odoo', '%s.%s' % (key, lang))
                self.assertNotRegex(pair[lang], r'Ask tab|tab Hỏi đáp|thẻ Hỏi đáp',
                                    '%s.%s still names the Ask tab' % (key, lang))
        # Q3: the chat is called PayAI.
        self.assertEqual(chrome['coachName']['en'], 'PayAI')
        self.assertEqual(chrome['coachName']['vi'], 'PayAI')
        self.assertIn('PayAI', chrome['orbLabel']['en'])
        self.assertIn('PayAI', chrome['swVoiceTitle']['en'])
        # String literals in the shipped code and templates of the one chat.
        for name, src in (('coach.js', self.coach), ('coach.xml', self.coach_xml),
                          ('ai_insight_chat.js', self.chat_js), ('embedded template', self._embedded_template()),
                          ('chat_patch.js', self.patch_js), ('coach_patch.js', self.cpatch_js)):
            code = _code(src)
            for lit in re.findall(r'"([^"\n]*)"|`([^`]*)`|>([^<>{}\n]+)<', code):
                text = ''.join(lit)
                if re.fullmatch(r'@[\w./-]+', text):
                    continue        # a module path ("@odoo/owl"), not a word anyone sees
                if re.fullmatch(r'odoo(\.[a-z_]+)+\.?', text):
                    continue        # a server exception's technical name, compared, never shown
                self.assertNotRegex(text, r'(?i)\bodoo\b', '%s shows %r' % (name, text[:80]))

    def test_10b_the_spoken_and_shown_text_passes_the_brand_seam(self):
        """Guide answers and notes go through `tx()` (the `_t` funnel the
        debranding seams see); read-aloud speaks a reply, never page text."""
        self.assertIn('text: (pair, lang) => this._inLang(lang, () => tx(pair))', self.coach)
        self.assertIn('String(_t(typeof o === "string"', _read('pb_learn', 'static/src/engine/runtime.js'))
