# Part of Payobook. See LICENSE file for full copyright and licensing details.
"""H-series: the pages as a real Employee (portal) login over HTTP."""
from odoo.tests import HttpCase, new_test_user, tagged


@tagged('post_install', '-at_install', 'pb_voice')
class TestVoiceHttp(HttpCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        cls.company = env['res.company'].create({'name': 'DEMO Voice Web'})
        co = cls.company.id
        cls.hr = new_test_user(env, login='s9c_whr',
                               company_id=co, company_ids=[(6, 0, [co])],
                               groups='base.group_user,hr.group_hr_user')
        cls.dept = env['hr.department'].create({'name': 'DEMO Web', 'company_id': co})
        cls.mgr_user = new_test_user(env, login='s9c_wmgr',
                                     company_id=co, company_ids=[(6, 0, [co])],
                                     groups='base.group_user')
        cls.mgr = env['hr.employee'].create({'name': 'DEMO Web Manager',
                                             'company_id': co,
                                             'department_id': cls.dept.id,
                                             'user_id': cls.mgr_user.id})
        cls.people = []
        for i in range(6):
            u = new_test_user(env, login='s9c_w%d' % i,
                              company_id=co, company_ids=[(6, 0, [co])],
                              groups='base.group_portal')
            e = env['hr.employee'].create({'name': 'DEMO Web %d' % i, 'company_id': co,
                                           'department_id': cls.dept.id,
                                           'parent_id': cls.mgr.id, 'user_id': u.id})
            cls.people.append((u, e))
        # five more people with no department, so the manager is not alone
        for i in range(5):
            env['hr.employee'].create({'name': 'DEMO Web General %d' % i,
                                       'company_id': co})
        Round = env['pb.voice.round'].with_user(cls.hr).with_context(
            allowed_company_ids=[co])
        cls.rnd = Round.create({'name': 'DEMO web pulse', 'company_id': co,
                                'company_ids': [(6, 0, [co])]})
        Q = env['pb.voice.question'].with_user(cls.hr).with_context(allowed_company_ids=[co])
        cls.q1 = Q.create({'round_id': cls.rnd.id, 'kind': 'scale', 'text': 'DEMO Q one'})
        cls.q2 = Q.create({'round_id': cls.rnd.id, 'kind': 'text', 'text': 'DEMO Q two'})
        cls.rnd.action_open()

    @classmethod
    def tearDownClass(cls):
        cls.env['pb.voice.box']._voice_destroy(cls.rnd.id)
        super().tearDownClass()

    def test_H01_portal_answers_once_over_http(self):
        user, emp = self.people[0]
        self.authenticate(user.login, user.login)
        page = self.url_open('/my/voice/%s' % self.rnd.id)
        self.assertEqual(page.status_code, 200)
        self.assertIn('Your answers are anonymous', page.text)
        self.assertIn('DEMO Q one', page.text)
        form = page.text[page.text.find('pbv-promise'):page.text.find('</form>')]
        self.assertTrue(form)
        self.assertNotIn('Odoo', form)
        home = self.url_open('/my/voice')
        self.assertEqual(home.status_code, 200)
        self.assertIn('Waiting for your answers', home.text)
        resp = self.url_open('/my/voice/%s/answer' % self.rnd.id, data={
            'q_%s' % self.q1.id: '4', 't_%s' % self.q2.id: 'over http',
            'csrf_token': self._csrf(page.text)}, allow_redirects=False)
        self.assertIn(resp.status_code, (302, 303))
        self.assertIn('/my/voice?done=thanks', resp.headers.get('Location', ''))
        again = self.url_open('/my/voice/%s' % self.rnd.id)
        self.assertIn('You have answered this survey', again.text)
        # a second POST is refused (the form re-renders with the reason)
        resp2 = self.url_open('/my/voice/%s/answer' % self.rnd.id, data={
            'q_%s' % self.q1.id: '1', 'csrf_token': self._csrf(page.text)})
        self.assertIn('You have answered this survey', resp2.text)
        self.assertEqual(len(self.env['pb.voice.box']._seal_paths(self.rnd.id)), 1)

    def _csrf(self, html):
        mark = 'name="csrf_token" value="'
        i = html.find(mark)
        return html[i + len(mark): html.find('"', i + len(mark))] if i >= 0 else ''

    def test_H02_someone_not_asked_gets_a_plain_refusal(self):
        u = new_test_user(self.env, login='s9c_wout',
                          company_id=self.company.id, groups='base.group_portal')
        self.env['hr.employee'].create({'name': 'DEMO Web Out',
                                        'company_id': self.company.id,
                                        'user_id': u.id})
        self.authenticate(u.login, u.login)
        page = self.url_open('/my/voice/%s' % self.rnd.id)
        self.assertEqual(page.status_code, 200)
        self.assertIn('You are not asked in this survey', page.text)
        self.assertNotIn('DEMO Q one', page.text)

    def test_H03_export_route(self):
        user, _emp = self.people[1]
        self.authenticate(user.login, user.login)
        r = self.url_open('/pb_voice/results/%s.xlsx' % self.rnd.id)
        self.assertEqual(r.status_code, 404)
        self.authenticate('s9c_whr', 's9c_whr')
        r = self.url_open('/pb_voice/results/%s.xlsx' % self.rnd.id)
        self.assertEqual(r.status_code, 200)
        self.assertIn('spreadsheetml', r.headers.get('Content-Type', ''))

    def test_H04_team_page_card(self):
        """After close the manager's /my/team shows the Team voice card."""
        for i, (u, e) in enumerate(self.people[1:], start=1):
            self.rnd.with_user(u).with_context(
                allowed_company_ids=[self.company.id]).voice_submit(
                e, {str(self.q1.id): 5}, {})
        self.rnd.sudo()._voice_seal()
        self.authenticate('s9c_wmgr', 's9c_wmgr')
        page = self.url_open('/my/team')
        self.assertEqual(page.status_code, 200)
        self.assertIn('Team voice', page.text)
        self.assertIn('Your team', page.text)
        self.assertNotIn('over http', page.text)
