# -*- coding: utf-8 -*-
"""Owner ruling PA1 (2026-11-16): HR reads the questions, never who asked.
Numbered PA1-1 … PA1-7 in the report."""
import io
import zipfile

from odoo import fields, http
from odoo.exceptions import AccessError
from odoo.tests import HttpCase, TransactionCase, tagged

from odoo.addons.pb_me_portal.tests.test_portal_accounts import _pin_dbfilter

from ..models.policy_answer import MIN_PEOPLE_FOR_QUESTIONS, QUOTA_SECRET_PARAM
from .common import PASSWORD, FakeProvider, make_world, stub

PERSON_MODELS = ('hr.employee', 'hr.employee.public', 'res.users', 'res.partner',
                 'hr.version', 'res.device', 'res.device.log')
NAME_QUESTION = ('Hi, I am Trần Thị DEMO Lụa, phone +84 912 345 678, '
                 'demo.lua.s6b@example.com. How many days of wedding leave do I get?')


def _columns(env, table):
    env.cr.execute("SELECT column_name FROM information_schema.columns "
                   "WHERE table_name = %s", (table,))
    return {r[0] for r in env.cr.fetchall()}


def _enough_people(env, company, prefix):
    """Make sure `company` has at least the minimum of people with a login."""
    Answer = env['pb.policy.answer']
    n = 0
    while Answer._people_who_could_ask(company) < MIN_PEOPLE_FOR_QUESTIONS:
        n += 1
        user = env['res.users'].with_context(no_reset_password=True).create({
            'name': 'DEMO S6B Colleague %s' % n, 'login': '%s_c%s' % (prefix, n),
            'company_id': company.id, 'company_ids': [(6, 0, company.ids)],
            'group_ids': [(6, 0, [env.ref('base.group_portal').id])]})
        env['hr.employee'].create({'name': 'DEMO S6B Colleague %s' % n,
                                   'user_id': user.id, 'company_id': company.id})


@tagged('post_install', '-at_install', 'wdgap_s6b')
class TestPolicyQuestions(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        make_world(cls, 'wdgap_s6b_pq')

    def _ask(self, question, fake=None):
        with stub(self.env, fake or FakeProvider()):
            return self.Answer.with_user(self.share).ask(self.emp.sudo(), question)

    def _rows(self):
        return self.env['pb.policy.question'].sudo().search(
            [('company_id', '=', self.company.id)])

    # PA1-1 — the row: scrubbed question, day only, NOTHING about the person
    def test_pa1_01_row_holds_no_person(self):
        self._ask(NAME_QUESTION)
        row = self._rows()[:1]
        self.assertEqual(row.day, fields.Date.today())
        for secret in ('Trần Thị DEMO Lụa', 'Lụa', '912 345 678',
                       'demo.lua.s6b@example.com'):
            self.assertNotIn(secret, row.question, 'PA1-1: %s kept' % secret)
        self.assertIn('[person-', row.question)
        self.assertIn('wedding leave', row.question)
        cols = _columns(self.env, 'pb_policy_question')
        self.assertTrue(cols <= {'id', 'company_id', 'day', 'question', 'outcome',
                                 'called_ai', 'section_id'}, cols)
        for stamp in ('create_uid', 'write_uid', 'create_date', 'write_date',
                      'employee_id', 'user_id', 'partner_id'):
            self.assertNotIn(stamp, cols)
        Q = self.env['pb.policy.question']
        for name, field in Q._fields.items():
            if field.relational:
                self.assertNotIn(field.comodel_name, PERSON_MODELS,
                                 'PA1-1: %s points at a person' % name)

    # PA1-2 — the per-person counter: separate, coded, today only
    def test_pa1_02_counter_cannot_be_joined(self):
        self._ask('How many days of wedding leave?')
        cols = _columns(self.env, 'pb_policy_quota')
        self.assertTrue(cols <= {'id', 'key', 'day', 'count'}, cols)
        quota = self.env['pb.policy.quota'].sudo().search([])
        self.assertEqual(len(quota), 1)
        self.assertNotIn(str(self.emp.id), [quota.key])
        self.assertNotIn(self.share.login, quota.key)
        today = fields.Date.today()
        other_day = self.Answer._quota_key(self.emp, fields.Date.add(today, days=-1))
        self.assertNotEqual(other_day, quota.key, 'a new code every day')
        # an old day's counter is deleted on the next question
        quota.write({'day': fields.Date.add(today, days=-1)})
        self._ask('How many days of wedding leave?')
        self.assertFalse(self.env['pb.policy.quota'].sudo().search(
            [('day', '<', today)]), 'PA1-2: no history of who asked how much')
        Q = self.env['pb.policy.question']
        for field in Q._fields.values():
            self.assertNotEqual(getattr(field, 'comodel_name', None), 'pb.policy.quota')

    # PA1-3 — HR with every HR right has no path from a question to a person
    def test_pa1_03_hr_has_no_path_to_a_person(self):
        _enough_people(self.env, self.company, 'wdgap_s6b_pq3')
        self._ask(NAME_QUESTION)
        hr = self.hr_manager
        hr.write({'group_ids': [(4, self.env.ref('hr.group_hr_user').id)]})
        self.env.flush_all()
        self.env.invalidate_all()
        for model in ('pb.policy.question', 'pb.policy.quota'):
            with self.assertRaises(AccessError, msg=model):
                self.env[model].with_user(hr).search_read([], [])
        secret = self.env['ir.config_parameter'].with_user(hr).sudo(False)
        try:
            got = secret.search_read([('key', '=', QUOTA_SECRET_PARAM)], ['value'])
        except AccessError:
            got = []
        self.assertFalse(got, 'PA1-3: HR cannot read the counter secret')
        rows = self.env['pb.policy.desk'].with_user(hr).get_questions('all')
        self.assertTrue(rows)
        self.assertEqual(set(rows[0]), {'day', 'question', 'policy', 'section',
                                        'answered', 'outcome'})
        for row in rows:
            self.assertNotIn('Lụa', row['question'])
        self.assertFalse(self.env['mail.message'].sudo().search_count(
            [('model', '=', 'pb.policy.question')]), 'no chatter on question rows')

    # PA1-4 — small company: numbers only
    def test_pa1_04_small_company_numbers_only(self):
        small = self.env['res.company'].create({'name': 'DEMO S6B Tiny Co'})
        self.assertLess(self.Answer._people_who_could_ask(small), MIN_PEOPLE_FOR_QUESTIONS)
        self.assertFalse(self.Answer._questions_shown(small))
        self.assertEqual(self.Answer._question_rows(small, 'all'), [])
        hr = self.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'DEMO S6B Tiny HR', 'login': 'wdgap_s6b_pq_tinyhr',
            'company_id': small.id, 'company_ids': [(6, 0, small.ids)],
            'group_ids': [(6, 0, [self.env.ref('base.group_user').id,
                                  self.env.ref('hr.group_hr_manager').id])]})
        Desk = self.env['pb.policy.desk'].with_user(hr).with_context(allowed_company_ids=small.ids)
        self.assertFalse(Desk.get_desk()['questions_shown'])
        self.assertEqual(Desk.get_questions('all'), [])

    # PA1-5 — "Could not answer" first; answered ones on their own filter
    def test_pa1_05_could_not_answer_first(self):
        _enough_people(self.env, self.company, 'wdgap_s6b_pq5')
        self._ask('How many days of wedding leave?')
        self._ask('Can I bring my dog to the office?')
        Desk = self.env['pb.policy.desk'].with_user(self.hr)
        default = Desk.get_questions()
        self.assertEqual([r['question'] for r in default], ['Can I bring my dog to the office?'])
        self.assertFalse(default[0]['answered'])
        answered = Desk.get_questions('answered')
        self.assertEqual(len(answered), 1)
        self.assertEqual(answered[0]['policy'], 'DEMO Staff handbook')
        self.assertEqual(answered[0]['section'], '2. Wedding leave')
        self.assertEqual(len(Desk.get_questions('all')), 2)


@tagged('post_install', '-at_install', 'wdgap_s6b')
class TestPolicyQuestionsDownload(HttpCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        _pin_dbfilter(cls)
        make_world(cls, 'wdgap_s6b_pqd', PASSWORD)

    # PA1-6 — the Excel file: questions without names, HR only
    def test_pa1_06_excel_download(self):
        _enough_people(self.env, self.company, 'wdgap_s6b_pqd6')
        with stub(self.env, FakeProvider()):
            self.Answer.with_user(self.share).ask(self.emp.sudo(), NAME_QUESTION)
            self.Answer.with_user(self.share).ask(self.emp.sudo(), 'Can I bring my dog to work?')
        url = '/pb_me_payai/questions.xlsx?company_id=%s&which=all' % self.company.id
        self.authenticate(self.hr.login, PASSWORD)
        res = self.url_open(url, timeout=60)
        self.assertEqual(res.status_code, 200)
        self.assertIn('spreadsheetml', res.headers.get('Content-Type', ''))
        with zipfile.ZipFile(io.BytesIO(res.content)) as zf:
            strings = zf.read('xl/sharedStrings.xml').decode()
        self.assertIn('Can I bring my dog to work?', strings)
        self.assertIn('wedding leave', strings)
        self.assertNotIn('Lụa', strings)
        self.assertNotIn('912 345 678', strings)
        # an employee login, and a plain staff login, get nothing
        for user in (self.share, self.plain):
            self.authenticate(user.login, PASSWORD)
            res = self.url_open(url, timeout=60)
            self.assertNotEqual(res.status_code, 200, user.login)

    # PA1-7 — small company: no file
    def test_pa1_07_no_file_in_a_small_company(self):
        small = self.env['res.company'].create({'name': 'DEMO S6B Tiny Download Co'})
        self.hr.write({'company_ids': [(4, small.id)]})
        self.authenticate(self.hr.login, PASSWORD)
        res = self.url_open('/pb_me_payai/questions.xlsx?company_id=%s' % small.id, timeout=60)
        self.assertEqual(res.status_code, 404)
