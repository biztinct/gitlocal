# -*- coding: utf-8 -*-
"""ONECHAT OC4 — the Learn content follows the one PayAI chat.

Handover §10 / §11 OC4 (4.3). The drawer lost its tabs, "Your next step" and
the Ask-tab hand-off in OC2; the chat is called PayAI everywhere (owner
decision Q3). "Lessons follow screen changes": the content may not name what
the screen no longer has, and every chrome key the code reads must exist in
both languages.

Source-only: nothing here touches the database, so the whole class runs in
docs/tutorial_poc/author/tools/replay_tests.py too.
"""
import glob
import os
import re
import unicodedata

from odoo.modules.module import get_module_path
from odoo.tests.common import TransactionCase, tagged

from .common import load_content

# Retired in OC4: nothing reads them since OC2.
RETIRED = ('tabGuide', 'tabAsk', 'tabPractice', 'nextStep', 'thisScreen',
           'askDataInstead', 'askDataLead', 'practiceTry', 'practiceTour',
           'practiceTourLead', 'honest')

# How the code reads a chrome key: T("k") (coach), this.t("k") / t('k')
# (the chat), h.pair("k"), self._pair('k') / self._note('k') (the router).
KEY_CALL = re.compile(r'''(?<![\w.$])(?:this\.|h\.|helper\.|this\._|props\.helper\.|self\.)?'''
                      r'''(?:T|t|_pair|pair|_note)\(\s*["']([A-Za-z][A-Za-z0-9]*)["']''')

# What the drawer no longer has, in both languages.
STALE = re.compile(r'Guide me|Your next step|Ask tab|Practice tab|Payobook helper|'
                   r'[Hh]old (the microphone|to speak|to talk)|press and hold|'
                   r'Thẻ Hỏi đáp|tab Hỏi đáp|Bước tiếp theo của bạn|Giữ để nói|giữ nút micrô')
# "the helper" / "trợ lý" / "the Coach" as the NAME of the chat.
# ("dịch vụ trợ lý" is "the assistant service", the AI provider — not the chat.)
OLD_NAME = re.compile(r'\b[Tt]he (helper|Coach|copilot)\b|\bthis helper\b|(?<!dịch vụ )\btrợ lý\b')

SEVEN = ('sc_payrun', 'sc_payslips', 'sc_import', 'sc_people', 'sc_wfclose',
         'sc_hiring', 'sc_welcome')


def _fold(text):
    text = unicodedata.normalize('NFD', (text or '').lower().replace('đ', 'd'))
    text = ''.join(c for c in text if unicodedata.category(c) != 'Mn')
    return ' '.join(re.sub(r'[^a-z0-9\s]+', ' ', text).split())


def _marked(phrase):
    return any(ord(c) > 127 for c in phrase)


def _sources():
    out = {}
    for module in ('pb_learn', 'pb_payroll_ai_insights', 'pb_payai_actions'):
        base = get_module_path(module)
        if not base:
            continue
        files = []
        for ext in ('js', 'xml'):
            files += glob.glob(os.path.join(base, 'static', 'src', '**', '*.' + ext),
                               recursive=True)
        files.append(os.path.join(base, 'models', 'learn_helper.py'))
        for path in files:
            if os.path.exists(path):
                with open(path, encoding='utf-8') as fh:
                    out[os.path.relpath(path, os.path.dirname(base))] = fh.read()
    return out


def _lesson_and_tour_prose(tree):
    """(where, en, vi) for every lesson step and every tour step."""
    for station in tree['stations']:
        for lesson in station.get('lessons') or []:
            for i, step in enumerate(lesson.get('steps') or []):
                for f in ('kicker', 'title', 'body', 'tip', 'consequence'):
                    pair = step.get(f)
                    if isinstance(pair, dict):
                        yield ('%s/%s step %d %s' % (station['key'], lesson['key'], i, f),
                               pair.get('en', ''), pair.get('vi', ''))
    for sc in tree['scenarios']:
        for f in ('name', 'tagline'):
            pair = sc.get(f)
            if isinstance(pair, dict):
                yield ('%s %s' % (sc['key'], f), pair.get('en', ''), pair.get('vi', ''))
        for st in sc['steps']:
            for f in ('kicker', 'title', 'body', 'tip'):
                pair = st.get(f)
                if isinstance(pair, dict):
                    yield ('%s/%s %s' % (sc['key'], st['key'], f),
                           pair.get('en', ''), pair.get('vi', ''))


@tagged('post_install', '-at_install', 'onechat')
class TestOneChatContent(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.tree = load_content()
        cls.chrome = cls.tree['chrome']

    # -- 4.3 chrome keys --------------------------------------------------
    def test_01_every_key_the_code_reads_exists_in_both_languages(self):
        used = {}
        for path, src in _sources().items():
            for m in KEY_CALL.finditer(src):
                used.setdefault(m.group(1), path)
        self.assertGreater(len(used), 100, "the key scan found almost nothing")
        for key, path in sorted(used.items()):
            pair = self.chrome.get(key)
            self.assertTrue(pair, "%s reads chrome %r, which does not exist" % (path, key))
            self.assertTrue(pair.get('en') and pair.get('vi'),
                            "%r is not filled in both languages" % key)

    def test_02_retired_keys_are_gone_and_unread(self):
        sources = _sources()
        for key in RETIRED:
            self.assertNotIn(key, self.chrome, "%s is retired (OC4)" % key)
            for path, src in sources.items():
                self.assertNotRegex(src, r'''["']%s["']''' % key,
                                    "%s still reads the retired key %s" % (path, key))

    def test_03_no_chrome_names_what_the_drawer_lost(self):
        for key, pair in self.chrome.items():
            if not isinstance(pair, dict) or 'en' not in pair:
                continue
            for lang in ('en', 'vi'):
                text = pair.get(lang) or ''
                self.assertNotRegex(text, STALE, '%s.%s' % (key, lang))
                self.assertNotRegex(text, OLD_NAME, '%s.%s names the chat the old way'
                                    % (key, lang))

    # -- lessons and tours ------------------------------------------------
    def test_04_no_lesson_or_tour_names_what_the_drawer_lost(self):
        for where, en, vi in _lesson_and_tour_prose(self.tree):
            for text in (en, vi):
                self.assertNotRegex(text, STALE, where)
                self.assertNotRegex(text, OLD_NAME, where)

    def test_05_the_tour_has_one_name_in_vietnamese(self):
        tour = next(sc for sc in self.tree['scenarios'] if sc['key'] == 'sc_welcome')
        self.assertEqual(tour['name']['vi'], 'Đi một vòng Payobook')
        self.assertEqual(self.chrome['welcomeGo']['vi'], tour['name']['vi'])

    # -- practise phrases (handover §10) ------------------------------------
    def test_06_scenario_phrases_in_both_languages(self):
        for sc in self.tree['scenarios']:
            if sc.get('retired'):
                continue
            phrases = sc['phrases']
            marked = [p for p in phrases if _marked(p)]
            plain_vi = {_fold(p) for p in marked}
            unmarked_vi = [p for p in phrases if not _marked(p) and _fold(p) in plain_vi]
            english = [p for p in phrases if not _marked(p) and _fold(p) not in plain_vi]
            need = 6 if sc['key'] in SEVEN else 3
            self.assertGreaterEqual(len(english), need, '%s English' % sc['key'])
            self.assertGreaterEqual(len(marked), need, '%s Vietnamese' % sc['key'])
            self.assertGreaterEqual(len(unmarked_vi), need,
                                    '%s Vietnamese without marks' % sc['key'])
        wftime = next(sc for sc in self.tree['scenarios'] if sc['key'] == 'sc_wftime')
        self.assertIn('approve overtime', wftime['phrases'])
        self.assertIn('duyệt tăng ca', wftime['phrases'])

    # -- intents (handover §5.6, §10, ledger OC26) ---------------------------
    def test_07_add_a_person_can_be_practised(self):
        intents = {i['key']: i for i in self.tree['intents']}
        self.assertEqual(intents['addperson']['try'], 'sc_people')
        people = next(sc for sc in self.tree['scenarios'] if sc['key'] == 'sc_people')
        self.assertIn('try', people['modes'])

    def test_08_vietnamese_gap_questions_have_a_written_answer(self):
        intents = {i['key']: i for i in self.tree['intents']}
        for key, question in (('bhxh', 'bhxh là gì'), ('bhyt', 'bhyt là gì'),
                              ('netpay', 'lương thực nhận là gì'),
                              ('howrun', 'chạy lương thế nào'), ('howrun', 'cách chạy lương')):
            folded = {_fold(p) for p in intents[key]['phrases']}
            self.assertIn(_fold(question), folded, '%s should answer %r' % (key, question))
        for key in ('bhyt', 'netpay'):
            kinds = [b['kind'] for b in intents[key]['blocks']]
            self.assertIn('source', kinds, '%s states a fact with no source' % key)
            self.assertNotEqual(intents[key]['screens'], '*',
                                'a new global intent would push whatpage off the list')
