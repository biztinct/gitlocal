# -*- coding: utf-8 -*-
"""Fixtures shared by the S2-D tax-details tests.

People are DEMO-named; logins and passwords are made up for the test run
only (never a real person, never a real password)."""
import secrets

from odoo.tests import TransactionCase

from odoo.addons.pb_me_details.tests.common import PDF, PNG, decide, seat  # noqa: F401

# made per test run, never a fixed string (no test passwords in files)
PASSWORD = secrets.token_urlsafe(16)


class TaxCase(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.company.country_id = cls.env.ref('base.vn')
        Users = cls.env['res.users'].with_context(no_reset_password=True)
        common = {'company_id': cls.company.id,
                  'company_ids': [(6, 0, [cls.company.id])]}
        portal = cls.env.ref('base.group_portal').id

        def user(name, login, groups):
            return Users.create(dict(common, name=name, login=login,
                                     password=PASSWORD,
                                     group_ids=[(6, 0, groups)]))
        cls.portal = user('DEMO Tax Person', 's2d_tax_me', [portal])
        cls.portal2 = user('DEMO Tax Other', 's2d_tax_other', [portal])
        cls.hr = user('DEMO Tax HR', 's2d_tax_hr',
                      [cls.env.ref('hr.group_hr_user').id])
        cls.pay = user('DEMO Tax Pay team', 's2d_tax_pay',
                       [cls.env.ref('om_hr_payroll.group_hr_payroll_user').id])
        # the person a pay run is worked out as: pay team + formula reader
        cls.pay_formula = user('DEMO Tax Pay runner', 's2d_tax_payrun', [
            cls.env.ref('om_hr_payroll.group_hr_payroll_user').id,
            cls.env.ref('pb_hr_payroll_formula.group_formula_user').id])
        cls.pay_only = user('DEMO Tax Payroll no HR', 's2d_tax_payonly', [
            cls.env.ref('base.group_user').id,
            cls.env.ref('pb_hr_payroll_base.group_payroll_base_officer').id])
        cls.manager_user = user('DEMO Tax Line manager', 's2d_tax_mgr',
                                [cls.env.ref('base.group_user').id])
        seat(cls.env, cls.company, 'hr_lead', cls.hr)
        Emp = cls.env['hr.employee']
        cls.boss = Emp.create({'name': 'DEMO Tax Boss', 'company_id': cls.company.id,
                               'user_id': cls.manager_user.id})
        cls.emp = Emp.create({'name': 'DEMO Tax Person', 'company_id': cls.company.id,
                              'user_id': cls.portal.id, 'parent_id': cls.boss.id,
                              'identification_id': '3174012345678901'})
        cls.other = Emp.create({'name': 'DEMO Tax Other', 'company_id': cls.company.id,
                                'user_id': cls.portal2.id})
        cls.Req = cls.env['pb.me.detail.request']
        cls.schemes = {}
        for code in ('VN', 'ID', 'IN', 'SG', 'MY'):
            cls.schemes[code] = cls.env['hr.formula.config'].sudo().create({
                'name': 'DEMO S2D %s' % code, 'code': 'STWOD%s' % code,
                'cycle_type': 'end_cycle', 'country_code': code,
                'company_id': cls.company.id})
        cls._pay_by(cls.emp, 'VN')
        cls._pay_by(cls.other, 'VN')

    @classmethod
    def _pay_by(cls, emp, code):
        vals = {'pb_paid_by_id': cls.schemes[code].id if code else False}
        if 'pb_paid_by_stale' in emp._fields:
            vals['pb_paid_by_stale'] = False
        emp.sudo().write(vals)
        emp.invalidate_recordset()

    def _ask(self, kind, values=None, upload=None, request_id=None, emp=None,
             user=None):
        return self.Req.with_user(user or self.portal).pb_portal_create(
            emp or self.emp, kind, values or {}, upload=upload,
            request_id=request_id)

    @staticmethod
    def _pdf(name='proof.pdf', data=PDF):
        return (data, name, 'application/pdf')
