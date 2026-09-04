# -*- coding: utf-8 -*-
import logging
from datetime import date

from odoo import api, models

_logger = logging.getLogger(__name__)


def _opts(records, name_field='name'):
    return [{'id': r.id, 'name': getattr(r, name_field, False) or r.display_name} for r in records]


class PbPeopleRefs(models.AbstractModel):
    """Shared reference lists for the People wizards."""
    _name = 'pb.people.refs'
    _description = 'Payobook People wizard reference data'

    @api.model
    def _refs(self):
        env = self.env
        company = env.company
        structs = _opts(env['hr.payroll.structure'].search([], limit=100)) \
            if 'hr.payroll.structure' in env else []
        stypes = _opts(env['hr.payroll.structure.type'].search([], limit=100)) \
            if 'hr.payroll.structure.type' in env else []
        calendars = _opts(env['resource.calendar'].search(
            [('company_id', 'in', [company.id, False])], limit=50))
        return {
            'structures': structs,
            'structure_types': stypes,
            'calendars': calendars,
            'default_calendar': company.resource_calendar_id.id or (calendars[0]['id'] if calendars else False),
            'default_struct': structs[0]['id'] if structs else False,
            'currency': (company.currency_id.symbol or ''),
            'today': date.today().isoformat(),
        }


class PbOnboardWizard(models.AbstractModel):
    _name = 'pb.people.onboard.wizard'
    _description = 'Payobook guided employee onboarding'

    @api.model
    def get_defaults(self):
        env = self.env
        d = env['pb.people.refs']._refs()
        d.update({
            'departments': _opts(env['hr.department'].search([], limit=200)),
            'jobs': _opts(env['hr.job'].search([], limit=200)),
            'countries': _opts(env['res.country'].search([], limit=300)),
        })
        return d

    @api.model
    def create_employee(self, vals):
        Emp = self.env['hr.employee']
        evals = {'name': (vals.get('name') or '').strip()}
        if not evals['name']:
            return {'error': 'A name is required.'}
        for k_src, k_dst in [('job_id', 'job_id'), ('department_id', 'department_id'),
                             ('country_id', 'country_id')]:
            if vals.get(k_src):
                evals[k_dst] = int(vals[k_src])
        if vals.get('job_title'):
            evals['job_title'] = vals['job_title']
        if vals.get('work_email'):
            evals['work_email'] = vals['work_email']
        if vals.get('work_phone'):
            evals['work_phone'] = vals['work_phone']
        try:
            emp = Emp.create(evals)
        except Exception as e:
            return {'error': str(getattr(e, 'name', None) or e) or 'Could not create employee.'}

        # bank
        try:
            if vals.get('account_number') and 'account_number' in emp._fields:
                emp.account_number = vals['account_number']
            if vals.get('bank_name') and 'bank_name' in emp._fields:
                emp.bank_name = vals['bank_name']
        except Exception:
            pass

        # first contract
        contract_id = False
        c_err = None
        if vals.get('with_contract'):
            res = self.env['pb.people.contract.wizard'].create_contract({
                'employee_id': emp.id,
                'wage': vals.get('wage'),
                'date_start': vals.get('date_start'),
                'date_end': vals.get('date_end'),
                'struct_id': vals.get('struct_id'),
                'structure_type_id': vals.get('structure_type_id'),
                'resource_calendar_id': vals.get('resource_calendar_id'),
                'activate': vals.get('activate'),
            })
            contract_id = res.get('contract_id')
            c_err = res.get('error')

        return {'employee_id': emp.id, 'employee_name': emp.name,
                'contract_id': contract_id, 'error': c_err}


class PbContractWizard(models.AbstractModel):
    _name = 'pb.people.contract.wizard'
    _description = 'Payobook guided contract creation'

    @api.model
    def get_defaults(self, employee_id=False, renew_from=False):
        env = self.env
        d = env['pb.people.refs']._refs()
        emp = env['hr.employee'].browse(int(employee_id)) if employee_id else None
        d['employee_id'] = emp.id if emp else False
        d['employee_name'] = emp.name if emp else ''
        # prefill from an existing contract being renewed
        if renew_from:
            c = env['hr.contract'].browse(int(renew_from))
            if c.exists():
                d['prefill'] = {
                    'wage': c.wage,
                    'struct_id': c.struct_id.id if getattr(c, 'struct_id', False) else False,
                    'structure_type_id': c.structure_type_id.id if c.structure_type_id else False,
                    'resource_calendar_id': c.resource_calendar_id.id if c.resource_calendar_id else d['default_calendar'],
                }
        return d

    @api.model
    def create_contract(self, vals):
        if not vals.get('employee_id'):
            return {'error': 'No employee selected.'}
        emp = self.env['hr.employee'].browse(int(vals['employee_id']))
        cvals = {
            'employee_id': emp.id,
            'name': vals.get('name') or ('%s - %s' % (emp.name, vals.get('date_start') or date.today())),
            'wage': float(vals.get('wage') or 0.0),
            'date_start': vals.get('date_start') or str(date.today()),
        }
        if vals.get('date_end'):
            cvals['date_end'] = vals['date_end']
        if vals.get('struct_id'):
            cvals['struct_id'] = int(vals['struct_id'])
        if vals.get('structure_type_id'):
            cvals['structure_type_id'] = int(vals['structure_type_id'])
        cal = vals.get('resource_calendar_id') or self.env.company.resource_calendar_id.id
        if cal:
            cvals['resource_calendar_id'] = int(cal)
        try:
            c = self.env['hr.contract'].create(cvals)
            if vals.get('activate'):
                c.write({'state': 'open'})
        except Exception as e:
            return {'error': str(getattr(e, 'name', None) or e) or 'Could not create contract.'}
        return {'contract_id': c.id, 'name': c.name, 'employee_id': emp.id, 'error': None}
