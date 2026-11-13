"""Typed employee facts previously stored as payroll contract components."""

from odoo import fields, models


class HrEmployeePayrollProfile(models.Model):
    _inherit = 'hr.employee'

    pb_legal_first_name = fields.Char('Legal given name', groups='hr.group_hr_user')
    pb_legal_last_name = fields.Char('Legal family name', groups='hr.group_hr_user')
    pb_blood_type = fields.Char('Blood type', groups='hr.group_hr_manager',
                                help='Optional restricted personal information; not a payroll amount.')
    pb_religion = fields.Char('Religion', groups='hr.group_hr_manager',
                              help='Optional restricted personal information; not a payroll amount.')
    pb_emergency_relationship = fields.Char('Emergency contact relationship', groups='hr.group_hr_user')
    pb_permanent_address = fields.Text('Permanent address', groups='hr.group_hr_user',
                                      help='Permanent address when different from the current private address.')
    pb_position_reference = fields.Char('Position reference', index=True,
                                       help='Position identifier from the organization register, not employee ID.')
    pb_job_level = fields.Char('Job level', help='Reviewed job level; separate from salary and pay grade.')
    pb_visa_status = fields.Char('Visa status', groups='hr.group_hr_user')
    pb_npwp_number = fields.Char('Indonesia NPWP number', groups='hr.group_hr_user')
    pb_family_card_number = fields.Char('Indonesia family card number', groups='hr.group_hr_user')
    pb_bpjs_employment_number = fields.Char('BPJS employment member number', groups='hr.group_hr_user')
    pb_bpjs_health_number = fields.Char('BPJS health member number', groups='hr.group_hr_user')


class HrContractPayrollProfile(models.Model):
    _inherit = 'hr.contract'

    pb_trial_date_start = fields.Date('Probation start date',
        help='Explicit start of the probation period on this contract. Never inferred from joining or contract signature dates.')
    pb_signed_date = fields.Date('Contract signed on', help='Signature date, distinct from the effective start date.')
    pb_salary_basis = fields.Selection([('gross', 'Gross'), ('net', 'Net')],
                                        string='Salary denomination',
                                        help='Whether the agreed remuneration is gross or net; conversion still follows the approved payroll formula.')
    pb_payroll_contract_type = fields.Selection([
        ('permanent', 'Permanent'), ('probation', 'Probation'),
    ], string='Vietnam payroll contract treatment',
        help='Reviewed treatment used by the Vietnam payroll formula. It is separate from generic employment type.')
    pb_payroll_nationality_status = fields.Selection([
        ('vn', 'VN'), ('expat', 'Expat'),
    ], string='Vietnam payroll nationality treatment',
        help='Reviewed VN/Expat payroll classification. Citizenship does not determine this automatically.')
