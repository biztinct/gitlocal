# -*- coding: utf-8 -*-
"""PAYAI P4 — the P3 live-walk fixes P4-W1/W2, then Vietnamese, the
Approvals deep link and the close-out checks: numbered tests 1–10 of
P4_HANDOVER.md.

Same rules as P1–P3: every gate is judged for an explicit user (PA12), no AI
provider is reached (the phrase table carries every sentence), fixtures use
2031 so a shared clone's own runs never collide (PA40).
"""
import ast
import json
import os
import re
from unittest.mock import patch

from odoo.modules.module import get_module_path
from odoo.tests.common import tagged
from odoo.tools.translate import PoFileReader, babel_extract_qweb

from odoo.addons.pb_payai_actions.payai import i18n, registry, resolve, runner
from odoo.addons.pb_payai_actions.payai.actions_amber import UpdatePayData
from odoo.addons.pb_payai_actions.payai.registry import ACTIONS
# The P3 classes are reached through their module: a class imported by name
# here would be collected (and run) a second time.
from odoo.addons.pb_payai_actions.tests import test_payai_p3 as p3

_P3Case = p3._P3Case
VI = 'vi_VN'

#: Every .po this phase wrote to (test 1 / the gate).
P4_CATALOGUES = (
    ('pb_payai_actions', 'vi_VN.po'), ('pb_payrun_wizard', 'vi_VN.po'),
    ('pb_audit', 'vi_VN.po'), ('om_hr_payroll', 'vi_VN.po'),
    ('pb_payroll_ai_insights', 'vi_VN.po'),
)
#: The model's tools schema and debug-only help: English on purpose.
NOT_SHOWN = re.compile(r'^\s*summary\s*=')


def _catalogue(module, name='vi_VN.po'):
    """{source: Vietnamese} for code rows that REACH a screen (module line,
    odoo-python/odoo-javascript marker, a code occurrence), via the very
    reader the server loads translations with (it merges the .pot too)."""
    path = os.path.join(get_module_path(module), 'i18n', name)
    out = {}
    for row in PoFileReader(path):
        if row['type'] == 'code' and row['value'] and (
                'odoo-python' in row['comments'] or 'odoo-javascript' in row['comments']):
            out[row['src']] = row['value']
    return out


def _is_translate_call(node):
    """`_lt(...)` / `_(...)` — and (FIX-1 P4:test-4) `self.env._(...)`."""
    func = node.func
    if isinstance(func, ast.Name):
        return func.id in ('_lt', '_')
    return isinstance(func, ast.Attribute) and func.attr == '_'


def _payai_literals():
    """(source, file) for every translatable literal pb_payai_actions shows:
    _lt/_/env._ in Python (an Action's `summary` excepted: only the model
    reads it), _t in the JavaScript and the OWL templates' own text (read by
    the very extractor the translation export uses)."""
    root = get_module_path('pb_payai_actions')
    found = []
    for sub in ('payai', 'models'):
        for name in sorted(os.listdir(os.path.join(root, sub))):
            if not name.endswith('.py'):
                continue
            src = open(os.path.join(root, sub, name), encoding='utf-8').read()
            tree = ast.parse(src)
            skip = set()
            for node in ast.walk(tree):
                if isinstance(node, ast.Assign) and any(
                        isinstance(t, ast.Name) and t.id == 'summary' for t in node.targets):
                    skip.update(id(n) for n in ast.walk(node.value))
            for node in ast.walk(tree):
                if (isinstance(node, ast.Call) and _is_translate_call(node) and node.args
                        and isinstance(node.args[0], ast.Constant)
                        and isinstance(node.args[0].value, str) and node.args[0].value
                        and id(node) not in skip):
                    found.append((node.args[0].value, '%s/%s' % (sub, name)))
    js_dir = os.path.join(root, 'static', 'src', 'js')
    for name in sorted(os.listdir(js_dir)):
        src = open(os.path.join(js_dir, name), encoding='utf-8').read()
        for m in re.finditer(r'_t\(\s*"((?:[^"\\]|\\.)*)"', src):
            found.append((m.group(1).encode().decode('unicode_escape').encode('latin-1')
                          .decode('utf-8'), 'js/' + name))
    xml_dir = os.path.join(root, 'static', 'src', 'xml')
    for name in sorted(os.listdir(xml_dir)):
        if not name.endswith('.xml'):
            continue
        with open(os.path.join(xml_dir, name), 'rb') as fh:
            for _line, _f, text, _c in babel_extract_qweb(fh, [], [], {}):
                found.append((text, 'xml/' + name))
    return found


def _shown_text(card):
    """Every piece of a card a person reads: title, subtitle, hint, audit
    line, slot labels and values, notes, button and chip labels."""
    out = [card.get(k) or '' for k in ('title', 'subtitle', 'hint', 'audit_line', 'footer')]
    for slot in card.get('slots') or []:
        out += [slot.get(k) or '' for k in ('label', 'value_label', 'origin_label', 'note')]
    out += [(n or {}).get('text') or '' for n in card.get('notes') or []]
    for act in (card.get('actions') or []) + (card.get('chips') or []):
        out += [act.get(k) or '' for k in ('label', 'sublabel', 'hint', 'placeholder')]
    return [t for t in out if isinstance(t, str) and t]


def _po_blocks(module, name='vi_VN.po'):
    """The entries of a catalogue as lists of lines (header dropped)."""
    path = os.path.join(get_module_path(module), 'i18n', name)
    text = open(path, encoding='utf-8').read()
    for block in text.split('\n\n')[1:]:
        lines = [l for l in block.strip().split('\n') if l]
        if lines:
            yield lines


def _strip_js_comments(src):
    """JavaScript without its comments (a comment may name what the code
    no longer does)."""
    src = re.sub(r'/\*.*?\*/', ' ', src, flags=re.S)
    return re.sub(r'(?m)(^|[^:\\])//.*$', r'\1', src)


@tagged('post_install', '-at_install', 'payai')
class TestPayaiP4Walk(_P3Case):
    """P4-W1/W2 — the pay-value refusal Fable met on the P3 walk."""

    def _no_pay_values(self):
        if 'pb.records.desk' not in self.env:
            self.skipTest('Records Desk not installed.')
        if 'pb.scheme.map' in self.env:
            p = patch.object(self.registry['pb.scheme.map'], 'resolve',
                             lambda self_, employee, cycle_type='any', on_date=None: {
                                 'config_id': self.retail_end.id, 'config_name': '',
                                 'rung': 'test', 'via': ''})
            p.start()
            self.addCleanup(p.stop)
        # The walk's data: the scheme has no Records value the person may change.
        p = patch.object(UpdatePayData, '_cards', lambda self_, ctx, config_id: {})
        p.start()
        self.addCleanup(p.stop)
        return self._user('P4 Records', [self.env.ref('hr.group_hr_user').id,
                                         self.g_officer, self.g_pay_user])

    def test_w1_one_records_door_only(self):
        hr_user = self._no_pay_values()
        card, _s = self._send(hr_user, 'Give Payai Linh Nguyen a Payai Lunch stipend of 500,000')
        self.assertEqual(card['kind'], 'blocked', card)
        doors = [a for a in card['actions'] if a.get('door_id') == 'peoplehub_records']
        self.assertEqual(len(doors), 1, card['actions'])
        labels = [a.get('label') for a in card['actions']]
        self.assertEqual(len(labels), len(set(labels)), "a button is drawn twice: %r" % labels)

    def test_w2_says_why_and_offers_what_can_you_do(self):
        hr_user = self._no_pay_values()
        card, _s = self._send(hr_user, 'Give Payai Linh Nguyen a Payai Lunch stipend of 500,000')
        text = ' '.join(n['text'] for n in card['notes'])
        readable = self.retail_end.with_user(hr_user).has_access('read')
        if readable:
            self.assertIn('Nothing on Payai Retail End-Month can be changed from here yet', text)
        else:
            self.assertIn("Nothing on this person's scheme can be changed from here yet", text)
        self.assertNotIn('has no pay value that can be changed here', text)
        self.assertIn('What can you do?', [c['label'] for c in card['chips']])
        self.assertNotIn('Odoo', json.dumps(card))


@tagged('post_install', '-at_install', 'payai')
class TestPayaiP4Catalogue(_P3Case):
    """Tests 1, 4, 5, 6 (server half) and 10 — no database fixtures needed
    beyond the shared ones."""

    # ================================================================ 1
    def test_01_every_catalogue_parses_and_every_entry_reaches_a_screen(self):
        for module, name in P4_CATALOGUES:
            path = os.path.join(get_module_path(module), 'i18n', name)
            rows = list(PoFileReader(path))          # a bad entry raises here
            self.assertTrue(rows, path)
        # FIX-1 (P4:test-3): EVERY catalogue this phase wrote to — not only
        # pb_payai_actions — has, on every entry, its module line FIRST, an
        # occurrence under its own module and, for a code entry, the
        # odoo-python / odoo-javascript marker: without the marker the entry
        # parses but is never loaded, and the screen stays English
        # (po-translation-loading-rules). Only om_hr_payroll's pre-P4 entries
        # in the old exporter's shape ("#, python-format", no marker) are
        # left as they were.
        for module, name in P4_CATALOGUES:
            for lines in _po_blocks(module, name):
                where = '%s: %s' % (module, ' | '.join(lines[:4])[:160])
                self.assertTrue(lines[0].startswith('#. module: %s' % module), where)
                occ = [part for l in lines if l.startswith('#: ') for part in l[3:].split()]
                self.assertTrue(occ, where)
                if not any(o.startswith('code:') for o in occ):
                    continue
                self.assertTrue(all(re.match(r'(?:code:addons/%s/\S+:\d+|model:\S+|model_terms:\S+)$'
                                             % module, o) for o in occ), where)
                marked = any(l in ('#. odoo-python', '#. odoo-javascript') for l in lines)
                legacy = module == 'om_hr_payroll' and '#, python-format' in lines
                self.assertTrue(marked or legacy, where)

    def test_01b_every_shown_string_has_vietnamese(self):
        """Coverage re-derived from the source on every run: a new card
        sentence without Vietnamese fails here, not on a customer's screen."""
        cat = _catalogue('pb_payai_actions')
        found = _payai_literals()
        self.assertGreater(len(found), 300, "the scan is broken")
        missing = sorted({s for s, _f in found if not cat.get(s)})
        self.assertFalse(missing, "shown with no Vietnamese: %r" % missing[:5])
        same = sorted({s for s, _f in found if cat.get(s) == s and s not in ('PayAI', 'ID')})
        self.assertFalse(same, "Vietnamese identical to English: %r" % same[:5])
        for src, vi in cat.items():
            self.assertEqual(sorted(re.findall(r'%\(\w+\)s|%s|%d', src)),
                             sorted(re.findall(r'%\(\w+\)s|%s|%d', vi)),
                             "a translation lost or invented a placeholder: %r" % src[:50])
        # The other modules' PayAI strings (P0–P2 copy).
        for module, sources in (
                ('pb_payrun_wizard', ("Running payroll is for payroll staff.",
                                      "Finished payroll is never cleared from here.",
                                      "PayAI filled this in from your request.")),
                ('pb_audit', ('Asked PayAI: %(what)s',)),
                ('om_hr_payroll', ('Payslips are emailed once the pay run is approved.',))):
            other = _catalogue(module)
            for start in sources:
                hit = [v for k, v in other.items() if k.startswith(start)]
                self.assertTrue(hit and hit[0] and not hit[0].startswith(start),
                                '%s: no Vietnamese for %r' % (module, start))

    # ================================================================ 4
    def test_04_every_vietnamese_phrasing_finds_its_action(self):
        table = [
            ('chạy lương tháng 6 cho Bán lẻ', 'run_payroll', {'period': 'tháng 6', 'scheme': 'Bán lẻ'}),
            ('Bạn giúp tôi tính lương tháng 12 năm 2031 nhé', 'run_payroll', {'period': 'tháng 12 năm 2031'}),
            ('gửi duyệt bảng lương tháng 8', 'submit_run', {'run': 'bảng lương tháng 8'}),
            ('gửi bảng lương tháng 8 đi duyệt', 'submit_run', {}),
            ('duyệt bảng lương tháng 6 Bán lẻ', 'approve_item', {'item': 'bảng lương tháng 6 Bán lẻ'}),
            ('duyet bang luong thang 6', 'approve_item', {'item': 'bang luong thang 6'}),
            ('duyệt bảng lương tháng 6 với ghi chú đã kiểm tra', 'approve_item',
             {'item': 'bảng lương tháng 6', 'reason': 'đã kiểm tra'}),
            ('trả lại bảng lương tháng 6 vì thiếu tăng ca', 'send_back_item',
             {'item': 'bảng lương tháng 6', 'reason': 'thiếu tăng ca'}),
            ('trả bảng lương tháng 6 lại cho Lan vì sai số', 'send_back_item', {'reason': 'sai số'}),
            ('từ chối bảng lương tháng 5 vì trả hai lần', 'reject_item',
             {'item': 'bảng lương tháng 5', 'reason': 'trả hai lần'}),
            ('mở bảng lương', 'open_screen', {'door': 'bảng lương'}),
            ('xem phiếu lương', 'open_screen', {}),
            ('xem bảng lương tháng 6', 'run_status', {'run': 'bảng lương tháng 6'}),
            ('bảng lương tháng 6 đang ở đâu?', 'run_status', {}),
            ('tải Excel tháng 6', 'download_run_excel', {'run': 'tháng 6'}),
            ('gửi phiếu lương tháng 6', 'send_payslips', {'run': 'tháng 6'}),
            ('đổi phụ cấp ăn trưa của Vũ Khánh Chi thành 500.000 từ tháng 11', 'update_pay_data',
             {'field': 'phụ cấp ăn trưa', 'person': 'Vũ Khánh Chi', 'value': '500.000',
              'from': 'tháng 11'}),
            ('lập tờ khai BHXH tháng 9', 'filing_prepare', {'period': 'tháng 9'}),
            ('bạn làm được gì?', 'what_can_you_do', {}),
            ('xoá bảng lương tháng 6', 'never_destructive', {}),
        ]
        for text, key, slots in table:
            got = registry.match(text)
            self.assertTrue(got, text)
            self.assertEqual(got[0], key, text)
            for k, v in slots.items():
                self.assertEqual(got[1].get(k), v, '%s → %s' % (text, got[1]))
        # A question stays a question.
        for text in ('làm sao để chạy lương?', 'tại sao bảng lương tháng 6 bị trả lại?',
                     'phụ cấp ăn trưa là gì?'):
            self.assertIsNone(registry.match(text), text)
        # Every example on "What can you do?", in Vietnamese, does what it says.
        token = i18n.set_lang(VI)
        try:
            for action in ACTIONS.values():
                for example in action.examples:
                    said = i18n.T(example)
                    self.assertNotEqual(said, i18n.EN(example), 'no Vietnamese for %r' % said)
                    got = registry.match(said)
                    self.assertTrue(got and got[0] == action.key,
                                    '%r (%s) → %r' % (said, action.key, got))
        finally:
            i18n.reset_lang(token)
        # The model's tools schema stays English for a Vietnamese reader.
        token = i18n.set_lang(VI)
        try:
            tool = registry.tool_for(ACTIONS['run_payroll'])
        finally:
            i18n.reset_lang(token)
        self.assertIn('Prepare a draft pay run', tool['description'])

    def test_04b_vietnamese_months(self):
        import datetime
        today = datetime.date(2026, 10, 13)
        cases = {
            'tháng 12 năm 2031': (2031, 12), 'tháng sáu': (2026, 6), 'tháng sau': (2026, 11),
            'thang sau': (2026, 11), 'tháng 6/2026': (2026, 6), 'T6': (2026, 6),
            'tháng trước': (2026, 9), 'tháng này': (2026, 10), 'tháng mười hai năm 2030': (2030, 12),
            'tháng năm 2026': (2026, 5),
        }
        for text, (y, m) in cases.items():
            got = resolve.parse_period(text, today)
            self.assertTrue(got, text)
            self.assertEqual((got[0].year, got[0].month), (y, m), text)
        self.assertEqual(resolve.parse_period('Bán lẻ tháng 6', today)[3].split(), ['ban', 'le'])
        token = i18n.set_lang(VI)
        try:
            self.assertEqual(resolve.month_label(datetime.date(2031, 12, 1)), 'tháng 12 năm 2031')
            self.assertEqual(i18n.num(1234567), '1.234.567')
            self.assertEqual(i18n.short_amount(18.6e9), '18,6 tỷ')
        finally:
            i18n.reset_lang(token)
        self.assertEqual(resolve.month_label(datetime.date(2031, 12, 1)), 'December 2031')
        self.assertEqual(i18n.num(1234567), '1,234,567')

    # ================================================================ 5
    def test_05_vietnamese_numbers(self):
        self.assertEqual(resolve.parse_amount('500.000'), 500000)
        self.assertEqual(resolve.parse_amount('1.500.000,5'), 1500000.5)
        self.assertEqual(resolve.parse_amount('500,000'), 500000)
        self.assertEqual(resolve.parse_amount('5 triệu'), 5000000)
        self.assertEqual(resolve.parse_amount('500 nghìn'), 500000)
        self.assertEqual(resolve.parse_amount('500.000đ'), 500000)
        self.assertEqual(resolve.parse_amount('1,5 triệu'), 1500000)
        key, slots = registry.match(
            'đổi phụ cấp ăn trưa của Vũ Khánh Chi thành 500.000 từ tháng 11')
        self.assertEqual(key, 'update_pay_data')
        self.assertEqual(resolve.parse_amount(slots['value']), 500000)

    # ================================================================ 6
    def test_06_inbox_reads_the_focus_the_cards_send(self):
        """The server writes pb_focus, the inbox reads it: one format, pinned
        on both ends (the regex is lifted out of inbox.js itself)."""
        from odoo.addons.pb_payai_actions.payai.actions_red import approvals_hub
        hub = approvals_hub(42)
        self.assertEqual(hub['focus'], 'request:42')
        self.assertEqual(hub['context']['pb_focus'], 'request:42')
        self.assertEqual(approvals_hub(42, 'org')['focus'], 'request:42:org')
        self.assertNotIn('focus', approvals_hub(0))
        src = open(os.path.join(get_module_path('pb_approval_config'), 'static', 'src', 'js',
                                'inbox.js'), encoding='utf-8').read()
        m = re.search(r'const m = /(.+?)/\.exec\(', src)
        self.assertTrue(m, 'inbox.js no longer reads pb_focus "request:<id>"')
        rx = re.compile(m.group(1).replace('\\/', '/'))
        self.assertTrue(rx.match('request:42') and rx.match('request:42:org'))
        self.assertFalse(rx.match('queue') or rx.match('month:2026-06'))
        self.assertIn('_consumedFocus', src)        # one arrival opens one drawer
        # FIX-1 (P4:link-1): a lens reads the hub's arrival prop (`wantsArrival`),
        # never the action service's current action (a Promise, and the
        # previous screen's while the lens is set up). Comments may still
        # tell that story; the code must not do it.
        code = _strip_js_comments(src)
        self.assertIn('inboxArrival', code)
        self.assertIn('props.arrival', code)
        self.assertNotIn('currentAction', code)

    # ================================================================ 8
    def test_08_learn_teaches_asking_payai_in_both_languages(self):
        """"Ask PayAI to do it" in Learn: the plan card → Do it → the
        ten-minute way back (Runs lesson), and the typed word (Approvals
        lesson). Both languages, on anchors the screens really lay."""
        learn = get_module_path('pb_learn')
        if not learn:
            self.skipTest('pb_learn is not here.')
        content = json.load(open(os.path.join(learn, 'static', 'content',
                                              'learn_content.json'), encoding='utf-8'))
        anchors = json.load(open(os.path.join(learn, 'static', 'src', 'anchors.json'),
                                 encoding='utf-8'))['product']
        steps = {s['key']: s['lessons'][0]['steps'] for s in content['stations']}
        ask = [st for st in steps['payruns'] if (st.get('kicker') or {}).get('en') == 'Ask PayAI']
        self.assertEqual(len(ask), 1, 'the Runs lesson has no "Ask PayAI" step')
        ask = ask[0]
        for lang, words in (('en', ('plan card', 'Do it', 'Withdraw', '10 minutes')),
                            ('vi', ('thẻ kế hoạch', 'Thực hiện', 'Thu hồi', '10 phút'))):
            # LEARNREV P4 moved a step's words into the four lines (look /
            # means / affects) and left `body` empty; read whichever is there.
            said = ' '.join((st_part or {}).get(lang, '') if isinstance(st_part, dict) else ''
                            for st_part in (ask.get('body'), ask.get('look'), ask.get('means'),
                                            ask.get('affects'), ask.get('tip')))
            for word in words:
                self.assertIn(word, said, (lang, word))
        self.assertIn('Undo', ask['tip']['en'])
        self.assertIn('Hoàn tác', ask['tip']['vi'])
        approve = [st for st in steps['approvals'] if st['anchor'] == 'ai-approve'][0]
        self.assertIn('APPROVE', approve['tip']['en'])
        self.assertIn('DUYỆT', approve['tip']['vi'])
        for st, screen in ((ask, 'payruns'), (approve, 'approvals')):
            self.assertEqual(st['screen'], screen)
            self.assertEqual(anchors[st['anchor']]['screen'], screen, st['anchor'])
            path = os.path.join(os.path.dirname(learn), anchors[st['anchor']]['file'])
            self.assertIn('"%s"' % st['anchor'], open(path, encoding='utf-8').read(),
                          '%s is not laid in %s' % (st['anchor'], path))
        # The sentences it teaches are ones PayAI understands, in both languages.
        self.assertEqual(registry.match('Send the June run for approval')[0], 'submit_run')
        self.assertEqual(registry.match('Gửi duyệt bảng lương tháng 6')[0], 'submit_run')
        self.assertEqual(registry.match('Duyệt bảng lương tháng 6 Bán lẻ')[0], 'approve_item')

    # =============================================================== 10
    def test_10_no_odoo_on_any_card(self):
        root = get_module_path('pb_payai_actions')
        # FIX-1 (P4:test-4): every row of the catalogue — code AND model
        # rows (settings labels, help, choices) — in English and Vietnamese.
        path = os.path.join(root, 'i18n', 'vi_VN.po')
        for row in PoFileReader(path):
            self.assertNotIn('odoo', (row['src'] or '').lower(), row['src'])
            self.assertNotIn('odoo', (row['value'] or '').lower(), row['value'])
        for src, _f in _payai_literals():
            self.assertNotIn('odoo', src.lower(), src)
        # Field labels, help and choices written in the models.
        for name in sorted(os.listdir(os.path.join(root, 'models'))):
            if not name.endswith('.py'):
                continue
            tree = ast.parse(open(os.path.join(root, 'models', name), encoding='utf-8').read())
            for node in ast.walk(tree):
                if not isinstance(node, ast.Call):
                    continue
                texts = [kw.value for kw in node.keywords if kw.arg in ('string', 'help', 'selection')]
                for value in texts:
                    for const in ast.walk(value):
                        if isinstance(const, ast.Constant) and isinstance(const.value, str):
                            self.assertNotIn('odoo', const.value.lower(),
                                             'models/%s: %s' % (name, const.value[:60]))
        for sub in ('static/src/xml', 'views'):
            for name in os.listdir(os.path.join(root, sub)):
                text = open(os.path.join(root, sub, name), encoding='utf-8').read()
                # Visible text and the attributes a person reads.
                for chunk in re.findall(r'>([^<>]+)<|(?:string|help|title|placeholder|'
                                        r'aria-label)="([^"]*)"', text):
                    words = ''.join(chunk)
                    self.assertNotIn('Odoo', words, '%s/%s: %s' % (sub, name, words[:60]))


class TestPayaiP4Vietnamese(p3.TestPayaiP3Red):
    """Tests 2, 3 and 6 (card half) with a Vietnamese user — on the P3 Red
    fixtures (their tests are switched off below, they run in P3)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env['res.lang']._activate_lang(VI)
        cls.hoa = cls._user('Hoa Payai', [cls.g_officer, cls.g_pay_user])
        cls.hoa.lang = VI
        cls.vi_officer = cls._user('Officer VI Payai', [cls.g_officer, cls.g_pay_user])
        cls.vi_officer.lang = VI

    def _send_vi(self, user, text, session=None, resolve=None):
        session = session or self._session(user)
        Conv = self.env['payroll.ai.conversation'].with_user(user).with_context(lang=VI)
        out = Conv.rpc_send_message(text, session.id, None, resolve=resolve)
        return out['card'], session

    def _confirm_vi(self, user, card, how='typed', word=None, note=None):
        Conv = self.env['payroll.ai.conversation'].with_user(user).with_context(lang=VI)
        return Conv.rpc_confirm_task(card['task_id'], how, word, note)['card']

    # ================================================================ 2
    def test_p4_02_vietnamese_plan_card(self):
        card, _s = self._send_vi(
            self.vi_officer, 'chạy lương tháng 12 năm 2031 cho Payai Retail End-Month')
        self.assertEqual((card['kind'], card['state']), ('plan', 'planned'), card)
        self.assertEqual(card['title'], 'Chạy lương')
        self.assertTrue(card['subtitle'].startswith('Chuẩn bị · tạo một đợt lương nháp'), card['subtitle'])
        slots = {s['key']: s for s in card['slots']}
        self.assertEqual(slots['period']['label'], 'Kỳ lương')
        self.assertEqual(slots['period']['value_label'], '1 đến 31 tháng 12 năm 2031')
        self.assertEqual(slots['scheme']['label'], 'Chương trình lương')
        self.assertEqual(slots['scheme']['value_label'], 'Payai Retail End-Month')
        self.assertEqual(slots['people']['label'], 'Nhân viên')
        self.assertIn('Toàn bộ 3 người thuộc chương trình lương này', slots['people']['value_label'])
        notes = ' '.join(n['text'] for n in card['notes'])
        self.assertIn('Chưa có đợt lương tháng 12 năm 2031 cho Payai Retail End-Month.', notes)
        labels = [a['label'] for a in card['actions']]
        self.assertIn('Thực hiện', labels)
        self.assertIn('Hủy bỏ', labels)
        self.assertIn('Mở trên màn hình', labels)
        # FIX-1 (P4:test-7): no English word anywhere a person reads on the
        # card — inside sentences too, chips, hint and audit line included.
        # The names people gave (the scheme, the run) are theirs and stay.
        vals = json.loads(self._task(card).params_json)['vals']
        blob = ' | '.join(_shown_text(card))
        for name in (vals['name'], 'Payai Retail End-Month', 'PayAI'):
            blob = blob.replace(name, ' ')
        english = ('Run payroll', 'Period', 'Scheme', 'Do it', 'Cancel', 'to', 'December',
                   'Pay period', 'People', 'Everyone', 'Open', 'instead', 'the', 'and', 'No run')
        for word in english:
            self.assertFalse(re.search(r'(?<![\w])%s(?![\w])' % re.escape(word), blob),
                             '%r on a Vietnamese card: %s' % (word, blob[:300]))
        # The run is still NAMED the screen's way (the wizard names in English).
        self.assertEqual(vals['name'], 'Payai Retail End-Month · December 2031')

    def test_p4_02b_card_follows_the_users_own_language(self):
        """FIX-1 (P4:test-7): no language in the call's context — the card
        follows the asker's own language setting (`user.lang`)."""
        session = self._session(self.vi_officer)
        context = {k: v for k, v in self.env.context.items() if k != 'lang'}
        Conv = self.env['payroll.ai.conversation'].with_user(self.vi_officer).with_context(context)
        self.assertFalse(Conv.env.context.get('lang'))
        card = Conv.rpc_send_message('chạy lương tháng 12 năm 2031 cho Payai Retail End-Month',
                                     session.id, None)['card']
        self.assertEqual(card['title'], 'Chạy lương', card)
        # And an English user asking the same thing reads English.
        en = Conv.with_user(self.officer)
        card = en.rpc_send_message('Run December 2031 payroll for Payai Retail End-Month',
                                   self._session(self.officer).id, None)['card']
        self.assertEqual(card['title'], 'Run payroll', card)

    # ================================================================ 3
    def test_p4_03_vietnamese_confirm_words(self):
        approve, back, reject = ACTIONS['approve_item'], ACTIONS['send_back_item'], ACTIONS['reject_item']
        for word in ('DUYỆT', 'duyet', 'Duyệt', ' duyệt ', 'APPROVE', 'approve'):
            self.assertTrue(runner.word_ok(approve, word), word)
        for word in ('duyệt đi', 'aprove', 'TRẢ LẠI', ''):
            self.assertFalse(runner.word_ok(approve, word), word)
        for word in ('TRẢ LẠI', 'tra lai', 'trả  lại', 'SEND BACK'):
            self.assertTrue(runner.word_ok(back, word), word)
        for word in ('TỪ CHỐI', 'tu choi', 'REJECT'):
            self.assertTrue(runner.word_ok(reject, word), word)
        self._two_steps(first=[self.hoa])
        run, request = self._submitted()
        card, _s = self._send_vi(self.hoa, 'duyệt bảng lương tháng 6 năm 2031 Payai Retail')
        self.assertEqual((card['kind'], card['state']), ('plan', 'planned'), card)
        self.assertEqual(card['title'], 'Duyệt %s' % request.title)
        self.assertIn('PayAI không thể hoàn tác', card['subtitle'])
        typed = next(a for a in card['actions'] if a['id'] == 'typed')
        self.assertEqual(typed['word'], 'DUYỆT')
        self.assertEqual(set(typed['words']), {'APPROVE', 'DUYỆT'})
        self.assertIn('Gõ DUYỆT để xác nhận', typed['hint'])
        slots = {s['key']: s for s in card['slots']}
        self.assertEqual(slots['step']['value_label'], 'HR Manager check, bước 1 trên 2')
        self.assertTrue(slots['figures']['value_label'].startswith('1 người · thực nhận '))
        # The not-yours deep link and the inbox door carry this request.
        inbox = next(a for a in card['actions'] if a.get('door_id') == 'homehub_approvals')
        self.assertEqual(inbox['hub']['focus'], 'request:%s' % request.id)
        self.assertEqual(inbox['label'], 'Mở mục Phê duyệt')
        # A wrong word: the hint is Vietnamese and names the Vietnamese word.
        out = self._confirm_vi(self.hoa, card, word='duyệt đi')
        self.assertTrue(out.get('inline'), out)
        self.assertIn('Hãy gõ đúng DUYỆT', json.dumps(out, ensure_ascii=False))
        self.assertFalse(self._decisions(request))
        # A tap is still never enough, in Vietnamese too.
        out = self._confirm_vi(self.hoa, card, how='tap', word='DUYỆT')
        self.assertIn('Việc này cần gõ để xác nhận', json.dumps(out, ensure_ascii=False))
        self.assertFalse(self._decisions(request))
        # No marks, no capitals: it counts.
        done = self._confirm_vi(self.hoa, card, word='duyet')
        self.assertEqual(done['state'], 'done', done)
        self.assertEqual(len(self._decisions(request, self.hoa)), 1)
        self.assertIn('Đã duyệt ở bước HR Manager check', done['notes'][0]['text'])
        self.assertIn('Đã ghi lại: Hoa Payai đã duyệt qua PayAI', done['audit_line'])
        inbox = next(a for a in done['actions'] if a.get('door_id') == 'homehub_approvals')
        self.assertEqual(inbox['hub']['focus'], 'request:%s' % request.id)

    def test_p4_03b_send_back_in_vietnamese_with_the_english_word(self):
        self._two_steps(first=[self.hoa])
        run, request = self._submitted()
        card, _s = self._send_vi(
            self.hoa, 'trả lại bảng lương tháng 6 năm 2031 Payai Retail vì thiếu tăng ca')
        self.assertEqual(card['kind'], 'plan', card)
        typed = next(a for a in card['actions'] if a['id'] == 'typed')
        self.assertEqual(typed['word'], 'TRẢ LẠI')
        slots = {s['key']: s for s in card['slots']}
        self.assertEqual(slots['reason']['value_label'], 'thiếu tăng ca')
        self.assertEqual(slots['reason']['label'], 'Lý do')
        done = self._confirm_vi(self.hoa, card, word='send back')
        self.assertEqual(done['state'], 'done', done)
        request.invalidate_recordset()
        run.invalidate_recordset()
        self.assertEqual((request.state, request.return_note), ('returned', 'thiếu tăng ca'))
        self.assertEqual(run.state, 'draft')
        self.assertIn('Đã trả về cho Prep Payai kèm lý do của bạn. Đợt lương trở lại dạng nháp.',
                      json.dumps(done, ensure_ascii=False))

    # ================================================================ 6
    def test_p4_06_not_yours_card_opens_the_request(self):
        self._two_steps()
        run, request = self._submitted()
        card, _s = self._send_vi(self.lan, 'duyệt bảng lương tháng 6 năm 2031 Payai Retail')
        self.assertEqual(card['kind'], 'refused', card)
        self.assertEqual(card['title'], 'Việc này không chờ bạn')
        door = next(a for a in card['actions'] if a.get('door_id') == 'homehub_approvals')
        self.assertTrue(door['hub']['focus'].startswith('request:%s' % request.id), door)
        self.assertEqual(door['hub']['context']['pb_focus'], door['hub']['focus'])
        self.assertEqual([c['label'] for c in card['chips']], ['Nhắc Minh'])


# The P3 Red tests run once, in P3 — not again under this class.
for _name in dir(p3.TestPayaiP3Red):
    if (_name.startswith('test_') and callable(getattr(p3.TestPayaiP3Red, _name))
            and _name not in TestPayaiP4Vietnamese.__dict__):
        setattr(TestPayaiP4Vietnamese, _name, None)
