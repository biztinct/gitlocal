# -*- coding: utf-8 -*-
"""WDGAP Step 9 merge seams (S9-A review forms, S9-B conduct cases and people
reports, S9-C employee voice) on the MERGED tree. Deploy handover §1 c–e.

M1 (c) employee home: the "Needs you" hooks of the three modules stack (each
   calls super()), the review, survey and HR-letter rows appear together, the
   letter row stays neutral; the home payload still builds.
M2 (d) privacy matrix as each role: payroll officer, payroll manager, general
   HR, lifecycle user, un-named administrator, line manager, another employee,
   the employee — conduct case / notes / files / letters / document copies;
   finished review document / PDF / answers / comments; survey answers; people
   reports.
M3 (e) one employee with BOTH a filed conduct letter and a filed review PDF:
   each document stays under its own rule; other documents unchanged for
   payroll.
M4 (S5-F 5b) the report preview / PDF page title is the report's own name for
   a finished review, a conduct letter and a payslip — never the platform's.
M5 (S5-F TP3) the late-minutes door on My Overtime and the Step 9 home
   entries live side by side.

Skipped unless pb_conduct, pb_people_reports and pb_voice are installed with
this module (the merged deploy installs all four).
"""

import base64

from odoo.exceptions import AccessError
from odoo.tests import tagged

from .test_review_forms import RFCase

NEUTRAL_BANNED = ('warning', 'disciplin', 'conduct', 'dismiss', 'hearing')


@tagged('post_install', '-at_install', 'wdgap_s9m')
class TestS9MergeSeams(RFCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        cls.ready = all(m in env for m in (
            'pb.conduct.case', 'pb.people.reports', 'pb.voice.round'))
        if not cls.ready:
            return
        Users = env['res.users'].with_context(no_reset_password=True)

        def user(login, groups):
            refs = [env.ref(x, raise_if_not_found=False) for x in groups]
            return Users.create({
                'name': 'DEMO S9M %s' % login,
                'login': 'demo.s9m.%s@example.com' % login,
                'company_id': cls.company.id,
                'company_ids': [(6, 0, [cls.company.id])],
                'group_ids': [(6, 0, [r.id for r in refs if r])],
            })

        cls.payroll_officer = user('po', ['base.group_user',
                                          'om_hr_payroll.group_hr_payroll_user',
                                          'pb_hr_payroll_base.group_payroll_base_officer'])
        cls.payroll_manager = user('pm', ['base.group_user',
                                          'om_hr_payroll.group_hr_payroll_manager'])
        cls.general_hr = user('hr', ['base.group_user', 'hr.group_hr_user'])
        cls.lifecycle_user = user('lc', ['base.group_user',
                                         'pb_lifecycle.group_lifecycle_user'])
        cls.admin_unnamed = user('adm', ['base.group_user', 'base.group_system',
                                         'hr.group_hr_manager'])
        # the people who run each thing
        cls.conduct_named = user('cn', ['base.group_user', 'hr.group_hr_user',
                                        'pb_conduct.group_conduct_user'])
        # W3-A (ruling CD1): a second named person gives the second sign-off
        cls.conduct_second = user('cn2', ['base.group_user', 'pb_conduct.group_conduct_user'])
        cls.voice_hr = user('vh', ['base.group_user', 'hr.group_hr_user'])
        # review HR also needs the HR officer right the documents ask for
        cls.hr_user.write({'group_ids': [(4, env.ref('hr.group_hr_user').id)]})

        # enough people in the company for a survey round (floor 5)
        Emp = env['hr.employee']
        cls.extra = Emp.create([{'name': 'DEMO S9M extra %d' % i,
                                 'company_id': cls.company.id} for i in range(3)])

        # ---- a conduct case on the employee, up to an issued decision letter
        F = env['pb.conduct'].with_user(cls.conduct_named).with_context(
            allowed_company_ids=cls.company.ids)
        reason = env.ref('pb_conduct.reason_attendance')
        cid = F.create_case({'employee_id': cls.staff.id, 'reason_id': reason.id,
                             'summary': 'S9M-SECRET-SUMMARY',
                             'incident_date': '2026-05-31', 'raised_by': 'S9M lead'})['id']
        cls.case = env['pb.conduct.case'].browse(cid)
        F.add_note(cid, 'investigation', 'S9M-SECRET-NOTE')
        F.add_file(cid, 'evidence.txt', base64.b64encode(b'S9M-SECRET-FILE').decode())
        F.move(cid, 'plan_hearing', {'hearing_date': '2026-06-10 03:00:00',
                                     'place': 'Room 2', 'attendees': 'HR'})
        F.move(cid, 'invite')
        invite = cls.case.letter_ids.filtered(lambda l: l.kind == 'invite')
        F.issue_letter(invite.id)
        F.move(cid, 'hearing_held', {'held_on': '2026-06-10', 'minutes': 'S9M-MINUTES'})
        F.move(cid, 'decide', {'outcome': 'written', 'summary': 'S9M decision.'})
        cls.letter = cls.case.letter_ids.filtered(lambda l: l.kind == 'written')
        F.move(cid, 'ask_signoff')
        env['pb.conduct'].with_user(cls.conduct_second).with_context(
            allowed_company_ids=cls.company.ids).move(cid, 'confirm_signoff')
        cls.letter_doc = cls.letter.document_id
        cls.case_note = env['pb.conduct.note'].sudo().search([('case_id', '=', cid)], limit=1)
        cls.case_file = env['ir.attachment'].sudo().search(
            [('res_model', '=', 'pb.conduct.case'), ('res_id', '=', cid)], limit=1)

        # ---- an open survey round that asks the employee
        Round = env['pb.voice.round'].with_user(cls.voice_hr).with_context(
            allowed_company_ids=cls.company.ids)
        cls.round = Round.create({'name': 'DEMO S9M pulse', 'company_id': cls.company.id,
                                  'company_ids': [(6, 0, cls.company.ids)]})
        env['pb.voice.question'].with_user(cls.voice_hr).with_context(
            allowed_company_ids=cls.company.ids).create({
                'round_id': cls.round.id, 'kind': 'scale', 'theme': 'manager',
                'sequence': 1, 'text': 'DEMO My manager listens.'})
        cls.round.action_open()

    @classmethod
    def tearDownClass(cls):
        if getattr(cls, 'ready', False):
            cls.env['pb.voice.box']._voice_destroy(cls.round.id)
        super().tearDownClass()

    def setUp(self):
        super().setUp()
        if not self.ready:
            self.skipTest('needs pb_conduct, pb_people_reports and pb_voice')

    # ----------------------------------------------------------- helpers
    def _reads(self, user, record, fname):
        self.env.flush_all()
        self.env.invalidate_all()
        try:
            with self.env.cr.savepoint():
                rec = record.with_user(user).with_context(
                    allowed_company_ids=[self.company.id])
                rec.check_access('read')
                rec.read([fname])
            return True
        except AccessError:
            return False

    def _finished_review(self):
        form = self._form()
        sheet, review = self._review()
        self._send_self(review, form)
        self._finish(review, form)
        entry = self._entry(review)
        self.assertTrue(entry.document_id.pb_rf_private)
        return sheet, review, entry

    def _needs(self, user, emp):
        found = {}
        self.env['pb.me.home'].with_user(user)._pbme_needs_extra(
            emp, lambda key, n, url, **kw: n and found.setdefault(
                key, dict(kw, n=n, url=url)))
        return found

    # ================================================================ M1
    def test_m1_needs_you_rows_stack(self):
        self._form()
        self._review()
        rows = self._needs(self.staff_user, self.staff)
        self.assertIn('review_self', rows, rows)
        self.assertIn('voice_survey', rows, rows)
        self.assertIn('hr_letters', rows, rows)
        self.assertEqual(rows['hr_letters']['url'], '/my/letters')
        self.assertEqual(rows['hr_letters']['n'], 2)   # invitation + decision
        words = ' '.join(str(rows['hr_letters'].get(k) or '')
                         for k in ('label', 'sub', 'sentence')).lower()
        for banned in NEUTRAL_BANNED:
            self.assertNotIn(banned, words)
        # a colleague with none of the three sees none of them, and only the
        # survey (everyone in the company was asked)
        other = self._needs(self.stranger_user, self.stranger)
        self.assertNotIn('hr_letters', other)
        self.assertNotIn('review_self', other)
        self.assertIn('voice_survey', other)
        # the whole home payload still builds with all three hooks
        data = self.env['pb.me.home'].with_user(self.staff_user).get_home_data(self.staff)
        keys = {r['key'] for r in data['needs_you']}
        self.assertTrue({'review_self', 'voice_survey', 'hr_letters'} <= keys, keys)
        urls = {t['url'] for t in data['tiles']}
        self.assertTrue({'/my/review', '/my/letters', '/my/voice'} <= urls, urls)

    # ================================================================ M2
    def test_m2_privacy_matrix(self):
        _sheet, review, entry = self._finished_review()
        doc, doc_file = entry.document_id, entry.document_id.attachment_id
        entry_file, answer = entry.attachment_id, entry.answer_ids[:1]
        conduct_records = {
            'case': (self.case, 'summary'),
            'note': (self.case_note, 'body'),
            'case file': (self.case_file, 'datas'),
            'letter': (self.letter, 'body'),
            'letter PDF': (self.letter.attachment_id, 'datas'),
        }
        roles = {
            'payroll officer': self.payroll_officer,
            'payroll manager': self.payroll_manager,
            'general HR': self.general_hr,
            'lifecycle user': self.lifecycle_user,
            'un-named administrator': self.admin_unnamed,
            'line manager': self.boss_user,
            'another employee': self.stranger_user,
            'the employee': self.staff_user,
        }
        Reports = self.env['pb.people.reports']
        for word, user in roles.items():
            # conduct: nothing at all, except the employee's own finished letter copy
            for what, (rec, fname) in conduct_records.items():
                if rec:
                    self.assertFalse(self._reads(user, rec, fname), '%s: conduct %s' % (word, what))
            self.assertFalse(self.env['pb.conduct'].with_user(user).can_open(),
                             word + ': conduct board')
            self.assertEqual(
                self._reads(user, self.letter_doc, 'name'), user == self.staff_user,
                word + ': conduct letter copy in documents')
            # review: only the employee, their manager (the review row) and review HR
            mine = user == self.staff_user
            self.assertEqual(self._reads(user, doc, 'name'), mine, word + ': review document')
            self.assertEqual(self._reads(user, doc_file, 'datas'), mine, word + ': review PDF')
            self.assertFalse(self._reads(user, entry_file, 'datas'), word + ': PDF on the review')
            self.assertFalse(self._reads(user, entry, 'overall_comment'), word + ': review entry')
            self.assertFalse(self._reads(user, answer, 'text'), word + ': review answers')
            self.assertEqual(self._reads(user, review, 'manager_note'),
                             user in (self.staff_user, self.boss_user),
                             word + ': overall comment')
            # survey answers: no model a person can read at all
            with self.assertRaises(AccessError, msg=word + ': survey box'):
                self.env['pb.voice.box'].with_user(user).search([])
            # people reports: HR only, never the payroll team
            self.assertEqual(Reports.with_user(user)._can_read(),
                             user in (self.general_hr, self.admin_unnamed),
                             word + ': people reports')
        # the people who run each thing
        self.assertTrue(self._reads(self.conduct_named, self.case, 'summary'))
        self.assertTrue(self._reads(self.conduct_named, self.letter_doc, 'name'))
        for rec, fname in ((doc, 'name'), (doc_file, 'datas'), (entry, 'overall_comment'),
                           (answer, 'text'), (review, 'manager_note')):
            self.assertTrue(self._reads(self.hr_user, rec, fname), rec._name)
        with self.assertRaises(AccessError):
            self.env['pb.voice.box'].with_user(self.voice_hr).search([])
        # the answer store carries nothing that points at a person
        box_links = [f.comodel_name for f in self.env['pb.voice.box']._fields.values()
                     if f.type in ('many2one', 'one2many', 'many2many')]
        self.assertEqual(box_links, ['pb.voice.round'])

    # ================================================================ M3
    def test_m3_two_private_documents_on_one_person(self):
        _sheet, _review, entry = self._finished_review()
        review_doc = entry.document_id
        self.assertEqual(review_doc.employee_id, self.staff)
        self.assertEqual(self.letter_doc.employee_id, self.staff)
        Doc = self.env['pb.employee.document']
        att = self.env['ir.attachment'].create({'name': 'DEMO s9m contract.pdf', 'raw': b'DEMO'})
        plain = Doc.sudo().create({
            'employee_id': self.staff.id, 'name': 'DEMO s9m contract',
            'category_id': self.env.ref('pb_employee_vault.cat_other').id,
            'attachment_id': att.id, 'company_id': self.company.id})
        att.write({'res_model': 'pb.employee.document', 'res_id': plain.id})

        def visible(user):
            self.env.invalidate_all()
            return set(Doc.with_user(user).with_context(
                allowed_company_ids=[self.company.id]).search(
                    [('employee_id', '=', self.staff.id)]).ids)

        expect = {
            # payroll: the ordinary document only
            self.payroll_officer: {plain.id},
            self.payroll_manager: {plain.id},
            # review HR (not named for conduct): review yes, conduct letter no
            self.hr_user: {plain.id, review_doc.id},
            # conduct-named HR without review rights: letter yes, review no
            self.conduct_named: {plain.id, self.letter_doc.id},
            # general HR: neither
            self.general_hr: {plain.id},
        }
        for user, ids in expect.items():
            got = visible(user)
            self.assertEqual(got & {plain.id, review_doc.id, self.letter_doc.id}, ids,
                             user.login)
        # the employee: all three of their own
        self.assertTrue({plain.id, review_doc.id, self.letter_doc.id} <= visible(self.staff_user))
        # the categories stay apart
        self.assertNotEqual(review_doc.category_id, self.letter_doc.category_id)
        self.assertFalse(self.letter_doc.pb_rf_private)

    # ================================================================ M4
    def test_m4_report_titles_never_name_the_platform(self):
        """S5-F 5b x Step 9: the report preview / PDF page title is the report's
        own name for a finished review, a conduct letter and a payslip."""
        import re
        vendor = re.compile('od' + 'oo', re.I)
        Report = self.env['ir.actions.report']
        if not hasattr(Report, '_biz_report_title'):
            self.skipTest('needs biz_debrand 19.0.2.11.0')

        def title(report, ids):
            html, _kind = Report._render_qweb_html(report, ids)
            if isinstance(html, bytes):
                html = html.decode('utf-8')
            found = re.search(r'<title>(.*?)</title>', html, re.S)
            return found.group(1).strip() if found else None

        _sheet, _review, entry = self._finished_review()
        rf = title('pb_review_forms.action_report_review_form', entry.ids)
        letter_report = Report.search([('model', '=', 'pb.conduct.letter')], limit=1)
        self.assertTrue(letter_report, 'the conduct letter report')
        lt = title(letter_report.report_name, self.letter.ids)
        found = {'review': rf, 'conduct letter': lt}
        slip_report = Report.search([('model', '=', 'hr.payslip'),
                                     ('print_report_name', '!=', False)], limit=1)
        slip = self.env['hr.payslip'].search([], limit=1)
        if slip_report and slip:
            found['payslip'] = title(slip_report.report_name, slip.ids)
            self.assertEqual(found['payslip'],
                             Report._biz_report_title(slip_report, slip.ids))
        for what, text in found.items():
            self.assertTrue(text, what)
            self.assertFalse(vendor.search(text), '%s: %s' % (what, text))
            self.assertNotEqual(text, 'Report', what + ' fell back to the neutral word')

    # ================================================================ M5
    def test_m5_late_minutes_page_beside_the_step9_tiles(self):
        """S5-F TP3 x Step 9: the late-minutes door on My Overtime and the
        Step 9 home entries live side by side; every old overtime key kept."""
        if 'pb.ess.workforce' not in self.env or not hasattr(
                self.env['pb.ess.workforce'], 'get_my_late_minutes'):
            self.skipTest('needs pb_time_pay 19.0.1.1.0')
        W = self.env['pb.ess.workforce'].with_user(self.staff_user)
        data = W.get_my_overtime()
        self.assertIn('late', data)
        W.get_my_late_minutes()
        self._form()
        self._review()
        home = self.env['pb.me.home'].with_user(self.staff_user).get_home_data(self.staff)
        urls = {t['url'] for t in home['tiles']}
        self.assertTrue({'/my/review', '/my/letters', '/my/voice', '/my/work/overtime'} <= urls,
                        urls)
        keys = {r['key'] for r in home['needs_you']}
        self.assertTrue({'review_self', 'voice_survey', 'hr_letters'} <= keys, keys)
