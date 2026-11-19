"""Contract pay and the document vault, directly from the HR employee form."""
import base64

from odoo import api, fields, models, _
from odoo.exceptions import AccessError, ValidationError
from odoo.tools.misc import formatLang

_PAY_READ = 'om_hr_payroll.group_hr_payroll_manager,base.group_system'


class EmployeeProfileTools(models.Model):
    _inherit = 'hr.employee'

    pb_profile_contract_pay = fields.Char(
        'Current contract salary', compute='_compute_profile_contract_pay',
        groups=_PAY_READ,
        help='Read from the current contract, in the paying scheme currency. '
             'Allowances and variable payments remain separate.')

    @api.depends('contract_id', 'contract_id.wage', 'contract_id.schedule_pay')
    def _compute_profile_contract_pay(self):
        for employee in self:
            contract = employee.contract_id
            if not contract:
                employee.pb_profile_contract_pay = _('No current contract')
                continue
            scheme = employee.pb_paid_by_id if 'pb_paid_by_id' in employee._fields else False
            currency = (scheme.sudo().currency_id if scheme else False) or employee.company_id.currency_id
            period = dict(contract._fields['schedule_pay']._description_selection(self.env)).get(contract.schedule_pay, '')
            employee.pb_profile_contract_pay = '%s %s · %s' % (
                currency.name, formatLang(self.env, contract.wage, digits=2), period)

    def action_upload_resume(self):
        self.ensure_one()
        self.env['pb.people']._require_hr()
        self.check_access('read')
        return {'type':'ir.actions.act_window','name':_('Upload résumé'),
                'res_model':'pb.employee.resume.upload','view_mode':'form','target':'new',
                'context':{'default_employee_id':self.id}}

    def action_view_resumes(self):
        self.ensure_one()
        self.env['pb.people']._require_hr()
        self.check_access('read')
        return {'type':'ir.actions.act_window','name':_('Résumés'),
                'res_model':'pb.employee.document','view_mode':'list,form',
                'domain':[('employee_id','=',self.id),('category_id.code','=','RESUME')],
                'context':{'create':False}}


class EmployeeResumeUpload(models.TransientModel):
    _name = 'pb.employee.resume.upload'
    _description = 'Upload employee résumé'

    employee_id = fields.Many2one('hr.employee', required=True, readonly=True)
    file_data = fields.Binary('Résumé (PDF)', required=True, attachment=False)
    filename = fields.Char(required=True)

    def action_upload(self):
        self.ensure_one()
        facade = self.env['pb.people']
        facade._require_hr()
        self.employee_id.check_access('read')
        try:
            content = base64.b64decode(self.file_data or b'', validate=True)
        except (ValueError, TypeError):
            raise ValidationError(_('Choose a valid PDF résumé.'))
        if not content.startswith(b'%PDF-') or not (self.filename or '').lower().endswith('.pdf'):
            raise ValidationError(_('Please upload the résumé as a PDF.'))
        if len(content) > 10 * 1024 * 1024:
            raise ValidationError(_('The résumé must be 10 MB or smaller.'))
        category = self.env.ref('pb_employee_vault.cat_resume')
        facade.vault_upload(self.employee_id.id, category.id,
            {'name':self.filename,'mime':'application/pdf','data':self.file_data.decode() if isinstance(self.file_data,bytes) else self.file_data})
        return {'type':'ir.actions.act_window_close'}
