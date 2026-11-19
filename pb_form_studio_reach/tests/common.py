# -*- coding: utf-8 -*-
"""Fixtures for the FS-5 tests.

The employee and contract HOSTS are registered by FS-2 / FS-3 on their own
branches. Here they are registered IN TEST CODE ONLY, by patching
`pb.form.studio._pbfs_hosts` for the class (merge check: once the real hosts
are merged these tests must still pass with the patch removed or kept).
The test hosts read Country of Work from the employee's `country_id` (a
res.country) — FS-2 decides the real path (FIELD_AUDIT_FACTS §6).

People are DEMO-named; passwords are made per run (never a fixed string).
"""
import secrets
from unittest.mock import patch

from odoo.tests import TransactionCase, new_test_user

from odoo.addons.pb_form_studio.models.form_studio import PbFormStudio

PASSWORD = secrets.token_urlsafe(16)

_ORIG_HOSTS = PbFormStudio._pbfs_hosts


def _section(sid, title, kind='open'):
    return {'id': sid, 'title': title, 'icon': 'sparkles', 'tone': 'brand', 'kind': kind}


def test_hosts(self):
    hosts = dict(_ORIG_HOSTS(self))
    hosts['pbfr_employee'] = {
        'model': 'hr.employee', 'title': 'Employee', 'icon': 'user',
        'sections': [_section('custom', 'Company details'), _section('extra', 'More about you')],
        'default_layout': {'custom': [], 'extra': []}, 'std_fields': [],
        'custom_section': 'custom', 'country_field': 'country_id',
        'country_view_field': 'country_id', 'copy_custom': False, 'native_views': [],
        'portal': True, 'standard_fields': [],
    }
    hosts['pbfr_contract'] = {
        'model': 'hr.contract', 'title': 'Contract', 'icon': 'fileText',
        'sections': [_section('custom', 'Company details')],
        'default_layout': {'custom': []}, 'std_fields': [], 'custom_section': 'custom',
        'country_field': 'employee_id.country_id', 'country_view_field': False,
        'copy_custom': True, 'native_views': [], 'portal': False, 'standard_fields': [],
    }
    return hosts


class ReachCase(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        Studio = type(cls.env['pb.form.studio'])
        cls.startClassPatcher(patch.object(Studio, '_pbfs_hosts', test_hosts))
        # Pay runs of OTHER local databases share table oids (FS5-1): never
        # let them refuse a field here. The busy rail is FS-1's test 8.
        cls.startClassPatcher(patch.object(Studio, '_pbfs_busy', lambda s: ''))
        cls.company = cls.env.company
        cls.vn = cls.env.ref('base.vn')
        cls.india = cls.env.ref('base.in')
        cls.admin = new_test_user(cls.env, 'pbfr_admin', name='DEMO Reach Admin',
                                  groups='base.group_user,base.group_system,hr.group_hr_user,'
                                         'om_hr_payroll.group_hr_payroll_user,'
                                         'pb_hr_payroll_formula.group_formula_user',
                                  password=PASSWORD)
        cls.hr = new_test_user(cls.env, 'pbfr_hr', name='DEMO Reach HR',
                               groups='base.group_user,hr.group_hr_user,'
                                      'om_hr_payroll.group_hr_payroll_user,'
                                      'pb_hr_payroll_formula.group_formula_user',
                               password=PASSWORD)
        cls.payonly = new_test_user(cls.env, 'pbfr_pay', name='DEMO Reach Pay team',
                                    groups='base.group_user,'
                                           'pb_hr_payroll_base.group_payroll_base_officer,'
                                           'pb_hr_payroll_formula.group_formula_user',
                                    password=PASSWORD)
        cls.portal = new_test_user(cls.env, 'pbfr_me', name='DEMO Reach Lan',
                                   groups='base.group_portal', password=PASSWORD)
        cls.portal2 = new_test_user(cls.env, 'pbfr_me2', name='DEMO Reach Arjun',
                                    groups='base.group_portal', password=PASSWORD)
        Emp = cls.env['hr.employee']
        cls.emp_vn = Emp.create({'name': 'DEMO Reach Lan', 'company_id': cls.company.id,
                                 'country_id': cls.vn.id, 'user_id': cls.portal.id})
        cls.emp_in = Emp.create({'name': 'DEMO Reach Arjun', 'company_id': cls.company.id,
                                 'country_id': cls.india.id, 'user_id': cls.portal2.id})
        Con = cls.env['hr.contract'].sudo()
        cls.con_vn = Con.create({'name': 'DEMO Reach contract Lan', 'employee_id': cls.emp_vn.id,
                                 'company_id': cls.company.id, 'wage': 12_000_000.0,
                                 'state': 'open', 'date_start': '2026-01-01'})
        cls.con_in = Con.create({'name': 'DEMO Reach contract Arjun', 'employee_id': cls.emp_in.id,
                                 'company_id': cls.company.id, 'wage': 90_000.0,
                                 'state': 'open', 'date_start': '2026-01-01'})
        S = cls.env['pb.form.studio'].with_user(cls.admin)

        def make(host, kind, label, **kw):
            vals = dict({'type': kind, 'label': label, 'vis': 'hr'}, **kw)
            return S.create_field(host, vals)['name']
        cls.f_num = make('pbfr_employee', 'integer', 'DEMO Shoe size', formula_ok=True)
        cls.f_unmarked = make('pbfr_employee', 'integer', 'DEMO Locker number')
        cls.f_admin = make('pbfr_employee', 'number', 'DEMO Secret score', vis='admin',
                           formula_ok=True)
        cls.f_all = make('pbfr_employee', 'text', 'DEMO T-shirt size', vis='all')
        cls.f_in = make('pbfr_employee', 'integer', 'DEMO Bus pass zone', vis='all',
                        formula_ok=True, country_ids=[cls.india.id])
        cls.f_sel = make('pbfr_employee', 'select', 'DEMO Shift', vis='all', formula_ok=True,
                         options=['Early', 'Late'])
        cls.f_bool = make('pbfr_employee', 'bool', 'DEMO Drives a forklift', formula_ok=True)
        cls.f_date = make('pbfr_employee', 'date', 'DEMO Safety course on', formula_ok=True)
        cls.f_file = make('pbfr_employee', 'file', 'DEMO Safety card')
        cls.c_num = make('pbfr_contract', 'integer', 'DEMO Site days', formula_ok=True)
        cls.c_admin = make('pbfr_contract', 'text', 'DEMO Board note', vis='admin')
        cls.emp_vn.write({cls.f_num: 42, cls.f_all: 'M', cls.f_sel: 'opt_2',
                          cls.f_bool: True, cls.f_date: '2026-03-05', cls.f_admin: 7.5})
        cls.emp_in.write({cls.f_num: 44, cls.f_in: 3})
        cls.con_vn.write({cls.c_num: 9, cls.c_admin: 'secret board words'})

    @classmethod
    def scheme(cls, code, rules=(), app_data=False):
        cfg = cls.env['hr.formula.config'].sudo().create({
            'name': 'DEMO Reach %s' % code, 'code': code, 'cycle_type': 'end_cycle',
            'country_code': 'VN', 'state': 'active', 'company_id': cls.company.id})
        category = cls.env['hr.salary.rule.category'].search([], limit=1)
        Rule = cls.env['hr.formula.rule'].sudo()
        base = {'config_id': cfg.id, 'default_value': 0.0, 'appears_on_payslip': True,
                'category_id': category.id}
        Rule.create(dict(base, name='Basic', code='BASIC', column_type='input',
                         sequence=1, value_kind='money', net_role='earning'))
        for seq, (code_, key, kind) in enumerate(rules, start=2):
            Rule.create(dict(base, name='DEMO %s' % code_, code=code_, column_type='input',
                             sequence=seq, value_kind=kind, net_role='info',
                             appears_on_payslip=False, application_source_key=key))
        Rule.create(dict(base, name='Net', code=code + 'NET', column_type='formula',
                         sequence=50, value_kind='money', net_role='net',
                         excel_formula='=BASIC'))
        if app_data:
            cfg.write({'application_data_enabled': True,
                       'application_effective_from': '2026-01-01'})
        return cfg
