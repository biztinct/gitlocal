# -*- coding: utf-8 -*-
"""WDGAP S8-C — Organisation: levels, job page, cost centres, pause hiring,
would-rehire. Numbered as in the phase report (T1…T12)."""
import os
import re
from datetime import date, timedelta

from odoo import fields
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests import TransactionCase, tagged

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


@tagged('post_install', '-at_install', 'wdgap_s8c')
class TestOrgStructure(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        cls.co = env['res.company'].create({'name': 'S8C Test Company'})
        cls.co2 = env['res.company'].create({'name': 'S8C Other Company'})
        Users = env['res.users'].with_context(no_reset_password=True)

        def user(login, groups, companies=None):
            companies = companies or cls.co
            return Users.create({
                'name': login.split('@')[0].replace('.', ' ').title(),
                'login': login, 'email': login,
                'company_id': companies[0].id, 'company_ids': [(6, 0, companies.ids)],
                'group_ids': [(6, 0, [env.ref(g).id for g in groups])],
            })
        cls.hr_manager = user('s8c.hrm@example.com', ['base.group_user', 'hr.group_hr_manager',
                                                       'pb_lifecycle.group_lifecycle_manager'])
        cls.hr_officer = user('s8c.hro@example.com', ['base.group_user', 'hr.group_hr_user'])
        cls.lead = user('s8c.lead@example.com', ['base.group_user', 'pb_hiring.group_hiring_manager'])
        cls.plain = user('s8c.plain@example.com', ['base.group_user'])
        # an HR officer who may look at exits but not change them
        cls.life_user = user('s8c.life@example.com', ['base.group_user', 'hr.group_hr_user',
                                                      'pb_lifecycle.group_lifecycle_user'])
        Dept = env['hr.department'].sudo()
        cls.sales = Dept.create({'name': 'S8C Sales', 'company_id': cls.co.id})
        cls.sales_north = Dept.create({'name': 'S8C North', 'company_id': cls.co.id,
                                       'parent_id': cls.sales.id})
        cls.ops = Dept.create({'name': 'S8C Ops', 'company_id': cls.co.id})
        cls.job = env['hr.job'].sudo().create({'name': 'S8C Field officer', 'company_id': cls.co.id,
                                               'department_id': cls.sales_north.id})
        cls.rule = env['hr.salary.rule'].sudo().search([('category_id', '!=', False)], limit=1)
        cls.Board = env['pb.org.structure']

    # ------------------------------------------------------------ helpers
    def _person(self, name, dept=None, text=False, company=None):
        company = company or self.co
        emp = self.env['hr.employee'].sudo().create({
            'name': name, 'company_id': company.id,
            'department_id': (dept or self.sales).id})
        contract = self.env['hr.contract'].sudo().create({
            'name': 'S8C %s' % name, 'employee_id': emp.id, 'wage': 10_000_000,
            'state': 'open', 'date_start': '2026-01-01', 'company_id': company.id,
            'costcenter': text})
        return emp, contract

    def _slip(self, emp, contract, month, done):
        first = date(2026, month, 1)
        last = (first.replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(days=1)
        slip = self.env['hr.payslip'].sudo().create({
            'name': 'S8C %s %s' % (emp.name, month), 'employee_id': emp.id,
            'contract_id': contract.id, 'date_from': first, 'date_to': last,
            'company_id': contract.company_id.id})
        line = self.env['hr.payslip.line'].sudo().create({
            'slip_id': slip.id, 'salary_rule_id': self.rule.id, 'employee_id': emp.id,
            'contract_id': contract.id, 'name': 'Basic', 'code': 'S8CBASIC',
            'category_id': self.rule.category_id.id, 'amount': 1234.0, 'quantity': 1})
        if done:
            slip.write({'state': 'done'})
        return slip, line

    def _fresh(self):
        self.env.flush_all()
        self.env.invalidate_all()

    def _as(self, user):
        return self.Board.with_user(user).with_context(allowed_company_ids=user.company_ids.ids)

    # ================================================== T1 silent install
    def test_t1_silent_install(self):
        """Nothing is switched on: no level, no cost centre, no pause, a quiet
        job that has nothing to do, one lens and three palette rows."""
        self.assertFalse(self.env['hr.job'].sudo().search_count([('pb_hiring_paused', '=', True)]))
        self.assertFalse(self.env['hr.department'].sudo().search_count([('pb_hiring_paused', '=', True)]))
        self.assertFalse(self.env['pb.job.level'].sudo().search_count([]))
        self.assertFalse(self.env['pb.cost.centre'].sudo().search_count([]))
        self.assertFalse(self.env['hr.contract'].sudo().search_count([('pb_cost_centre_id', '!=', False)]))
        cron = self.env.ref('pb_org_structure.cron_pb_cost_centre_moves')
        self.assertTrue(cron.active)
        self.assertEqual(self.env['pb.cost.centre.move']._cron_apply_due(), 0)
        head = self._as(self.hr_manager).get_head()
        self.assertTrue(head['allowed'])
        self.assertEqual(head['kpis']['cost_centres'], 0)
        self.assertEqual(head['kpis']['paused_roles'], 0)
        palette = open(os.path.join(HERE, 'static/src/js/org_palette.js')).read()
        self.assertEqual(palette.count('registry.category(PEOPLE_LENSES).add('), 1)
        self.assertEqual(len(re.findall(r'sequence: 45[0-6]\d', palette)), 3)
        self.assertIn('sequence: 58', palette)

    def test_t1b_no_product_vendor_name_on_screen(self):
        """No "Odoo" in any string a user can see (templates, JS, Python
        messages, field labels)."""
        for root, _dirs, files in os.walk(HERE):
            if '/tests' in root or '/i18n' in root:
                continue
            for name in files:
                if not name.endswith(('.xml', '.js', '.py', '.scss')):
                    continue
                text = open(os.path.join(root, name)).read()
                if name.endswith('.py'):
                    strings = re.findall(r"_\(\s*['\"](.+?)['\"]", text) + \
                        re.findall(r"string=['\"](.+?)['\"]", text) + \
                        re.findall(r"help=['\"](.+?)['\"]", text)
                    for s in strings:
                        self.assertNotIn('odoo', s.lower(), '%s: %s' % (name, s))
                elif name.endswith('.xml') and '/static/' in root:
                    visible = re.sub(r'<!--.*?-->', '', text, flags=re.S)
                    visible = re.sub(r'<[^>]+>', ' ', visible)
                    self.assertNotIn('odoo', visible.lower(), name)
                elif name.endswith('.js'):
                    for s in re.findall(r'_t\(\s*"(.+?)"', text):
                        self.assertNotIn('odoo', s.lower(), '%s: %s' % (name, s))

    # ======================================================== T2 levels
    def test_t2_levels_and_job_page(self):
        board = self._as(self.hr_manager)
        rows = board.save_level({'name': 'S8C Associate'})
        rows = board.save_level({'name': 'S8C Senior', 'description': 'Works alone'})
        mine = [r for r in rows if r['name'].startswith('S8C')]
        self.assertEqual([r['name'] for r in mine], ['S8C Associate', 'S8C Senior'])
        senior = next(r for r in mine if r['name'] == 'S8C Senior')
        rows = board.move_level(senior['id'], -1)
        order = [r['name'] for r in rows if r['name'].startswith('S8C')]
        self.assertEqual(order, ['S8C Senior', 'S8C Associate'])
        with self.assertRaises(ValidationError):
            board.save_level({'name': 's8c senior'})
        page = board.save_job(self.job.id, {'level_id': senior['id'],
                                            'description': 'Visits farms.\n\nWrites reports.'})
        self.assertEqual(page['level'], 'S8C Senior')
        self.assertIn('<p>Visits farms.</p>', str(self.job.description))
        self.assertIn('Writes reports.', page['description'])
        with self.assertRaises(UserError):
            board.archive_level(senior['id'])          # a job is at this level
        # HR officers read, never change
        officer = self._as(self.hr_officer)
        self.assertTrue(officer.get_job(self.job.id)['level'])
        with self.assertRaises(AccessError):
            officer.save_job(self.job.id, {'level_id': False})
        with self.assertRaises(AccessError):
            officer.save_level({'name': 'S8C Nope'})
        # somebody outside HR sees nothing
        self.assertFalse(self._as(self.plain).get_head()['allowed'])
        with self.assertRaises(AccessError):
            self._as(self.plain).get_job(self.job.id)
        page = self._as(self.hr_manager).get_job_page(filters={'level': [False]}, search='S8C')
        self.assertNotIn(self.job.id, [r['id'] for r in page['rows']])

    # ================================================ T3 the list in step
    def test_t3_list_kept_in_step_with_the_text(self):
        _e1, c1 = self._person('S8C Ana', text='cc-100')
        _e2, c2 = self._person('S8C Binh', text=' Head  Office ')
        _e3, c3 = self._person('S8C Chi', text='CC-999')
        board = self._as(self.hr_manager)
        unlisted = {u['text'] for u in board.get_cost_centres()['unlisted']}
        self.assertTrue({'cc-100', 'Head  Office', 'CC-999'} <= unlisted)
        stamp = {c.id: c.write_date for c in (c1 | c2 | c3)}
        board.save_cost_centre({'code': 'CC-100', 'name': 'Head office', 'company_id': self.co.id})
        self._fresh()
        cc = self.env['pb.cost.centre'].sudo().search([('code', '=', 'CC-100'), ('company_id', '=', self.co.id)])
        self.assertEqual(c1.pb_cost_centre_id, cc)                 # code, any case
        self.assertEqual(c2.pb_cost_centre_id, cc)                 # name, spaces ignored
        self.assertFalse(c3.pb_cost_centre_id)
        self.assertEqual(c1.costcenter, 'cc-100')                  # the text is never rewritten
        # making the list from the contracts writes no contract
        res = board.make_list_from_contracts()
        self.assertGreaterEqual(res['made'], 1)
        self._fresh()
        self.assertTrue(c3.pb_cost_centre_id)
        for c in (c1 | c2 | c3):
            self.assertEqual(c.write_date, stamp[c.id])
        # typing the text anywhere keeps the link in step
        c3.sudo().write({'costcenter': 'CC-100'})
        self.assertEqual(c3.pb_cost_centre_id, cc)
        # the code of a cost centre in use cannot be changed
        with self.assertRaises(UserError):
            board.save_cost_centre({'id': cc.id, 'code': 'CC-101', 'name': 'Head office'})
        with self.assertRaises(UserError):
            cc.sudo().unlink()
        with self.assertRaises(ValidationError):
            board.save_cost_centre({'code': 'cc-100', 'name': 'Again', 'company_id': self.co.id})

    # ================================================= T4 never history
    def test_t4_history_is_never_rewritten(self):
        emp, contract = self._person('S8C Dung', text='OLD')
        _s_done, l_done = self._slip(emp, contract, 9, done=True)
        _s_old_draft, l_old_draft = self._slip(emp, contract, 1, done=False)
        s_draft, l_draft = self._slip(emp, contract, 12, done=False)
        s_draft.write({'date_from': fields.Date.today().replace(day=1),
                       'date_to': fields.Date.today() + timedelta(days=40)})
        self._fresh()
        self.assertEqual(l_done.costcenter, 'OLD')
        # 1) a direct write of the text (any screen, the connected system)
        contract.sudo().write({'costcenter': 'NEW'})
        self._fresh()
        self.assertEqual(l_done.costcenter, 'OLD', 'a finished payslip kept its cost centre')
        self.assertEqual(l_old_draft.costcenter, 'OLD', 'a past month kept its cost centre')
        self.assertEqual(l_draft.costcenter, 'NEW', 'a draft for now follows the contract')
        # 2) a move dated today, through the screen
        cc = self.env['pb.cost.centre'].sudo().create({'code': 'CC-7', 'name': 'Seven',
                                                       'company_id': self.co.id})
        board = self._as(self.hr_manager)
        preview = board.preview_move(cc.id, str(fields.Date.today()), employee_ids=[emp.id])
        self.assertEqual(preview['moving'], 1)
        res = board.move_people(cc.id, str(fields.Date.today()), employee_ids=[emp.id], note='Site')
        self.assertEqual(res['moved'], 1)
        self._fresh()
        self.assertEqual(contract.costcenter, 'CC-7')
        self.assertEqual(l_done.costcenter, 'OLD')
        self.assertEqual(l_draft.costcenter, 'CC-7')
        # 3) amounts never move
        self.assertEqual(l_done.total, 1234.0)
        self.assertEqual(contract.wage, 10_000_000)
        # 4) a past date is refused
        with self.assertRaises(UserError):
            board.move_people(cc.id, str(fields.Date.today() - timedelta(days=1)),
                              employee_ids=[emp.id])

    def test_t4b_a_later_date_waits_for_its_day(self):
        emp, contract = self._person('S8C Em', text='OLD', dept=self.ops)
        cc = self.env['pb.cost.centre'].sudo().create({'code': 'CC-8', 'name': 'Eight',
                                                       'company_id': self.co.id})
        board = self._as(self.hr_manager)
        later = fields.Date.today() + timedelta(days=10)
        res = board.move_people(cc.id, str(later), department_id=self.ops.id)
        self.assertEqual(res['waiting'], 1)
        move = self.env['pb.cost.centre.move'].sudo().search([('contract_id', '=', contract.id)])
        self.assertEqual(move.state, 'scheduled')
        self.assertEqual(self.env['pb.cost.centre.move']._cron_apply_due(), 0)
        self.assertEqual(contract.costcenter, 'OLD')
        # a newer change replaces the waiting one
        cc9 = self.env['pb.cost.centre'].sudo().create({'code': 'CC-9', 'name': 'Nine',
                                                        'company_id': self.co.id})
        board.move_people(cc9.id, str(later), employee_ids=[emp.id])
        self.assertEqual(move.state, 'cancelled')
        newer = self.env['pb.cost.centre.move'].sudo().search(
            [('contract_id', '=', contract.id), ('state', '=', 'scheduled')])
        self.assertEqual(len(newer), 1)
        # the day comes
        self.env.cr.execute("UPDATE pb_cost_centre_move SET date_start = %s WHERE id = %s",
                            (fields.Date.today(), newer.id))
        self.env.invalidate_all()
        self.assertEqual(self.env['pb.cost.centre.move']._cron_apply_due(), 1)
        self.assertEqual(contract.costcenter, 'CC-9')
        self.assertEqual(newer.state, 'done')
        self.assertEqual(newer.old_text, 'OLD')
        # twice is harmless
        self.assertEqual(self.env['pb.cost.centre.move']._cron_apply_due(), 0)

    # =========================================== T5 the team's usual one
    def test_t5_team_default_on_new_contracts_only(self):
        _e0, before = self._person('S8C Old timer', dept=self.ops)
        cc = self.env['pb.cost.centre'].sudo().create({'code': 'OPS-1', 'name': 'Ops',
                                                       'company_id': self.co.id})
        self._as(self.hr_manager).set_team_cost_centre(self.ops.id, cc.id)
        self.assertFalse(before.costcenter, 'nobody already there changes')
        _e1, new = self._person('S8C Newcomer', dept=self.ops)
        self.assertEqual(new.costcenter, 'OPS-1')
        _e2, typed = self._person('S8C Typed', dept=self.ops, text='MINE')
        self.assertEqual(typed.costcenter, 'MINE', 'a typed cost centre wins')

    # ============================================ T6 multi-company
    def test_t6_other_company_stays_apart(self):
        other_cc = self.env['pb.cost.centre'].sudo().create(
            {'code': 'X-1', 'name': 'Other', 'company_id': self.co2.id})
        emp, _c = self._person('S8C Fay', text='X-1')
        self.assertFalse(_c.pb_cost_centre_id, 'a code of another company never links')
        board = self._as(self.hr_manager)
        codes = [r['code'] for r in board.get_cost_centres()['rows']]
        self.assertNotIn('X-1', codes)
        with self.assertRaises(UserError):
            board.move_people(other_cc.id, str(fields.Date.today()), employee_ids=[emp.id])

    # ================================================ T7 pause hiring
    def _request(self, dept, title='S8C Picker', user=None):
        Req = self.env['pb.hiring.requisition'].with_user(user or self.lead).with_context(
            allowed_company_ids=[self.co.id])
        return Req.create({'title': title, 'department_id': dept.id,
                           'company_id': self.co.id, 'headcount': 1})

    def test_t7_pause_a_team_stops_new_hiring(self):
        req_before = self._request(self.sales_north, 'S8C Before')
        board = self._as(self.lead)
        with self.assertRaises(UserError):
            board.set_pause('team', self.sales.id, True, '')     # a reason is needed
        board.set_pause('team', self.sales.id, True, 'Budget review until March')
        self.assertTrue(self.sales.pb_hiring_paused)
        self.assertTrue(self.sales_north.pb_hiring_paused, 'the teams under it too')
        self.assertFalse(self.ops.pb_hiring_paused)
        self.assertTrue(self.job.pb_hiring_paused)               # C-2
        self.assertIn('Budget review until March', self.job.pb_hiring_pause_sentence())
        # new request: refused, with the reason
        with self.assertRaisesRegex(UserError, 'Budget review until March'):
            self._request(self.sales_north)
        self._request(self.ops, 'S8C Ops role')                  # other teams carry on
        # the request made before: not sent in, not opened, not advertised
        with self.assertRaisesRegex(UserError, 'paused'):
            req_before._request_send_in()
        with self.assertRaisesRegex(UserError, 'paused'):
            req_before.sudo()._open_for_candidates()
        with self.assertRaisesRegex(UserError, 'paused'):
            self.env['pb.hiring.posting'].sudo().publish_for(req_before.id)
        # what carries on: the offer rule is unchanged, the board warns
        self.assertNotIn('paused', req_before.sudo()._offer_block_reason())
        row = self.env['pb.hiring'].sudo()._row(req_before.sudo())
        self.assertTrue(row['pb_paused'])
        self.assertIn('Budget review', row['pb_paused_reason'])
        # restart: everything back, nothing was rewritten
        board.set_pause('team', self.sales.id, False)
        self.assertFalse(self.job.pb_hiring_paused)
        self.assertFalse(self.sales_north.pb_hiring_paused)
        self._request(self.sales_north, 'S8C After')
        self.assertEqual(req_before.state, 'setup')

    def test_t7b_company_and_role_pause_and_rights(self):
        with self.assertRaises(AccessError):
            self._as(self.hr_officer).set_pause('company', self.co.id, True, 'No')
        with self.assertRaises(AccessError):
            self._as(self.plain).set_pause('role', self.job.id, True, 'No')
        board = self._as(self.hr_manager)
        board.set_pause('role', self.job.id, True, 'Role under review')
        self.assertTrue(self.job.pb_hiring_paused)
        self.assertFalse(self.sales_north.pb_hiring_paused, 'one role, not the team')
        with self.assertRaisesRegex(UserError, 'this role'):
            self.env['pb.hiring.requisition'].with_user(self.lead).with_context(
                allowed_company_ids=[self.co.id]).create({
                    'title': 'S8C Field officer', 'department_id': self.sales_north.id,
                    'company_id': self.co.id, 'job_id': self.job.id})
        board.set_pause('role', self.job.id, False)
        board.set_pause('company', self.co.id, True, 'Year-end freeze')
        self.assertTrue(self.ops.pb_hiring_paused)
        with self.assertRaisesRegex(UserError, 'Year-end freeze'):
            self._request(self.ops)
        pauses = board.get_pauses()
        self.assertTrue(next(c for c in pauses['companies'] if c['id'] == self.co.id)['paused'])
        self.assertTrue(next(t for t in pauses['teams'] if t['id'] == self.ops.id)['inherited'])
        board.set_pause('company', self.co.id, False)
        self.assertFalse(self.ops.pb_hiring_paused)

    def test_t7c_careers_page_and_org_chart(self):
        website = self.env['website'].sudo().search([], limit=1)
        if not website:
            self.skipTest('no website on this database')
        job = self.env['hr.job'].sudo().create({
            'name': 'S8C Careers role', 'company_id': website.company_id.id,
            'department_id': False, 'is_published': True})
        self.assertTrue(job.pb_hiring_accepts_applications(website))
        detail = job._search_get_detail(website, 'name', {'displayDescription': False})
        self.assertIn([('pb_hiring_paused', '=', False)], detail['base_domain'])
        job.sudo().write({'pb_hiring_pause_self': True, 'pb_hiring_pause_reason_self': 'x'})
        self.assertFalse(job.pb_hiring_accepts_applications(website))
        job.sudo().write({'pb_hiring_pause_self': False})
        self.assertTrue(job.pb_hiring_accepts_applications(website))
        # org chart: no new open role in a paused team
        mgr = self.env['hr.employee'].sudo().create({'name': 'S8C Manager', 'company_id': self.co.id,
                                                     'department_id': self.sales.id})
        self._as(self.lead).set_pause('team', self.sales.id, True, 'Hold')
        res = self.env['pb.orgchart'].add_open_role(mgr.id, 'S8C New role')
        self.assertIn('error', res)
        self.assertIn('Hold', res['error'])
        self.assertFalse(self.env['hr.job'].sudo().search([('name', '=', 'S8C New role')]))

    # =================================================== T8 would rehire
    def test_t8_rehire_mark_is_hr_only(self):
        emp_user = self.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'S8C Leaver', 'login': 's8c.leaver@example.com', 'email': 'gone@example.com',
            'company_id': self.co.id, 'company_ids': [(6, 0, [self.co.id])],
            'group_ids': [(6, 0, [self.env.ref('base.group_user').id])]})
        leaver = self.env['hr.employee'].sudo().create({
            'name': 'S8C Leaver', 'company_id': self.co.id, 'user_id': emp_user.id,
            'work_email': 'gone@example.com'})
        case = self.env['pb.journey.case'].sudo().create({
            'employee_id': leaver.id, 'case_type': 'offboarding', 'company_id': self.co.id})
        Exits = self.env['pb.exits']
        hr = Exits.with_user(self.hr_manager).with_context(allowed_company_ids=[self.co.id])
        detail = hr.get_exit(case.id)
        self.assertIn('pb_rehire', detail)
        self.assertEqual(detail['pb_rehire']['value'], '')
        res = hr.set_rehire(case.id, 'yes', 'Great with customers')
        self.assertEqual(res['value'], 'yes')
        self.assertEqual(leaver.sudo().pb_rehire, 'yes')
        # a lifecycle reader who may not change exits never sees it
        reader = Exits.with_user(self.life_user).with_context(allowed_company_ids=[self.co.id])
        self.assertNotIn('pb_rehire', reader.get_exit(case.id))
        with self.assertRaises(AccessError):
            reader.set_rehire(case.id, 'no')
        # the person themselves cannot read the field (PRC-W1)
        self._fresh()
        with self.assertRaises(AccessError):
            leaver.with_user(emp_user).read(['pb_rehire'])
        # they leave; they apply again: HR sees a quiet chip, nobody else
        leaver.sudo().write({'active': False})
        applicant = self.env['hr.applicant'].sudo().create({
            'partner_name': 'S8C Leaver again', 'email_from': 'GONE@example.com',
            'job_id': self.job.id, 'company_id': self.co.id})
        Hiring = self.env['pb.hiring']
        req = self._request(self.ops, 'S8C Chip role').sudo()
        now, today = fields.Datetime.now(), fields.Date.today()
        card = Hiring.with_user(self.hr_manager).with_context(allowed_company_ids=[self.co.id])._card(
            applicant, [], 0, req, now, today, True)
        self.assertIn('would rehire: Yes', card.get('pb_former_employee', ''))
        self.assertTrue(any('Worked here' in c['label'] for c in card['chips']))
        card2 = Hiring.with_user(self.lead).with_context(allowed_company_ids=[self.co.id])._card(
            applicant, [], 0, req, now, today, True)
        self.assertNotIn('pb_former_employee', card2)
