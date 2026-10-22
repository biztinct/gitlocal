# -*- coding: utf-8 -*-
"""LEARNING L7 — PayAI drafts a course from a document. Handover T7, T8, T10.

The rails: a draft that is published (or lands on somebody's own page), an
AI provider called when none is set up (or called at all from a test — the
provider here is a fake), a Word file refused only because a library is
missing, a file the person cannot read opened with sudo, an upload that is
read before its size is checked, a chat action that drafts or publishes
instead of opening a screen, and a vendor name or an English word on a
Vietnamese screen.

No test here reaches a real AI provider (`get_active_config` is replaced by
a fake for every class). Fixtures are "DEMO" and roll back; `lang='en_US'`
is pinned (LN14).
"""

import base64
import io
import os
import re
import types
import zipfile
from unittest.mock import patch

from odoo.exceptions import AccessError, UserError
from odoo.modules.module import get_module_path
from odoo.tests import TransactionCase, tagged

from odoo.addons.pb_training_payai.models.draft import (
    MAX_BYTES, docx_text, file_kind)

EMOJI = re.compile('[\U0001F300-\U0001FAFF☀-➿\U0001F000-\U0001F2FF]')


def _src(*parts):
    with open(os.path.join(get_module_path('pb_training_payai'), *parts),
              encoding='utf-8') as fh:
        return fh.read()


def _docx(paragraphs):
    xml = ('<?xml version="1.0" encoding="UTF-8"?>'
           '<w:document xmlns:w="http://schemas.openxmlformats.org/'
           'wordprocessingml/2006/main"><w:body>%s</w:body></w:document>') % ''.join(
        '<w:p><w:r><w:t>%s</w:t></w:r></w:p>' % p for p in paragraphs)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w') as zf:
        zf.writestr('[Content_Types].xml', '<Types/>')
        zf.writestr('word/document.xml', xml)
    return buf.getvalue()


DRAFT = {
    'title': 'DEMO Forklift safety',
    'blurb': 'How to drive a forklift safely in the warehouse.',
    'lessons': [
        {'title': 'Before you start', 'html': '<p>Check the forks.</p>'
         '<script>alert(1)</script>', 'minutes': 4},
        {'title': 'Driving', 'html': '<p>Slow in the aisles.</p>', 'minutes': 6},
        {'title': 'Parking', 'html': '<ul><li>Forks down.</li></ul>',
         'minutes': 3},
    ],
    'quiz': [{'question': 'DEMO question %s?' % n,
              'options': ['A', 'B', 'C', 'D'], 'correct': n % 4}
             for n in range(10)],
}


class _FakeProvider:
    calls = []

    def __init__(self, answer):
        self.answer = answer

    def generate_structured(self, prompt, schema_hint=None, max_tokens=2000,
                            temperature=0.3):
        _FakeProvider.calls.append(prompt)
        return self.answer

    def supports_vision(self):
        return False

    def accepts_pdf(self):
        return False


class _FakeConfig:
    provider_type = 'openai'
    model_name = 'demo-model'
    max_tokens = 2000

    def __init__(self, answer=DRAFT):
        self.answer = answer

    def __bool__(self):
        return True

    def get_provider(self):
        return _FakeProvider(self.answer)


class DraftCase(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, lang='en_US'))
        Users = cls.env['res.users'].with_context(no_reset_password=True)
        cls.trainer = Users.create({
            'name': 'DEMO L7 drafter', 'login': 'demo.l7.drafter@example.com',
            'email': 'demo.l7.drafter@example.com',
            'group_ids': [(6, 0, [cls.env.ref(
                'pb_training.group_training_user').id])]})
        cls.plain = Users.create({
            'name': 'DEMO L7 plain', 'login': 'demo.l7.plain@example.com',
            'group_ids': [(6, 0, [cls.env.ref('base.group_user').id])]})
        cls.Board = cls.env['pb.training']
        _FakeProvider.calls = []

    def setUp(self):
        super().setUp()
        _FakeProvider.calls = []

    def _with(self, config):
        """Every provider lookup answers `config` (a fake, or nothing)."""
        Cfg = type(self.env['payroll.ai.config'])
        return patch.object(Cfg, 'get_active_config',
                            lambda self_: config if config else
                            self_.browse())

    def _upload(self, user, name, raw, lang='en'):
        return self.Board.with_user(user).draft_upload(
            name, base64.b64encode(raw).decode(), lang)


# =========================================================================
#  T7 — the draft
# =========================================================================
@tagged('post_install', '-at_install')
class TestT7Draft(DraftCase):

    def test_t7_an_unpublished_course_with_lessons_and_a_quiz(self):
        text = b'DEMO forklift procedure. Check the forks. Drive slowly.'
        with self._with(_FakeConfig()):
            res = self._upload(self.trainer, 'forklift.txt', text)
        channel = self.env['slide.channel'].browse(res['channel_id'])
        self.assertFalse(channel.is_published, 'PayAI never publishes')
        self.assertEqual(channel.visibility, 'members')
        self.assertEqual(channel.enroll, 'invite')
        self.assertEqual(channel.channel_type, 'training')
        self.assertEqual(channel.name, 'DEMO Forklift safety')
        self.assertEqual(channel.user_id, self.trainer, 'made as the person')
        self.assertFalse(channel.channel_partner_ids.filtered('active'),
                         'a draft is nobody\'s course yet (LN46)')
        lessons = channel.slide_ids.filtered(
            lambda s: s.slide_category == 'article')
        self.assertEqual(len(lessons), 3)
        self.assertNotIn('<script', ''.join(str(s.html_content)
                                             for s in lessons))
        quiz = channel.slide_ids.filtered(
            lambda s: s.slide_category == 'quiz')
        self.assertEqual(len(quiz.question_ids), 10)
        for q in quiz.question_ids:
            self.assertEqual(len(q.answer_ids), 4)
            self.assertEqual(len(q.answer_ids.filtered('is_correct')), 1)
        self.assertEqual(res['lessons'], 3)
        self.assertEqual(res['questions'], 10)
        self.assertEqual(channel.pb_draft_source_id.name, 'forklift.txt')
        self.assertEqual(channel.pb_draft_source_id.res_id, channel.id)
        note = channel.message_ids.filtered(
            lambda m: 'Drafted by PayAI from forklift.txt' in (m.body or ''))
        self.assertTrue(note, 'the chatter says who, from which file, how')
        self.assertIn('demo-model', note[0].body)
        self.assertIn('DEMO forklift procedure', _FakeProvider.calls[-1])
        drawer = self.Board.with_user(self.trainer).get_course(channel.id)
        self.assertEqual(drawer['draft']['words'],
                         'Drafted by PayAI from forklift.txt. Read every '
                         'lesson before you publish.')
        # A learner never sees a draft: the facade's membership gate wants a
        # published course.
        self.assertIsNone(self.env['pb.my.training'].with_user(
            self.trainer).course(channel.id))

    def test_t7_no_provider_is_a_sentence_and_nothing_is_sent(self):
        with self._with(None):
            with self.assertRaises(UserError) as caught:
                self._upload(self.trainer, 'forklift.txt', b'DEMO words here')
            setup = self.Board.with_user(self.trainer).draft_setup()
        self.assertIn('PayAI is not set up for documents yet',
                      str(caught.exception))
        self.assertIn('Settings › PayAI', str(caught.exception))
        self.assertFalse(setup['ready'])
        self.assertFalse(_FakeProvider.calls)

    def test_t7_a_word_file_is_read_without_python_docx(self):
        raw = _docx(['DEMO Procedure', 'Check the forks every morning.'])
        self.assertEqual(file_kind('p.docx', raw), 'docx')
        with patch.dict('sys.modules', {'docx': None}):
            self.assertIn('Check the forks', docx_text(raw))
            with self._with(_FakeConfig()):
                res = self._upload(self.trainer, 'procedure.docx', raw)
        self.assertTrue(res['channel_id'])
        self.assertIn('Check the forks every morning.',
                      _FakeProvider.calls[-1])

    def test_t7_an_unreadable_word_file_says_save_as_pdf(self):
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, 'w') as zf:
            zf.writestr('word/document.xml', 'not xml at all <<<')
        with patch.dict('sys.modules', {'docx': None}), \
                self._with(_FakeConfig()):
            with self.assertRaises(UserError) as caught:
                self._upload(self.trainer, 'broken.docx', buf.getvalue())
        self.assertIn('Save it as a PDF first', str(caught.exception))

    def test_t7_a_plain_user_is_refused(self):
        with self._with(_FakeConfig()):
            with self.assertRaises(AccessError):
                self._upload(self.plain, 'forklift.txt', b'DEMO words')
            with self.assertRaises(AccessError):
                self.Board.with_user(self.plain).draft_setup()

    def test_t7_never_sudo_on_a_file_the_person_cannot_read(self):
        # An attachment on no record, made by somebody else, is readable by
        # its maker only.
        att = self.env['ir.attachment'].with_user(self.plain).create({
            'name': 'DEMO private.txt', 'datas': base64.b64encode(b'secret'),
            'res_model': False, 'res_id': 0})
        with self._with(_FakeConfig()):
            with self.assertRaises(AccessError):
                self.Board.with_user(self.trainer).draft_course(att.id, 'en')
            self.assertEqual(self.Board.with_user(
                self.trainer).draft_attachment_info(att.id), {})
        self.assertFalse(_FakeProvider.calls, 'nothing was sent')

    def test_t7_uploads_are_bounded_and_checked(self):
        with self._with(_FakeConfig()):
            big = 'A' * ((MAX_BYTES * 4) // 3 + 100)
            with self.assertRaises(UserError) as caught:
                self.Board.with_user(self.trainer).draft_upload(
                    'big.txt', big, 'en')
            self.assertIn('larger than 10 MB', str(caught.exception))
            with self.assertRaises(UserError) as caught:
                self._upload(self.trainer, 'picture.png',
                             b'\x89PNG\r\n\x1a\n' + b'\x00' * 20)
            self.assertIn('a PDF, a Word file or a text file',
                          str(caught.exception))
        self.assertFalse(_FakeProvider.calls)

    def test_t7_a_useless_answer_is_a_sentence(self):
        with self._with(_FakeConfig(answer={'title': 'x', 'lessons': []})):
            with self.assertRaises(UserError) as caught:
                self._upload(self.trainer, 'forklift.txt', b'DEMO words')
        self.assertIn('did not return a course', str(caught.exception))

    def test_t7_vietnamese_draft_is_written_in_vietnamese(self):
        if not self.env['res.lang'].sudo().search_count(
                [('code', '=', 'vi_VN'), ('active', '=', True)]):
            self.skipTest('Vietnamese is not installed on this database')
        with self._with(_FakeConfig()):
            res = self._upload(self.trainer, 'forklift.txt', b'DEMO words',
                               lang='vi')
        self.assertIn('Vietnamese', _FakeProvider.calls[-1])
        channel = self.env['slide.channel'].browse(res['channel_id'])
        self.assertEqual(channel.with_context(lang='vi_VN').name,
                         'DEMO Forklift safety')


# =========================================================================
#  T8 — the PayAI action: tier prepare, opens the drawer, nothing else
# =========================================================================
@tagged('post_install', '-at_install')
class TestT8Action(DraftCase):

    def _ctx(self, user):
        return types.SimpleNamespace(env=self.env(user=user.id), user=user,
                                     task=None, params={}, cache={},
                                     has_door=lambda d: True)

    def test_t8_registered_as_prepare(self):
        from odoo.addons.pb_payai_actions.payai.registry import ACTIONS, match
        action = ACTIONS['draft_course']
        self.assertEqual(action.tier, 'prepare')
        self.assertFalse(action.stub)
        self.assertEqual(action.screen_keys, ('pb_learning_hub.item_learning',))
        self.assertTrue(action.method_gate(self.env, self.trainer))
        self.assertFalse(action.method_gate(self.env, self.plain))
        got = match('Draft a course from the forklift procedure')
        self.assertEqual(got and got[0], 'draft_course')
        self.assertEqual(got[1].get('file'), 'forklift procedure')
        got = match('soạn khóa học từ tài liệu an toàn xe nâng')
        self.assertEqual(got and got[0], 'draft_course')
        self.assertIsNone(match('How do I draft a course from a file?'))

    def test_t8_it_only_opens_the_drawer(self):
        from odoo.addons.pb_payai_actions.payai.registry import ACTIONS
        action = ACTIONS['draft_course']
        att = self.env['ir.attachment'].with_user(self.trainer).create({
            'name': 'DEMO zqlift procedure.pdf', 'mimetype': 'application/pdf',
            'datas': base64.b64encode(b'%PDF-1.4 demo'),
            'res_model': 'slide.channel', 'res_id': 0})
        ctx = self._ctx(self.trainer)
        slot = action.resolve_slot(ctx, action.slots[0], 'zqlift')
        self.assertEqual(slot['status'], 'resolved')
        self.assertEqual(slot['value'], att.id)
        out = action.plan(ctx, {'file': slot})
        acts = out['card']['actions']
        self.assertFalse([a for a in acts if a['id'] == 'do'],
                         'no "Do it": the chat never drafts')
        door = next(a for a in acts if a['id'] == 'door')
        self.assertEqual(door['hub']['lens'], 'courses')
        self.assertEqual(door['hub']['xmlid'],
                         'pb_learning_hub.action_pb_learning_hub')
        self.assertEqual(door['hub']['context'], {
            'pb_training_new_course': 'payai',
            'pb_training_draft_attachment': att.id})
        self.assertEqual(out['vals'], {'attachment_id': att.id})
        before = self.env['slide.channel'].search_count([])
        self.assertEqual(self.env['slide.channel'].search_count([]), before)

    def test_t8_it_finds_only_what_the_person_can_read(self):
        from odoo.addons.pb_payai_actions.payai.registry import ACTIONS
        action = ACTIONS['draft_course']
        self.env['ir.attachment'].with_user(self.plain).create({
            'name': 'DEMO hidden zqhide.txt', 'mimetype': 'text/plain',
            'datas': base64.b64encode(b'x'), 'res_model': False, 'res_id': 0})
        slot = action.resolve_slot(self._ctx(self.trainer), action.slots[0],
                                   'zqhide')
        self.assertEqual(slot['status'], 'missing')

    def test_t8_the_arrival_opens_new_course(self):
        """The Courses lens reads the door's context (training_palette.js)
        and the board opens its "New course" drawer on PayAI's way."""
        pal = open(os.path.join(get_module_path('pb_training'), 'static', 'src',
                                'js', 'training_palette.js'),
                   encoding='utf-8').read()
        self.assertIn('pb_training_new_course', pal)
        self.assertIn('pb_training_draft_attachment', pal)
        self.assertIn('registry.category(NEW_COURSE_WAYS).add("payai"',
                      _src('static', 'src', 'js', 'draft_way.js'))


# =========================================================================
#  T10 — words
# =========================================================================
@tagged('post_install', '-at_install')
class TestT10Words(DraftCase):

    FILES = (('models', 'draft.py'), ('payai', 'action_draft_course.py'),
             ('static', 'src', 'js', 'draft_way.js'),
             ('static', 'src', 'xml', 'draft_way.xml'),
             ('static', 'src', 'scss', 'draft_way.scss'),
             ('__manifest__.py',))

    def test_t10_no_vendor_word_no_emoji(self):
        for rel in self.FILES:
            text = _src(*rel)
            for line in text.splitlines():
                if 'odoo' in line.lower() and not re.search(
                        r'from odoo|import odoo|odoo-module|odoo\.|@odoo',
                        line):
                    self.fail('%s: %s' % ('/'.join(rel), line.strip()))
            self.assertFalse(EMOJI.search(text), rel)
        self.assertIn('Do not name any software product', _src('models',
                                                                'draft.py'))

    def test_t10_vietnamese(self):
        po = _src('i18n', 'vi_VN.po')
        for msgid in ('Draft it with PayAI from a document', 'Draft the course',
                      'Choose a file', 'Write it in',
                      'Draft a course from a document',
                      'Open New course with this file'):
            m = re.search(r'msgid "%s"\nmsgstr "([^"]+)"' % re.escape(msgid), po)
            self.assertTrue(m and m.group(1), 'no Vietnamese for %r' % msgid)
        self.assertIn('PayAI is not set up for documents yet', po)
