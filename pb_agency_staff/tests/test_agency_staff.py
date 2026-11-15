# -*- coding: utf-8 -*-
"""WDGAP S8-B — agency staff (`pb_agency_staff`).

AG1  by construction: no employee, contract, login or payslip link; nothing
     in pay, time or payslips can point at one; employees unchanged.
AG2  headcount: a separate "+N agency staff" figure, never added to it.
AG3  the board: on site / starting later / ending in 30 days / ended; search
     by agency.
AG4  rights: HR only; HR officers keep them, HR managers may delete; other
     companies see nothing.
AG5  checks: end before start, a manager from another company.
AG6  papers: PDF/PNG/JPG only, added and removed.
AG7  the agency's drawer in Vendors lists them for HR only.
AG8  silent install: no job, empty board.
"""
import base64
from datetime import timedelta

from odoo import fields
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged('post_install', '-at_install', 'wdgap_s8b')
class TestAgencyStaff(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env['res.company'].create({'name': 'S8B Agency Co'})
        cls.other = cls.env['res.company'].create({'name': 'S8B Agency Other'})
        cls.env.user.company_ids = [(4, cls.company.id), (4, cls.other.id)]
        cls.env.user.company_id = cls.company
        cls.env = cls.env(context=dict(cls.env.context,
                                       allowed_company_ids=[cls.company.id],
                                       tracking_disable=True, mail_notrack=True))
        cls.W = cls.env['pb.agency.worker']
        cls.Board = cls.env['pb.agency.board']
        cls.vendor = cls.env['pb.vendor'].create({
            'name': 'S8B Staffing Partners', 'company_id': cls.company.id,
            'responsible_user_id': cls.env.user.id})
        cls.dept = cls.env['hr.department'].create(
            {'name': 'S8B Warehouse', 'company_id': cls.company.id})
        cls.boss = cls.env['hr.employee'].create(
            {'name': 'S8B Shift lead', 'company_id': cls.company.id})
        cls.today = fields.Date.context_today(cls.W)

    def _user(self, login, groups, company=None):
        company = company or self.company
        return self.env['res.users'].create({
            'name': login, 'login': login, 'company_id': company.id,
            'company_ids': [(6, 0, [company.id])],
            'group_ids': [(6, 0, [self.env.ref(g).id for g in groups])]})

    def _worker(self, **kw):
        vals = {'name': 'S8B Picker', 'vendor_id': self.vendor.id,
                'company_id': self.company.id, 'department_id': self.dept.id,
                'manager_id': self.boss.id, 'job_title': 'Picker',
                'date_start': self.today - timedelta(days=10)}
        vals.update(kw)
        return self.W.create(vals)

    # ================================================================ AG1
    def test_ag01_never_payroll_by_construction(self):
        emp_before = self.env['hr.employee'].with_context(active_test=False).search_count([])
        w = self._worker()
        self.assertEqual(
            self.env['hr.employee'].with_context(active_test=False).search_count([]),
            emp_before, "no employee is made")
        # the record's OWN fields (mail.thread brings followers and messages)
        targets = {f.comodel_name for f in self.W._fields.values()
                   if f.type in ('many2one', 'one2many', 'many2many')
                   and getattr(f, '_module', '') == 'pb_agency_staff'
                   and f.name not in ('create_uid', 'write_uid')}
        self.assertIn('pb.vendor', targets)
        for forbidden in ('hr.contract', 'hr.payslip', 'hr.payslip.run', 'res.users',
                          'hr.attendance', 'hr.version'):
            self.assertNotIn(forbidden, targets)
        self.assertNotIn('employee_id', self.W._fields)
        self.assertNotIn('user_id', self.W._fields)
        # nothing in pay, time or payslips can point at one
        for name in self.env.registry.models:
            if not name.startswith(('hr.payslip', 'hr.contract', 'hr.attendance',
                                    'hr.payroll', 'hr.formula', 'pb.payrun')):
                continue
            for field in self.env[name]._fields.values():
                self.assertNotEqual(getattr(field, 'comodel_name', None),
                                    'pb.agency.worker',
                                    '%s.%s points at agency staff' % (name, field.name))
        self.assertTrue(w.exists())

    # ================================================================ AG2
    def test_ag02_beside_the_headcount(self):
        kpis_before = self.env['pb.people']._roster_kpis()['kpis']
        self._worker()
        self._worker(name='S8B Starter', date_start=self.today + timedelta(days=5))
        kpis = self.env['pb.people']._roster_kpis()['kpis']
        self.assertEqual(kpis['headcount'], kpis_before['headcount'], "never added")
        self.assertEqual(kpis['agency_staff'], kpis_before.get('agency_staff', 0) + 1,
                         "only those on site today")

    # ================================================================ AG3
    def test_ag03_board(self):
        self._worker()
        self._worker(name='S8B Later', date_start=self.today + timedelta(days=3))
        self._worker(name='S8B Ending', date_end=self.today + timedelta(days=12))
        self._worker(name='S8B Gone', date_end=self.today - timedelta(days=1))
        board = self.Board.get_board()
        k = board['kpis']
        self.assertEqual((k['on_site'], k['upcoming'], k['ending'], k['ended']),
                         (2, 1, 1, 1))
        page = self.Board.get_page(filters={'where': ['ending']})
        self.assertEqual([r['name'] for r in page['rows']], ['S8B Ending'])
        self.assertTrue(page['rows'][0]['ending'])
        found = self.Board.get_page(search='Staffing Partners')
        self.assertEqual(found['total'], 4)

    # ================================================================ AG4
    def test_ag04_rights(self):
        w = self._worker()
        plain = self._user('s8b_ag_plain', ['base.group_user'])
        self.assertFalse(self.Board.with_user(plain).get_board()['allowed'])
        with self.assertRaises(AccessError):
            self.W.with_user(plain).search([]).read(['name'])
        officer = self._user('s8b_ag_officer', ['base.group_user', 'hr.group_hr_user'])
        ob = self.Board.with_user(officer).with_context(allowed_company_ids=[self.company.id])
        res = ob.save_worker({'name': 'S8B Added by HR', 'vendor_id': self.vendor.id})
        self.assertTrue(res['ok'])
        row = ob.get_worker(res['id'])
        self.assertEqual(row['agency'], 'S8B Staffing Partners', "agency name read for HR")
        w_row = ob.get_worker(w.id)
        self.assertEqual(w_row['job_title'], 'Picker', "walk finding: the drawer's Role box was empty")
        with self.assertRaises(AccessError):
            ob.delete_worker(res['id'])
        manager = self._user('s8b_ag_mgr', ['base.group_user', 'hr.group_hr_manager'])
        self.Board.with_user(manager).with_context(
            allowed_company_ids=[self.company.id]).delete_worker(res['id'])
        stranger = self._user('s8b_ag_other', ['base.group_user', 'hr.group_hr_user'],
                              self.other)
        self.env.flush_all()
        self.env.invalidate_all()
        self.assertFalse(self.W.with_user(stranger).with_context(
            allowed_company_ids=[self.other.id]).search([('id', '=', w.id)]))

    # ================================================================ AG5
    def test_ag05_checks(self):
        with self.assertRaises(ValidationError):
            self._worker(date_start=self.today, date_end=self.today - timedelta(days=1))
        foreign = self.env['hr.employee'].create({'name': 'S8B Elsewhere',
                                                  'company_id': self.other.id})
        with self.assertRaises(ValidationError):
            self._worker(manager_id=foreign.id)
        with self.assertRaises(UserError):
            self.Board.save_worker({'name': ''})
        w = self._worker()
        res = self.Board.end_worker(w.id)
        self.assertTrue(res['ok'])
        self.assertEqual(w.date_end, self.today)

    # ================================================================ AG6
    def test_ag06_papers(self):
        w = self._worker()
        data = base64.b64encode(b'%PDF-1.4 test').decode()
        out = self.Board.add_file(w.id, 'agreement.pdf', 'application/pdf', data)
        self.assertEqual(len(out['files']), 1)
        with self.assertRaises(UserError):
            self.Board.add_file(w.id, 'x.exe', 'application/octet-stream', data)
        out = self.Board.remove_file(w.id, out['files'][0]['id'])
        self.assertFalse(out['files'])

    # ================================================================ AG7
    def test_ag07_vendor_drawer(self):
        self._worker()
        from odoo.service.model import call_kw
        answer = call_kw(self.env['pb.vendors'], 'get_vendor', [self.vendor.id], {})
        self.assertEqual([r['name'] for r in answer['agency_staff']], ['S8B Picker'])
        vendor_user = self._user('s8b_ag_vendor', [
            'base.group_user', 'pb_vendor_access.group_vendor_manager'])
        self.vendor.responsible_user_id = vendor_user
        theirs = self.env['pb.vendors'].with_user(vendor_user).with_context(
            allowed_company_ids=[self.company.id]).get_vendor(self.vendor.id)
        self.assertNotIn('agency_staff', theirs, "not HR: not shown")

    # ================================================================ AG8
    def test_ag08_silent_install(self):
        crons = self.env['ir.cron'].sudo().search([('model_id.model', '=', 'pb.agency.worker')])
        self.assertFalse(crons)
        board = self.Board.get_board()
        self.assertTrue(board['allowed'])
        self.assertEqual(board['total'], 0)
