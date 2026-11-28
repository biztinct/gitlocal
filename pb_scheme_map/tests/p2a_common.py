# -*- coding: utf-8 -*-
"""PSCHEME P2a — the shared world of the phase's tests (DEMO-prefixed)."""

from datetime import date

from dateutil.relativedelta import relativedelta

from odoo import fields
from odoo.tests.common import TransactionCase, new_test_user


class P2aCase(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        cls.Map = env['pb.scheme.map']
        cls.Board = env['pb.scheme.board']
        cls.Row = env['pb.person.scheme']
        cls.Assign = env['hr.formula.scheme.assignment']
        cls.Fill = env['pb.person.scheme.fill']
        vnd = env.ref('base.VND').sudo()
        if not vnd.active:
            vnd.active = True
        for code in ('SGD', 'IDR'):
            cur = env.ref('base.%s' % code).sudo()
            if not cur.active:
                cur.active = True
        cls.company = env['res.company'].create({'name': 'DEMO P2A Company',
                                                 'currency_id': vnd.id})
        env.user.company_ids = [(4, cls.company.id)]
        cls.fast(cls.company)
        Dept = env['hr.department']
        cls.top = Dept.create({'name': 'DEMO P2A Top', 'company_id': cls.company.id})
        cls.team = Dept.create({'name': 'DEMO P2A Team', 'parent_id': cls.top.id,
                                'company_id': cls.company.id})
        cls.sub = Dept.create({'name': 'DEMO P2A Sub', 'parent_id': cls.team.id,
                               'company_id': cls.company.id})
        cls.sub2 = Dept.create({'name': 'DEMO P2A Sub own', 'parent_id': cls.team.id,
                                'company_id': cls.company.id})
        cls.loose = Dept.create({'name': 'DEMO P2A Loose', 'company_id': cls.company.id})
        cls.vn_end = cls._config('DEMO P2A Vietnam monthly', 'DEMOP2AVNE', 'end_cycle', 'VN')
        cls.vn_mid = cls._config('DEMO P2A Vietnam advance', 'DEMOP2AVNM', 'mid_cycle', 'VN')
        cls.vn_reg = cls._config('DEMO P2A Vietnam regular', 'DEMOP2AVNR', 'regular', 'VN')
        cls.id_end = cls._config('DEMO P2A Indonesia monthly', 'DEMOP2AIDE', 'end_cycle', 'ID')
        cls.sg_end = cls._config('DEMO P2A Singapore monthly', 'DEMOP2ASGE', 'end_cycle', 'SG')
        today = fields.Date.context_today(cls.Row)
        cls.today = today
        cls.first = today.replace(day=1)
        cls.next_first = cls.first + relativedelta(months=1)

    # -------------------------------------------------------------- fixtures
    @classmethod
    def fast(cls, company):
        try:
            cls.env['biz.approval.seed'].sudo().set_no_approval_needed(
                company, 'schememap', reason='PSCHEME P2a suite')
        except Exception:   # noqa: BLE001
            pass

    @classmethod
    def _config(cls, name, code, cycle, country, company=None):
        return cls.env['hr.formula.config'].create({
            'name': name, 'code': code, 'cycle_type': cycle, 'country_code': country,
            'company_id': (company or cls.company).id, 'state': 'active'})

    @classmethod
    def _person(cls, name, team, country, company=None):
        company = company or cls.company
        employee = cls.env['hr.employee'].create({
            'name': name, 'company_id': company.id,
            'payroll_country': country or False})
        version = employee.current_version_id
        if team:
            if version and 'department_id' in version._fields:
                version.department_id = team.id
            else:
                employee.department_id = team.id
        return employee

    def row(self, employee, config, date_from, date_to=False, source='hand'):
        return self.Row.sudo().create({'employee_id': employee.id, 'config_id': config.id,
                                       'date_from': date_from, 'date_to': date_to,
                                       'source': source})

    def line(self, config, cycle='any', team=None, **kw):
        values = {'config_id': config.id, 'cycle_type': cycle, 'company_id': self.company.id}
        if team:
            values['department_id'] = team.id
        values.update(kw)
        return self.Assign.create(values)

    def rows_of(self, employee):
        return [(r.config_id, r.date_from, r.date_to, r.source) for r in self.Row.sudo().search(
            [('employee_id', '=', employee.id)], order='date_from, cycle_type, id')]

    def board(self, user=None):
        Board = self.Board.with_user(user) if user else self.Board
        return Board.with_context(allowed_company_ids=[self.company.id])

    def routed(self, name='DEMO P2A Routed'):
        """A company where a payroll manager approves (P1 T19's world)."""
        company = self.env['res.company'].create({'name': name,
                                                  'currency_id': self.company.currency_id.id})
        self.env['pb.schememap.proposal']._approval_seed_default(company)
        co = {'company_id': company.id, 'company_ids': [(6, 0, [company.id])]}
        suffix = str(company.id)
        hr = new_test_user(self.env, login='p2a_hr_%s' % suffix,
                           groups='base.group_user,hr.group_hr_user',
                           name='DEMO P2A HR %s' % suffix, **co)
        boss = new_test_user(self.env, login='p2a_boss_%s' % suffix,
                             name='DEMO P2A Payroll manager %s' % suffix,
                             groups='base.group_user,hr.group_hr_user,'
                                    'pb_hr_payroll_formula.group_formula_manager', **co)
        role = self.env['biz.approval.role'].sudo().search([('key', '=', 'payroll_mgr')], limit=1)
        Resp = self.env['biz.approval.responsibility'].sudo()
        held = Resp.with_context(active_test=False).search([
            ('company_id', '=', company.id), ('role_id', '=', role.id), ('scope_key', '=', '')],
            limit=1)
        if held:
            held.write({'user_id': boss.id, 'active': True, 'backup_user_id': False})
        else:
            Resp.create({'company_id': company.id, 'role_id': role.id, 'scope_key': '',
                         'scope_label': company.name, 'user_id': boss.id,
                         'date_from': date(2020, 1, 1)})
        return company, hr, boss

    def approve(self, answer, boss, company):
        request = self.env['biz.approval.request'].sudo().browse(answer['request_id'])
        step = request.step_ids.filtered(lambda s: s.status == 'active')[:1]
        self.env['biz.approval.engine'].with_user(boss).with_context(
            allowed_company_ids=[company.id]).decide(request.id, step.key, 'approve', 'ok')
        self.env.invalidate_all()
        return request
