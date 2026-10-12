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
from odoo.tools.translate import PoFileReader

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


def _payai_literals():
    """(source, file) for every translatable literal pb_payai_actions shows:
    _lt/_ in Python (an Action's `summary` excepted: only the model reads
    it) and _t in the JavaScript."""
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
                if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                        and node.func.id in ('_lt', '_') and node.args
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
    return found


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
        # pb_payai_actions: every entry has its module line FIRST, a marker
        # and a code occurrence (or a model one) — the three things a .po
        # entry needs (po-translation-loading-rules).
        path = os.path.join(get_module_path('pb_payai_actions'), 'i18n', 'vi_VN.po')
        text = open(path, encoding='utf-8').read()
        for block in text.split('\n\n')[1:]:
            lines = [l for l in block.strip().split('\n') if l]
            if not lines:
                continue
            self.assertTrue(lines[0].startswith('#. module: pb_payai_actions'), block[:120])
            occ = [l for l in lines if l.startswith('#: ')]
            self.assertTrue(occ, block[:120])
            if any(o.startswith('#: code:') for o in occ):
                self.assertTrue(any(l in ('#. odoo-python', '#. odoo-javascript') for l in lines),
                                block[:120])
                self.assertTrue(all(re.match(r'#: (code:addons/pb_payai_actions/\S+:\d+|model)', o)
                                    for o in occ), block[:120])

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
        self.assertIn('currentAction', src)          # a lens reads the hub's context

    # =============================================================== 10
    def test_10_no_odoo_on_any_card(self):
        root = get_module_path('pb_payai_actions')
        cat = _catalogue('pb_payai_actions')
        for src, vi in cat.items():
            self.assertNotIn('odoo', src.lower(), src)
            self.assertNotIn('odoo', vi.lower(), vi)
        for src, _f in _payai_literals():
            self.assertNotIn('odoo', src.lower(), src)
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
        self.assertIn('Mở trên màn hình thay vào đó', labels)
        english = ('Run payroll', 'Period', 'Scheme', 'Do it', 'Cancel', ' to ', 'December')
        blob = json.dumps({k: card[k] for k in ('title', 'subtitle', 'slots', 'notes', 'actions')},
                          ensure_ascii=False)
        for word in english:
            self.assertNotIn('"%s"' % word if ' ' not in word else word, blob, word)
        # The run is still NAMED the screen's way (the wizard names in English).
        vals = json.loads(self._task(card).params_json)['vals']
        self.assertEqual(vals['name'], 'Payai Retail End-Month · December 2031')

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
        self.assertEqual(inbox['label'], 'Mở mục Phê duyệt của tôi thay vào đó')
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
