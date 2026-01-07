# -*- coding:utf-8 -*-

import babel
from datetime import date, datetime, time
from dateutil.relativedelta import relativedelta
from pytz import timezone
from odoo import api, fields, models, tools, _
from odoo.exceptions import UserError, ValidationError
from bokeh.plotting import figure, output_file, show
from bokeh.palettes import HighContrast3
from bokeh.embed import components
from bokeh.models import ColumnDataSource, HoverTool, LabelSet, Legend, FactorRange
from bokeh.transform import factor_cmap, cumsum
from bokeh.palettes import Category20c
import json
from pudb import set_trace
#from odoo.addons.report_xlsx.report.report_xlsx import ReportXlsx

class HrPayslip(models.Model):
    _name = 'hr.payslip'
    _description = 'Pay Slip'
    _inherit = ['portal.mixin', 'mail.thread', 'mail.activity.mixin']
    _order = 'id desc'

    struct_id = fields.Many2one('hr.payroll.structure', string='Structure',
        readonly=True, states={'draft': [('readonly', False)]},
        help='Defines the rules that have to be applied to this payslip, accordingly '
             'to the contract chosen. If you let empty the field contract, this field isn\'t '
             'mandatory anymore and thus the rules applied will be all the rules set on the '
             'structure of all contracts of the employee valid for the chosen period')
    name = fields.Char(string='Payslip Name', readonly=True,
        states={'draft': [('readonly', False)]})
    number = fields.Char(string='Reference', readonly=True, copy=False,
        states={'draft': [('readonly', False)]})
    employee_id = fields.Many2one('hr.employee', string='Employee', required=True, readonly=True,
        states={'draft': [('readonly', False)]})
    date_from = fields.Date(string='Date From', readonly=True, required=True,
        default=lambda self: fields.Date.to_string(date.today().replace(day=1)), states={'draft': [('readonly', False)]})
    date_to = fields.Date(string='Date To', readonly=True, required=True,
        default=lambda self: fields.Date.to_string((datetime.now() + relativedelta(months=+1, day=1, days=-1)).date()),
        states={'draft': [('readonly', False)]})
    # this is chaos: 4 states are defined, 3 are used ('verify' isn't) and 5 exist ('confirm' seems to have existed)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('verify', 'Waiting'),
        ('level1', 'HR Manager pending'),
        ('level2', 'General Manager pending'),
        ('done', 'Done'),
        ('cancel', 'Rejected'),
    ], string='Status', index=True, readonly=True, copy=False, default='draft',
        help="""* When the payslip is created the status is \'Draft\'
                \n* If the payslip is under verification, the status is \'Waiting\'.
                \n* If the payslip is confirmed then status is set to \'Done\'.
                \n* When user cancel payslip the status is \'Rejected\'.""")
    line_ids = fields.One2many('hr.payslip.line', 'slip_id', string='Payslip Lines', readonly=True,
        states={'draft': [('readonly', False)]})
    company_id = fields.Many2one('res.company', string='Company', readonly=True, copy=False,
                                 default=lambda self: self.env.company,
                                 states={'draft': [('readonly', False)]})
    worked_days_line_ids = fields.One2many('hr.payslip.worked_days', 'payslip_id',
        string='Payslip Worked Days', copy=True, readonly=True,
        states={'draft': [('readonly', False)]})
    input_line_ids = fields.One2many('hr.payslip.input', 'payslip_id', string='Payslip Inputs',
        readonly=True, copy=True, states={'draft': [('readonly', False)]})
    paid = fields.Boolean(string='Made Payment Order ? ', readonly=True, copy=False,
        states={'draft': [('readonly', False)]})
    note = fields.Text(string='Internal Note', readonly=True, states={'draft': [('readonly', False)]})
    contract_id = fields.Many2one('hr.contract', string='Contract', readonly=True,
        states={'draft': [('readonly', False)]})
    details_by_salary_rule_category = fields.One2many('hr.payslip.line',
        compute='_compute_details_by_salary_rule_category', string='Details by Salary Rule Category')
    credit_note = fields.Boolean(string='Credit Note', readonly=True,
        states={'draft': [('readonly', False)]},
        help="Indicates this payslip has a refund of another")
    payslip_run_id = fields.Many2one('hr.payslip.run', string='Payslip Batches', readonly=True,
        copy=False, states={'draft': [('readonly', False)]})
    payslip_count = fields.Integer(compute='_compute_payslip_count', string="Payslip Computation Details")
    #Biztinct
    #bokeh_chart = fields.Text(string='Bokeh Chart', compute='_compute_bokeh_chart')
    def _compute_bokeh_chart(self):
        for rec in self:
            # Sample data (replace with your actual data)
            # Sample data (replace with your data)
            labels = ["Category A", "Category B", "Category C"]
            values = [45, 25, 30]
            colors = ["#718dbf", "#e84d60", "#c9d9d3"] 

            # Create data source
            source = ColumnDataSource(data=dict(labels=labels, values=values, colors=colors))

            # Create the Bokeh plot
            p = figure(x_range=labels, height=350, title="Data Distribution",
                       toolbar_location=None, tools="")

            # Create bars
            p.vbar(x='labels', top='values', width=0.9, color='colors', source=source)

            # Add labels on top of the bars
            labels = LabelSet(x='labels', y='values', text='values', level='glyph',
                  x_offset=0, y_offset=5, source=source, 
                  text_align='center') 
            p.add_layout(labels)

            # Styling 
            p.xgrid.grid_line_color = None
            p.y_range.start = 0

            # Embed the plot components
            script, div = components(p, wrap_script=False)
            rec.bokeh_chart = json.dumps({"div": div, "script": script})

    # portal.mixin override
    def _compute_access_url(self):
        super()._compute_access_url()
        for payslip in self:
            payslip.access_url = f'/my/payslips/{payslip.id}'
    
    def _get_report_base_filename(self):
        self.ensure_one()
        return '%s' % (self.name)

    def _compute_details_by_salary_rule_category(self):
        for payslip in self:
            payslip.details_by_salary_rule_category = payslip.mapped('line_ids').filtered(lambda line: line.category_id)

    def _compute_payslip_count(self):
        for payslip in self:
            payslip.payslip_count = len(payslip.line_ids)

    @api.constrains('date_from', 'date_to')
    def _check_dates(self):
        if any(self.filtered(lambda payslip: payslip.date_from > payslip.date_to)):
            raise ValidationError(_("Payslip 'Date From' must be earlier 'Date To'."))

    def action_payslip_draft(self):
        return self.write({'state': 'draft'})

    def action_payslip_done(self):
        #self.compute_sheet()
        #Biztinct
        #return self.write({'state': 'done'})
        return self.write({'state': 'level1'})
    
    #Biztinct
    def action_payslip_level1_done(self):
        result = self.write({'state': 'level2'})
        
        # Auto-generate analytics when payslips reach Level 2
        if self.env['ir.config_parameter'].sudo().get_param('payroll_analytics_approval.auto_generate', 'True') == 'True':
            self._auto_generate_analytics_on_level2()
        
        return result
    
    def _auto_generate_analytics_on_level2(self):
        """Auto-generate analytics when payslips reach Level 2 state"""
        try:
            # Only generate analytics if we have the analytics module installed
            if 'payroll.analytics' not in self.env:
                return
            
            # Get the country from the payslip structure or fallback
            country = 'VN'  # Default to Vietnam, can be enhanced to detect from structure
            
            # Get date range from current payslips (only this specific set, not all Level 2)
            payslip_dates = [slip.date_from for slip in self] + [slip.date_to for slip in self]
            if payslip_dates:
                # Group payslips by month to avoid cross-month analytics
                payslips_by_month = {}
                for slip in self:
                    month_key = (slip.date_from.year, slip.date_from.month)
                    if month_key not in payslips_by_month:
                        payslips_by_month[month_key] = []
                    payslips_by_month[month_key].append(slip)
                
                # Generate separate analytics for each month
                for month_key, month_payslips in payslips_by_month.items():
                    first_day = min([slip.date_from for slip in month_payslips])
                    last_day = max([slip.date_to for slip in month_payslips])
                    
                    # Generate analytics for this specific month and country
                    analytics_model = self.env['payroll.analytics']
                    existing_analytics = analytics_model.search([
                        ('country', '=', country),
                        ('date_from', '=', first_day),
                        ('date_to', '=', last_day)
                    ], limit=1)
                    
                    if not existing_analytics:
                        analytics = analytics_model.generate_analytics(country, first_day, last_day)
                        analytics.write({'state': 'ready'})
                    
        except Exception as e:
            # Don't fail payslip approval if analytics generation fails
            import logging
            _logger = logging.getLogger(__name__)
            _logger.warning(f"Failed to auto-generate analytics on Level 2: {e}")

    #Biztinct
    def action_payslip_level2_done(self):
        return self.write({'state': 'done'})


    def action_payslip_cancel(self):
        # if self.filtered(lambda slip: slip.state == 'done'):
        #     raise UserError(_("Cannot cancel a payslip that is done."))
        return self.write({'state': 'cancel'})

    def refund_sheet(self):
        for payslip in self:
            copied_payslip = payslip.copy({'credit_note': True, 'name': _('Refund: ') + payslip.name})
            copied_payslip.compute_sheet()
            copied_payslip.action_payslip_done()
        form_view_ref = self.env.ref('om_om_hr_payroll.view_hr_payslip_form', False)
        tree_view_ref = self.env.ref('om_om_hr_payroll.view_hr_payslip_tree', False)
        return {
            'name': (_("Refund Payslip")),
            'view_mode': 'tree, form',
            'view_id': False,
            'view_type': 'form',
            'res_model': 'hr.payslip',
            'type': 'ir.actions.act_window',
            'target': 'current',
            'domain': "[('id', 'in', %s)]" % copied_payslip.ids,
            'views': [(tree_view_ref and tree_view_ref.id or False, 'tree'), (form_view_ref and form_view_ref.id or False, 'form')],
            'context': {}
        }

    def action_send_email(self):
        self.ensure_one()
        ir_model_data = self.env['ir.model.data']
        try:
            template_id = self.env.ref('om_hr_payroll.mail_template_payslip').id
        except ValueError:
            template_id = False
        try:
            compose_form_id = ir_model_data._xmlid_lookup('mail.email_compose_message_wizard_form')[2]
        except ValueError:
            compose_form_id = False
        ctx = {
            'default_model': 'hr.payslip',
            'default_res_id': self.ids[0],
            'default_use_template': bool(template_id),
            'default_template_id': template_id,
            'default_composition_mode': 'comment',
        }
        return {
            'name': _('Compose Email'),
            'type': 'ir.actions.act_window',
            'view_mode': 'form',
            'res_model': 'mail.compose.message',
            'views': [(compose_form_id, 'form')],
            'view_id': compose_form_id,
            'target': 'new',
            'context': ctx,
        }

#Biztinct
    def action_send_email_backend(self):
        self.ensure_one()
        template = self.env.ref('om_hr_payroll.mail_template_payslip', raise_if_not_found=False)
        if not template:
            raise ValidationError('Email template not found.')
        
        template.send_mail(self.id, force_send=False)

    def action_send_email_tree(self):
        for record in self:
            if record.state == 'done' :
                record.action_send_email_backend()
        self.env.user.notify_info(message="Only Payslips with status as Done have been mailed ", title='INFO', sticky=False)

    def check_done(self):
        return True

    def unlink(self):
        if any(self.filtered(lambda payslip: payslip.state not in ('draft', 'cancel'))):
            raise UserError(_('You cannot delete a payslip which is not draft or cancelled!'))
        return super(HrPayslip, self).unlink()

    # TODO move this function into hr_contract module, on hr.employee object
    @api.model
    def get_contract(self, employee, date_from, date_to):
        """
        @param employee: recordset of employee
        @param date_from: date field
        @param date_to: date field
        @return: returns the ids of all the contracts for the given employee that need to be considered for the given dates
        """
        # a contract is valid if it ends between the given dates
        clause_1 = ['&', ('date_end', '<=', date_to), ('date_end', '>=', date_from)]
        # OR if it starts between the given dates
        clause_2 = ['&', ('date_start', '<=', date_to), ('date_start', '>=', date_from)]
        # OR if it starts before the date_from and finish after the date_end (or never finish)
        clause_3 = ['&', ('date_start', '<=', date_from), '|', ('date_end', '=', False), ('date_end', '>=', date_to)]
        clause_final = [('employee_id', '=', employee.id), ('state', '=', 'open'), '|', '|'] + clause_1 + clause_2 + clause_3
        return self.env['hr.contract'].search(clause_final).ids

    #Biztinct - metod to get zoho employee data into payslip lineids
    def update_payslip_lines_from_zoho_data(self,payslip):
        """
        Update payslip line_ids amount field with values
        from zoho.employee.data.

        Args:
            payslip: The payslip record to update.
        """
        payroll_from_spreadsheet = self.env[
            'ir.config_parameter'
        ].sudo().get_param('payroll_from_spreadsheet')
        if payroll_from_spreadsheet == 'True':
            zoho_data = self.env['zoho.employee.data'].search(
                [('employee_id', '=', payslip.employee_id.employee_id)]
            )
            if zoho_data:
                field_mapping = {
               # Vietnam/Generic mappings (existing)
               'ACTBASE': 'actual_basicsalary',
                'ACTGAZ': 'actual_gas',
                'ACTPHONE': 'actual_phone',
                'ACTMEAL': 'actual_meal',
                'ACTRESP': 'actual_resp',
                'ACTPARK': 'actual_parking',
                'ACTTAXI': 'actual_taxi',
                'OT15': 'ot_15amount',
                'OT2': 'ot_2amount',
                'OT3': 'ot_3amount',
                'NS': 'ns_amount',
                'OTNW': 'otns_weekamount',
                'OTNO': 'otns_offamount',
                'OTNH': 'otns_holamount',
                'TOTOT': 'total_otamount',  
                'ATI': 'actual_totalincome',
                'SI': 'salary_si',
                'UI': 'salary_ui',
                'SIEIGHT': 'social_ins8',
                'MIONEFIVE': 'med_ins15',
                'UIONE': 'unemp_ins1',
                'SIHIUITEN': 'sihiui_total105',
                'EMPTU': 'etu',
                'DEPAMT': 'dep_amount',
                'OTTAX': 'ot_tax',
                'OTNT': 'ot_nontax',
                'TAXIN': 'tax_income',
                'TAXINAD': 'taxincome_afterded',
                'MONPIT': 'monthly_pit',
                'TOTDEDU': 'total_ded',
                'NETPAY': 'net_pay',
                'SOCSEVEN': 'social_ins175',
                'MEDTHREE': 'med_ins3',
                'UNONE': 'unemp_ins1',  
                'SIHIUIT': 'sihiui_total215',
                'TUERTWO': 'trade_er2',
                'TCTE': 'total_cte',
                
                # Indonesia-specific mappings for spreadsheet headers
                'BASIC_SALARY': 'actual_basic_salary',
                'GAS_ALLOWANCE': 'actual_gas_allowance', 
                'PHONE_ALLOWANCE': 'actual_phone_allowance',
                'MEAL_ALLOWANCE': 'actual_meal_allowance',
                'BPJS_KES_EMP': 'calculated_bpjs_health_emp',
                'BPJS_JHT_EMP': 'calculated_bpjs_jht_emp',
                'BPJS_JP_EMP': 'calculated_bpjs_jp_emp',
                'BPJS_KES_COMP': 'calculated_bpjs_health_comp',
                'BPJS_JHT_COMP': 'calculated_bpjs_jht_comp',
                'BPJS_JP_COMP': 'calculated_bpjs_jp_comp',
                'PPH21_TAX': 'calculated_pph21_tax',
                'GROSS_PAY': 'calculated_gross_pay',
                'NET_PAY': 'calculated_net_pay',
                'TOTAL_DEDUCTIONS': 'calculated_total_deductions',
                'OVERTIME_AMOUNT': 'total_overtime_amount'
                }
                for line in payslip.line_ids:
                    zoho_field = field_mapping.get(line.code)
                    if zoho_field:
                        line.amount = getattr(zoho_data, zoho_field) or 0.0


    def compute_sheet(self):
        for payslip in self:
            number = payslip.number or self.env['ir.sequence'].next_by_code('salary.slip')
            # delete old payslip lines
            payslip.line_ids.unlink()
            # set the list of contract for which the rules have to be applied
            # if we don't give the contract, then the rules to apply should be for all current contracts of the employee
            contract_ids = payslip.contract_id.ids or \
                self.get_contract(payslip.employee_id, payslip.date_from, payslip.date_to)
            if not contract_ids:
                raise ValidationError(_("No running contract found for the employee: %s or no contract in the given period" % payslip.employee_id.name))
            lines = [(0, 0, line) for line in self._get_payslip_lines(contract_ids, payslip.id)]
            payslip.write({'line_ids': lines, 'number': number})
            #Biztinct - Overwrite line_ids amount with spreadsheet data which is now stored in Zoho employee data table
            self.update_payslip_lines_from_zoho_data(payslip)
        return True

    @api.model
    def get_worked_day_lines(self, contracts, date_from, date_to):
        """
        @param contract: Browse record of contracts
        @return: returns a list of dict containing the input that should be applied for the given contract between date_from and date_to
        """
        res = []
        # fill only if the contract as a working schedule linked
        for contract in contracts.filtered(lambda contract: contract.resource_calendar_id):
            day_from = datetime.combine(fields.Date.from_string(date_from), time.min)
            day_to = datetime.combine(fields.Date.from_string(date_to), time.max)

            # compute leave days
            leaves = {}
            calendar = contract.resource_calendar_id
            tz = timezone(calendar.tz)
            day_leave_intervals = contract.employee_id.list_leaves(day_from, day_to, calendar=contract.resource_calendar_id)
            for day, hours, leave in day_leave_intervals:
                holiday = leave.holiday_id
                current_leave_struct = leaves.setdefault(holiday.holiday_status_id, {
                    'name': holiday.holiday_status_id.name or _('Global Leaves'),
                    'sequence': 5,
                    'code': holiday.holiday_status_id.code or 'GLOBAL',
                    'number_of_days': 0.0,
                    'number_of_hours': 0.0,
                    'contract_id': contract.id,
                })
                current_leave_struct['number_of_hours'] -= hours
                work_hours = calendar.get_work_hours_count(
                    tz.localize(datetime.combine(day, time.min)),
                    tz.localize(datetime.combine(day, time.max)),
                    compute_leaves=False,
                )
                if work_hours:
                    current_leave_struct['number_of_days'] -= hours / work_hours

            # compute worked days
            work_data = contract.employee_id._get_work_days_data(
                day_from,
                day_to,
                calendar=contract.resource_calendar_id,
                compute_leaves=False,
            )

            zoho_employee = self.env['zoho.employee.data'].search([('employee_id', '=', self.employee_id.employee_id)], limit=1)
            #zoho_employee = self.env['zoho.employee.data'].search([('employee_id', '=', '11660')], limit=1)
            if zoho_employee:
                #set_trace()
                standard_whr = zoho_employee.standard_whr
            else :
                standard_whr = work_data['hours']

            attendances = {
                'name': _("Normal Working Days paid at 100%"),
                'sequence': 1,
                'code': 'WORK100',
                'number_of_days': work_data['days'],
                #'number_of_hours': work_data['hours'],
                'number_of_hours': standard_whr,
                'contract_id': contract.id,
            }

            res.append(attendances)
            res.extend(leaves.values())
            #set_trace()
            att_list = []
            att_list = [{'name': _("Actual work incl paid leave"), 'sequence': 2, 'code': 'ACPL', 'contract_id': contract.id, 'number_of_hours': zoho_employee.actual_working_hours_incl_paid_leave },
            {'name': _("Actual work not incl paid leave"), 'sequence': 3, 'code': 'ACNPL', 'contract_id': contract.id, 'number_of_hours': zoho_employee.actual_working_hours_excl_paid_leave},
            {'name': _("OT 1.5 Hrs"), 'sequence': 4, 'code': 'OT15', 'contract_id': contract.id, 'number_of_hours': zoho_employee.overtime_normal_150_hour },
            {'name': _("OT 2 Hrs"), 'sequence': 5, 'code': 'OT2', 'contract_id': contract.id,'number_of_hours': zoho_employee.overtime_weekend_200_hour },
            {'name': _("OT 3 Hrs"), 'sequence': 6, 'code': 'OT3', 'contract_id': contract.id, 'number_of_hours': zoho_employee.overtime_holiday_300_hour },
            {'name': _("OT Night Shift Week day"), 'sequence': 7, 'code': 'OTNW', 'contract_id': contract.id, 'number_of_hours': zoho_employee.overtime_nightshift_210_hour },
            {'name': _("OT Night Shift Off day"), 'sequence': 8, 'code': 'OTNO', 'contract_id': contract.id, 'number_of_hours': zoho_employee.overtime_nightshift_270_hour },
            {'name': _("OT Night Shift Holiday"), 'sequence': 9, 'code': 'OTNH', 'contract_id': contract.id, 'number_of_hours': zoho_employee.overtime_nightshift_390_hour },
            {'name': _("Night Shift"), 'sequence': 10, 'code': 'NS', 'contract_id': contract.id, 'number_of_hours': zoho_employee.nightshift_hour },
            #{'name': _("Paid leave unused"), 'sequence': 11, 'code': 'PAIDUNUSED', 'contract_id': contract.id, 'number_of_hours': zoho_employee.paidleave_unused },            
             ]
            res.extend(att_list)

            #Biztinct TODO
            #Get hours from the raw table populated by API

        return res

    @api.model
    def get_inputs(self, contracts, date_from, date_to):
        res = []

        structure_ids = contracts.get_all_structures()
        rule_ids = self.env['hr.payroll.structure'].browse(structure_ids).get_all_rules()
        sorted_rule_ids = [id for id, sequence in sorted(rule_ids, key=lambda x:x[1])]
        inputs = self.env['hr.salary.rule'].browse(sorted_rule_ids).mapped('input_ids')

        for contract in contracts:
            for input in inputs:
                input_data = {
                    'name': input.name,
                    'code': input.code,
                    'contract_id': contract.id,
                }
                res += [input_data]
        return res

    @api.model
    def _get_payslip_lines(self, contract_ids, payslip_id):
        def _sum_salary_rule_category(localdict, category, amount):
            if category.parent_id:
                localdict = _sum_salary_rule_category(localdict, category.parent_id, amount)
            localdict['categories'].dict[category.code] = category.code in localdict['categories'].dict and localdict['categories'].dict[category.code] + amount or amount
            return localdict

        class BrowsableObject(object):
            def __init__(self, employee_id, dict, env):
                self.employee_id = employee_id
                self.dict = dict
                self.env = env

            def __getattr__(self, attr):
                return attr in self.dict and self.dict.__getitem__(attr) or 0.0

        class InputLine(BrowsableObject):
            """a class that will be used into the python code, mainly for usability purposes"""
            def sum(self, code, from_date, to_date=None):
                if to_date is None:
                    to_date = fields.Date.today()
                self.env.cr.execute("""
                    SELECT sum(amount) as sum
                    FROM hr_payslip as hp, hr_payslip_input as pi
                    WHERE hp.employee_id = %s AND hp.state = 'done'
                    AND hp.date_from >= %s AND hp.date_to <= %s AND hp.id = pi.payslip_id AND pi.code = %s""",
                    (self.employee_id, from_date, to_date, code))
                return self.env.cr.fetchone()[0] or 0.0

        class WorkedDays(BrowsableObject):
            """a class that will be used into the python code, mainly for usability purposes"""
            def _sum(self, code, from_date, to_date=None):
                if to_date is None:
                    to_date = fields.Date.today()
                self.env.cr.execute("""
                    SELECT sum(number_of_days) as number_of_days, sum(number_of_hours) as number_of_hours
                    FROM hr_payslip as hp, hr_payslip_worked_days as pi
                    WHERE hp.employee_id = %s AND hp.state = 'done'
                    AND hp.date_from >= %s AND hp.date_to <= %s AND hp.id = pi.payslip_id AND pi.code = %s""",
                    (self.employee_id, from_date, to_date, code))
                return self.env.cr.fetchone()

            def sum(self, code, from_date, to_date=None):
                res = self._sum(code, from_date, to_date)
                return res and res[0] or 0.0

            def sum_hours(self, code, from_date, to_date=None):
                res = self._sum(code, from_date, to_date)
                return res and res[1] or 0.0

        class Payslips(BrowsableObject):
            """a class that will be used into the python code, mainly for usability purposes"""

            def sum(self, code, from_date, to_date=None):
                if to_date is None:
                    to_date = fields.Date.today()
                self.env.cr.execute("""SELECT sum(case when hp.credit_note = False then (pl.total) else (-pl.total) end)
                            FROM hr_payslip as hp, hr_payslip_line as pl
                            WHERE hp.employee_id = %s AND hp.state = 'done'
                            AND hp.date_from >= %s AND hp.date_to <= %s AND hp.id = pl.slip_id AND pl.code = %s""",
                            (self.employee_id, from_date, to_date, code))
                res = self.env.cr.fetchone()
                return res and res[0] or 0.0

        #we keep a dict with the result because a value can be overwritten by another rule with the same code
        result_dict = {}
        rules_dict = {}
        worked_days_dict = {}
        inputs_dict = {}
        blacklist = []
        payslip = self.env['hr.payslip'].browse(payslip_id)
        for worked_days_line in payslip.worked_days_line_ids:
            worked_days_dict[worked_days_line.code] = worked_days_line.number_of_days
        for input_line in payslip.input_line_ids:
            inputs_dict[input_line.code] = input_line  
        #set_trace()
        categories = BrowsableObject(payslip.employee_id.id, {}, self.env)
        inputs = InputLine(payslip.employee_id.id, inputs_dict, self.env)
        worked_days = WorkedDays(payslip.employee_id.id, worked_days_dict, self.env)
        payslips = Payslips(payslip.employee_id.id, payslip, self.env)
        rules = BrowsableObject(payslip.employee_id.id, rules_dict, self.env)

        baselocaldict = {'categories': categories, 'rules': rules, 'payslip': payslips, 'worked_days': worked_days, 'inputs': inputs}
        #baselocaldict = {'categories': categories, 'rules': rules, 'worked_days': worked_days, 'inputs': inputs}

        #Biztinct
        #payslip_dict = {}
        #for payslip_line in payslip.line_ids:
        #    payslip_dict[payslip_line.code] = payslip_line.amount
        #baselocaldict.update(
        #    {"payslip": BrowsableObject(payslip.employee_id, payslip_dict, self.env)}
        #    )         
        #Biztinct change ends

        #get the ids of the structures on the contracts and their parent id as well
        contracts = self.env['hr.contract'].browse(contract_ids)
        if len(contracts) == 1 and payslip.struct_id:
            structure_ids = list(set(payslip.struct_id._get_parent_structure().ids))
        else:
            structure_ids = contracts.get_all_structures()
        #get the rules of the structure and thier children
        rule_ids = self.env['hr.payroll.structure'].browse(structure_ids).get_all_rules()
        #run the rules by sequence
        sorted_rule_ids = [id for id, sequence in sorted(rule_ids, key=lambda x:x[1])]
        sorted_rules = self.env['hr.salary.rule'].browse(sorted_rule_ids)

        for contract in contracts:
            employee = contract.employee_id
            #set_trace()
            #Biztinct changes
            advantages_dict = {}
            for advantage in contract.advantages_ids:
                advantages_dict[advantage.advantage_template_code] = advantage.amount
            baselocaldict.update(
                {"component": BrowsableObject(payslip.employee_id, advantages_dict, self.env)}
                )
            worked_hours_dict = {}
            for worked_days_line in payslip.worked_days_line_ids:
                worked_hours_dict[worked_days_line.code] = worked_days_line.number_of_hours
            baselocaldict.update(
                {"worked_hours": BrowsableObject(payslip.employee_id, worked_hours_dict, self.env)}
                )                
            ## Change ends

            localdict = dict(baselocaldict, employee=employee, contract=contract)
            for rule in sorted_rules:
                key = rule.code + '-' + str(contract.id)
                localdict['result'] = None
                localdict['result_qty'] = 1.0
                localdict['result_rate'] = 100
                #check if the rule can be applied
                if rule._satisfy_condition(localdict) and rule.id not in blacklist:
                    #compute the amount of the rule
                    #set_trace()
                    amount, qty, rate = rule._compute_rule(localdict)
                    #check if there is already a rule computed with that code
                    previous_amount = rule.code in localdict and localdict[rule.code] or 0.0
                    #set/overwrite the amount computed for this rule in the localdict
                    tot_rule = contract.company_id.currency_id.round(amount * qty * rate / 100.0)
                    localdict[rule.code] = tot_rule
                    #rules_dict[rule.code] = rule
                    rules_dict[rule.code] = amount
                    #sum the amount for its salary category
                    localdict = _sum_salary_rule_category(localdict, rule.category_id, tot_rule - previous_amount)
                    #create/overwrite the rule in the temporary results
                    result_dict[key] = {
                        'salary_rule_id': rule.id,
                        'contract_id': contract.id,
                        'name': rule.name,
                        'code': rule.code,
                        'category_id': rule.category_id.id,
                        'sequence': rule.sequence,
                        'appears_on_payslip': rule.appears_on_payslip,
                        'condition_select': rule.condition_select,
                        'condition_python': rule.condition_python,
                        'condition_range': rule.condition_range,
                        'condition_range_min': rule.condition_range_min,
                        'condition_range_max': rule.condition_range_max,
                        'amount_select': rule.amount_select,
                        'amount_fix': rule.amount_fix,
                        'amount_python_compute': rule.amount_python_compute,
                        'amount_percentage': rule.amount_percentage,
                        'amount_percentage_base': rule.amount_percentage_base,
                        'register_id': rule.register_id.id,
                        'amount': amount,
                        'employee_id': contract.employee_id.id,
                        'quantity': qty,
                        'rate': rate,
                    }
                else:
                    #blacklist this rule and its children
                    blacklist += [id for id, seq in rule._recursive_search_of_rules()]

        return list(result_dict.values())

    # YTI TODO To rename. This method is not really an onchange, as it is not in any view
    # employee_id and contract_id could be browse records
    def onchange_employee_id(self, date_from, date_to, employee_id=False, contract_id=False):
        #defaults
        res = {
            'value': {
                'line_ids': [],
                #delete old input lines
                'input_line_ids': [(2, x,) for x in self.input_line_ids.ids],
                #delete old worked days lines
                'worked_days_line_ids': [(2, x,) for x in self.worked_days_line_ids.ids],
                #'details_by_salary_head':[], TODO put me back
                'name': '',
                'contract_id': False,
                'struct_id': False,
            }
        }
        if (not employee_id) or (not date_from) or (not date_to):
            return res
        ttyme = datetime.combine(fields.Date.from_string(date_from), time.min)
        ttyme2 = datetime.combine(fields.Date.from_string(date_to), time.min)
        employee = self.env['hr.employee'].browse(employee_id)
        locale = self.env.context.get('lang') or 'en_US'
        res['value'].update({
#            'name': _('Salary Slip of %s for %s') % (employee.name, tools.ustr(babel.dates.format_date(date=ttyme, format='MMMM-y', locale=locale))),
            'name': _('Salary Slip of %s for %s to %s') % (employee.name, tools.ustr(babel.dates.format_date(date=ttyme, format='dd-MMM-yy', locale=locale)), tools.ustr(babel.dates.format_date(date=ttyme2, format='dd-MMM-yy', locale=locale))),
            'company_id': employee.company_id.id,
        })

        if not self.env.context.get('contract'):
            #fill with the first contract of the employee
            contract_ids = self.get_contract(employee, date_from, date_to)
        else:
            if contract_id:
                #set the list of contract for which the input have to be filled
                contract_ids = [contract_id]
            else:
                #if we don't give the contract, then the input to fill should be for all current contracts of the employee
                contract_ids = self.get_contract(employee, date_from, date_to)

        if not contract_ids:
            return res
        contract = self.env['hr.contract'].browse(contract_ids[0])
        res['value'].update({
            'contract_id': contract.id
        })
        struct = contract.struct_id
        if not struct:
            return res
        res['value'].update({
            'struct_id': struct.id,
        })
        #computation of the salary input
        contracts = self.env['hr.contract'].browse(contract_ids)
        worked_days_line_ids = self.get_worked_day_lines(contracts, date_from, date_to)
        #Biztinct - populate worked days data from Zoho Employee data
        lemployee = self.env['hr.employee'].search([('id', '=', employee_id)], limit=1)
        zoho_employee = self.env['zoho.employee.data'].search([('employee_id', '=', lemployee.employee_id)], limit=1)
        for line in worked_days_line_ids:
            
            if line['code'] == 'WORK100':
                line['number_of_hours'] = zoho_employee.standard_whr
            elif line['code'] == 'ACPL':
                line['number_of_hours'] = zoho_employee.actual_working_hours_incl_paid_leave
            elif line['code'] == 'ACNPL':
                line['number_of_hours'] = zoho_employee.actual_working_hours_excl_paid_leave
            elif line['code'] == 'OT15':
                line['number_of_hours'] = zoho_employee.overtime_normal_150_hour
            elif line['code'] == 'OT2':
                line['number_of_hours'] = zoho_employee.overtime_weekend_200_hour
            elif line['code'] == 'OT3':
                line['number_of_hours'] = zoho_employee.overtime_holiday_300_hour
            elif line['code'] == 'OTNW':
                line['number_of_hours'] = zoho_employee.overtime_nightshift_200_hour
            elif line['code'] == 'OTNO':
                line['number_of_hours'] = zoho_employee.overtime_nightshift_270_hour
            elif line['code'] == 'OTNH':
                line['number_of_hours'] = zoho_employee.overtime_nightshift_390_hour   
            #Biztinct - Paid leave unused is amount and not hours so it should go into contract to be given at end of employment
            #elif line['code'] == 'PAIDUNUSED':
            #    line['number_of_hours'] = zoho_employee.paidleave_unused   



        input_line_ids = self.get_inputs(contracts, date_from, date_to)
        res['value'].update({
            'worked_days_line_ids': worked_days_line_ids,
            'input_line_ids': input_line_ids,
        })

        return res

    @api.onchange('employee_id', 'date_from', 'date_to')
    def onchange_employee(self):
        self.ensure_one()
        if (not self.employee_id) or (not self.date_from) or (not self.date_to):
            return
 
        #Biztinct -  Search for the employee in zoho.employee.data using the employee's name
        zoho_employee = self.env['zoho.employee.data'].search([('employee_id', '=', self.employee_id.employee_id)], limit=1)
        #if zoho_employee:
            # If found, update the date_from and date_to fields
        #    self.date_from = zoho_employee.start_date
        #    self.date_to = zoho_employee.end_date  

        employee = self.employee_id
        date_from = self.date_from
        date_to = self.date_to
        contract_ids = []

        ttyme = datetime.combine(fields.Date.from_string(date_from), time.min)
        ttyme2 = datetime.combine(fields.Date.from_string(date_to), time.min)
        locale = self.env.context.get('lang') or 'en_US'
        #self.name = _('Salary Slip of %s for %s') % (employee.name, tools.ustr(babel.dates.format_date(date=ttyme, format='MMMM-y', locale=locale)))
        self.name =  _('Salary Slip of %s for %s to %s') % (employee.name, tools.ustr(babel.dates.format_date(date=ttyme, format='dd-MMM-yy', locale=locale)), tools.ustr(babel.dates.format_date(date=ttyme2, format='dd-MMM-yy', locale=locale)))
        self.company_id = employee.company_id

        if not self.env.context.get('contract') or not self.contract_id:
            contract_ids = self.get_contract(employee, date_from, date_to)
            if not contract_ids:
                return
            self.contract_id = self.env['hr.contract'].browse(contract_ids[0])

        if not self.contract_id.struct_id:
            return
        self.struct_id = self.contract_id.struct_id


        #computation of the salary input
        contracts = self.env['hr.contract'].browse(contract_ids)
        if contracts:
            worked_days_line_ids = self.get_worked_day_lines(contracts, date_from, date_to)
            worked_days_lines = self.worked_days_line_ids.browse([])
            for r in worked_days_line_ids:
                worked_days_lines += worked_days_lines.new(r)
            self.worked_days_line_ids = worked_days_lines

            input_line_ids = self.get_inputs(contracts, date_from, date_to)
            input_lines = self.input_line_ids.browse([])
            for r in input_line_ids:
                input_lines += input_lines.new(r)
            self.input_line_ids = input_lines

            #Biztinct - populate worked days data from Zoho Employee data

            for line in self.worked_days_line_ids:
                #set_trace()
                if line.code == 'WORK100':
                    line.number_of_hours = zoho_employee.standard_whr
                elif line.code == 'ACPL':
                    line.number_of_hours = zoho_employee.actual_working_hours_incl_paid_leave
                elif line.code == 'ACNPL':
                    line.number_of_hours = zoho_employee.actual_working_hours_excl_paid_leave
                elif line.code == 'OT15':
                    line.number_of_hours = zoho_employee.overtime_normal_150_hour
                elif line.code == 'OT2':
                    line.number_of_hours = zoho_employee.overtime_weekend_200_hour
                elif line.code == 'OT3':
                    line.number_of_hours = zoho_employee.overtime_holiday_300_hour
                elif line.code == 'OTNW':
                    line.number_of_hours = zoho_employee.overtime_nightshift_200_hour
                elif line.code == 'OTNO':
                    line.number_of_hours = zoho_employee.overtime_nightshift_270_hour
                elif line.code == 'OTNH':
                    line.number_of_hours = zoho_employee.overtime_nightshift_390_hour            
                #elif line.code == 'PAIDUNUSED':
                #    line.number_of_hours = zoho_employee.paidleave_unused    

            return

    @api.onchange('contract_id')
    def onchange_contract(self):
        if not self.contract_id:
            self.struct_id = False
        self.with_context(contract=True).onchange_employee()
        return

    def get_salary_line_total(self, code):
        self.ensure_one()
        line = self.line_ids.filtered(lambda line: line.code == code)
        if line:
            return line[0].total
        else:
            return 0.0


class HrPayslipLine(models.Model):
    _name = 'hr.payslip.line'
    _inherit = 'hr.salary.rule'
    _description = 'Payslip Line'
    _order = 'date_to desc, contract_id, sequence'

    slip_id = fields.Many2one('hr.payslip', string='Pay Slip', required=True, ondelete='cascade')
    salary_rule_id = fields.Many2one('hr.salary.rule', string='Rule', required=True)
    employee_id = fields.Many2one('hr.employee', string='Employee', required=True)
    contract_id = fields.Many2one('hr.contract', string='Contract', required=True, index=True)
    rate = fields.Float(string='Rate (%)', default=100.0)
    amount = fields.Float()
    quantity = fields.Float(default=1.0)
    total = fields.Float(compute='_compute_total', string='Total', store=True)
    date_from = fields.Date(related='slip_id.date_from', string='Date From', store=True)
    date_to = fields.Date(related='slip_id.date_to', string='Date To', store=True)
    costcenter = fields.Char(related='slip_id.contract_id.costcenter', string='Cost center', store=True)
    @api.depends('quantity', 'amount', 'rate')
    def _compute_total(self):
        for line in self:
            line.total = float(line.quantity) * line.amount * line.rate / 100

    @api.model_create_multi
    def create(self, vals_list):
        for values in vals_list:
            if 'employee_id' not in values or 'contract_id' not in values:
                payslip = self.env['hr.payslip'].browse(values.get('slip_id'))
                values['employee_id'] = values.get('employee_id') or payslip.employee_id.id
                values['contract_id'] = values.get('contract_id') or payslip.contract_id and payslip.contract_id.id
                if not values['contract_id']:
                    raise UserError(_('You must set a contract to create a payslip line.'))
        return super(HrPayslipLine, self).create(vals_list)


class HrPayslipWorkedDays(models.Model):
    _name = 'hr.payslip.worked_days'
    _description = 'Payslip Worked Days'
    _order = 'payslip_id, sequence'

    name = fields.Char(string='Description', required=True)
    payslip_id = fields.Many2one('hr.payslip', string='Pay Slip', required=True, ondelete='cascade', index=True)
    sequence = fields.Integer(required=True, index=True, default=10)
    code = fields.Char(required=True, help="The code that can be used in the salary rules")
    number_of_days = fields.Float(string='Number of Days')
    number_of_hours = fields.Float(string='Number of Hours')
    contract_id = fields.Many2one('hr.contract', string='Contract', required=True,
        help="The contract for which applied this input")


class HrPayslipInput(models.Model):
    _name = 'hr.payslip.input'
    _description = 'Payslip Input'
    _order = 'payslip_id, sequence'

    name = fields.Char(string='Description', required=True)
    payslip_id = fields.Many2one('hr.payslip', string='Pay Slip', required=True, ondelete='cascade', index=True)
    sequence = fields.Integer(required=True, index=True, default=10)
    code = fields.Char(required=True, help="The code that can be used in the salary rules")
    amount = fields.Float(help="It is used in computation. For e.g. A rule for sales having "
                               "1% commission of basic salary for per product can defined in expression "
                               "like result = inputs.SALEURO.amount * contract.wage*0.01.")
    contract_id = fields.Many2one('hr.contract', string='Contract', required=True,
        help="The contract for which applied this input")


class HrPayslipRun(models.Model):
    _name = 'hr.payslip.run'
    _description = 'Payslip Batches'

    name = fields.Char(required=True, readonly=True, states={'draft': [('readonly', False)]})
    slip_ids = fields.One2many('hr.payslip', 'payslip_run_id', string='Payslips', readonly=True,
                               states={'draft': [('readonly', False)]})
    state = fields.Selection([
        ('draft', 'Draft'),
        ('level1', 'HR Manager pending'),
        ('level2', 'General Manager pending'),
        ('done', 'Done'),
        ('cancel', 'Rejected'),
    ], string='Status', index=True, readonly=True, copy=False, default='draft')
    date_start = fields.Date(string='Date From', required=True, readonly=True,
                             states={'draft': [('readonly', False)]}, default=lambda self: fields.Date.to_string(date.today().replace(day=1)))
    date_end = fields.Date(string='Date To', required=True, readonly=True,
                           states={'draft': [('readonly', False)]},
                           default=lambda self: fields.Date.to_string((datetime.now() + relativedelta(months=+1, day=1, days=-1)).date()))
    credit_note = fields.Boolean(string='Credit Note', readonly=True,
                                 states={'draft': [('readonly', False)]},
                                 help="If its checked, indicates that all payslips generated from here are refund payslips.")

    def draft_payslip_run(self):
        for line in self.slip_ids:
            line.action_payslip_done()
        return self.write({'state': 'draft'})

#    def close_payslip_run(self):
#        return self.write({'state': 'close'})

    def done_payslip_run(self):
        for line in self.slip_ids:
            line.action_payslip_done()
        return self.write({'state': 'level1'})  # Start with level1

    def action_payslip_run_level1_done(self):
        for line in self.slip_ids:
            line.action_payslip_level1_done()
        
        result = self.write({'state': 'level2'})
        
        # Auto-generate analytics for the entire batch when it reaches Level 2
        if self.env['ir.config_parameter'].sudo().get_param('payroll_analytics_approval.auto_generate', 'True') == 'True':
            self._auto_generate_batch_analytics_on_level2()

        notify_action = self._notify_general_manager_for_batch_approval()
        return notify_action or result

    def _notify_general_manager_for_batch_approval(self):
        """Send approval email to General Manager and return a notification action."""
        self.ensure_one()
        try:
            analytics_model = self.env['payroll.analytics']
        except KeyError:
            raise UserError(_('Payroll analytics module is not available to build approval link.'))

        structure = self.slip_ids[:1].struct_id
        country = 'VN'
        if structure and hasattr(structure, 'country_id') and structure.country_id and structure.country_id.code:
            country = structure.country_id.code

        analytics = analytics_model.search([
            ('country', '=', country),
            ('date_from', '=', self.date_start),
            ('date_to', '=', self.date_end)
        ], limit=1)
        
        # Get salary structure name
        # Priority 1: From Import Batch (Most accurate for imported batches)
        salary_structure_name = ''
        if 'hr.payroll.import.batch' in self.env:
            import_batch = self.env['hr.payroll.import.batch'].search([
                ('payslip_run_id', '=', self.id)
            ], limit=1)
            if import_batch and import_batch.formula_config_id:
                salary_structure_name = import_batch.formula_config_id.name

        # Priority 2: From Formula Config matching key structure (Fallback)
        if not salary_structure_name and 'hr.formula.config' in self.env and structure:
            formula_config = self.env['hr.formula.config'].search([
                ('structure_id', '=', structure.id)
            ], limit=1)
            if formula_config and formula_config.name:
                salary_structure_name = formula_config.name

        # Priority 3: From Structure Name directly
        if not salary_structure_name and structure:
            salary_structure_name = structure.name
        
        if not analytics:
            analytics = analytics_model.generate_analytics(country, self.date_start, self.date_end)
            analytics.write({
                'state': 'ready', 
                'payslip_run_id': self.id,
                'salary_structure_name': salary_structure_name
            })
        else:
            analytics.write({
                'payslip_run_id': self.id,
                'salary_structure_name': salary_structure_name
            })

        analytics_data = analytics._generate_analytics_data(self.slip_ids, country, self.date_start, self.date_end)
        analytics.write(analytics_data)
        analytics.invalidate_cache()
        analytics._compute_analytics()

        view = self.env.ref('payroll_analytics_approval.view_payroll_analytics_dashboard', raise_if_not_found=False)
        action = self.env.ref('payroll_analytics_approval.action_payroll_approval_queue', raise_if_not_found=False)
        if not view:
            raise UserError(_('Payroll analytics dashboard view is missing.'))

        base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
        approval_url = (
            f"{base_url}/web#id={analytics.id}"
            f"&model=payroll.analytics"
            f"&view_type=form"
            f"&view_id={view.id}"
        )
        if action:
            approval_url += f"&action={action.id}"

        group = self.env.ref('pb_hr_payroll_base.group_payroll_final_approver', raise_if_not_found=False)
        gm_users = group.users if group else self.env['res.users']
        emails = [u.partner_id.email for u in gm_users if u.partner_id.email]
        if not emails:
            raise UserError(_('No General Manager email found. Please set an email on the Final Approver users.'))

        total_employees = analytics.total_employees or len(self.slip_ids.mapped('employee_id'))
        total_payroll = analytics.total_payroll or 0.0
        currency = self.env.company.currency_id
        total_payroll_display = f"{total_payroll:,.2f} {currency.name}" if currency else f"{total_payroll:,.2f}"

        subject = f"Yêu cầu phê duyệt bảng lương: {self.name}"
        body_html = (
            "<p>Kính gửi Anh/Chị Tổng Giám đốc,</p>"
            "<p>Bộ phận HR kính đề nghị Anh/Chị phê duyệt đợt bảng lương sau:</p>"
            "<ul>"
            f"<li>Đợt bảng lương: <strong>{self.name or ''}</strong></li>"
            f"<li>Kỳ lương: <strong>{self.date_start} - {self.date_end}</strong></li>"
            f"<li>Số phiếu lương: <strong>{len(self.slip_ids)}</strong></li>"
            f"<li>Tổng nhân viên: <strong>{total_employees}</strong></li>"
            f"<li>Tổng quỹ lương: <strong>{total_payroll_display}</strong></li>"
            "</ul>"
            "<p>Vui lòng truy cập dashboard để xem chi tiết và phê duyệt:</p>"
            f"<p><a href=\"{approval_url}\">{approval_url}</a></p>"
            f"<p>Trân trọng,<br/>{self.env.user.name}</p>"
        )

        mail = self.env['mail.mail'].sudo().create({
            'subject': subject,
            'body_html': body_html,
            'email_to': ','.join(emails),
            'email_from': self.env.user.email_formatted or self.env.company.email or '',
        })
        mail.send()

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Email sent'),
                'message': _('Đã gửi email cho Tổng Giám đốc để phê duyệt. Link phê duyệt: %s') % approval_url,
                'type': 'success',
                'sticky': False,
            }
        }
    
    def _auto_generate_batch_analytics_on_level2(self):
        """Auto-generate analytics when payslip batch reaches Level 2 state"""
        try:
            # Only generate analytics if we have the analytics module installed
            if 'payroll.analytics' not in self.env:
                return
            
            # Get the country from payslips or fallback
            country = 'VN'  # Default to Vietnam, can be enhanced to detect from payslip structures
            
            # Use batch date range
            first_day = self.date_start
            last_day = self.date_end
            
            # Generate analytics for this period and country
            analytics_model = self.env['payroll.analytics']
            existing_analytics = analytics_model.search([
                ('country', '=', country),
                ('date_from', '=', first_day),
                ('date_to', '=', last_day)
            ], limit=1)
            
            # Get salary structure name
            salary_structure_name = ''
            
            # Priority 1: From Import Batch (Most accurate for imported batches)
            if 'hr.payroll.import.batch' in self.env:
                import_batch = self.env['hr.payroll.import.batch'].search([
                    ('payslip_run_id', '=', self.id)
                ], limit=1)
                if import_batch and import_batch.formula_config_id:
                    salary_structure_name = import_batch.formula_config_id.name
            
            # Priority 2: From Formula Config matching key structure (Fallback)
            if not salary_structure_name and self.slip_ids:
                structure = self.slip_ids[0].struct_id
                if 'hr.formula.config' in self.env and structure:
                    formula_config = self.env['hr.formula.config'].search([
                        ('structure_id', '=', structure.id)
                    ], limit=1)
                    if formula_config and formula_config.name:
                        salary_structure_name = formula_config.name

            # Priority 3: From Structure Name directly
            if not salary_structure_name and self.slip_ids:
                structure = self.slip_ids[0].struct_id
                if structure:
                    salary_structure_name = structure.name
            
            if not existing_analytics:
                analytics = analytics_model.generate_analytics(country, first_day, last_day)
                analytics.write({
                    'state': 'ready', 
                    'payslip_run_id': self.id,
                    'salary_structure_name': salary_structure_name
                })
            else:
                existing_analytics.write({
                    'payslip_run_id': self.id,
                    'salary_structure_name': salary_structure_name
                })
                
        except Exception as e:
            # Don't fail batch approval if analytics generation fails
            import logging
            _logger = logging.getLogger(__name__)
            _logger.warning(f"Failed to auto-generate batch analytics on Level 2: {e}")

    def action_payslip_run_level2_done(self):
        for line in self.slip_ids:
            line.action_payslip_level2_done()
        return self.write({'state': 'done'})

    def action_payslip_run_cancel(self):
        for line in self.slip_ids:
            line.action_payslip_cancel()
        return self.write({'state': 'cancel'})


    def unlink(self):
        for rec in self:
            if rec.state == 'done':
                raise ValidationError(_('You Cannot Delete Done Payslips Batches'))
        return super(HrPayslipRun, self).unlink()
#Biztinct
    def action_download_payslip_xlsx(self):
        """Generate and download a raw dump of payslip components and values."""
        self.ensure_one()
        import io
        import base64
        try:
            import xlsxwriter
        except ImportError:
            raise UserError(_("The 'xlsxwriter' module is not installed. Please install it."))

        if not self.slip_ids:
            raise UserError(_("No payslips found in this batch."))

        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})

        header_fmt = workbook.add_format({'bold': True, 'align': 'center', 'valign': 'vcenter', 'border': 1, 'bg_color': '#D9D9D9'})
        text_fmt = workbook.add_format({'border': 1})
        num_fmt = workbook.add_format({'border': 1, 'num_format': '#,##0.00'})

        worksheet = workbook.add_worksheet('Payslips')
        worksheet.set_column(0, 0, 18)
        worksheet.set_column(1, 1, 28)
        worksheet.set_column(2, 2, 20)
        worksheet.set_column(3, 3, 26)
        worksheet.set_column(4, 4, 40)

        def _line_key(line):
            if line.code:
                return ('code', line.code.upper().strip())
            return ('name', (line.name or '').strip().upper())

        def _normalize_msnv(value):
            if value is None:
                return ''
            if isinstance(value, bool):
                return str(value)
            if isinstance(value, (int, float)):
                if abs(value - int(value)) < 1e-6:
                    return str(int(value))
                return ('%f' % value).rstrip('0').rstrip('.')
            text = str(value).replace(',', '').strip()
            if not text:
                return ''
            try:
                num = float(text)
            except ValueError:
                return text
            if abs(num - int(num)) < 1e-6:
                return str(int(num))
            return ('%f' % num).rstrip('0').rstrip('.')

        base_component_keys = {
            ('code', 'MSNV'),
            ('code', 'FULLNAME'),
            ('code', 'UNIT'),
            ('code', 'TYPEOFLABORCONTRACT'),
            ('code', 'SUBJECTSARECOUNTEDASWORKINGOVERTIME'),
            ('name', 'MSNV'),
            ('name', 'FULL NAME'),
            ('name', 'UNIT'),
            ('name', 'TYPE OF LABOR CONTRACT'),
            ('name', 'SUBJECTS ARE COUNTED AS WORKING OVERTIME'),
        }

        line_domain = [('slip_id', 'in', self.slip_ids.ids)]
        if 'report_visible' in self.env['hr.payslip.line']._fields:
            line_domain.append(('report_visible', '=', True))
        all_lines = self.env['hr.payslip.line'].search(line_domain, order='sequence,id')
        component_columns = []
        seen_keys = set()
        for line in all_lines:
            key = _line_key(line)
            if not key[1] or key in seen_keys:
                continue
            if key in base_component_keys or key[1] == 'MSNV':
                continue
            seen_keys.add(key)
            header = line.name or line.code or key[1]
            component_columns.append((key, header))

        headers = [
            'MSNV',
            'Full name',
            'Unit',
            'Type of labor contract',
            'Subjects are counted as working overtime',
        ] + [header for _, header in component_columns]

        for col_idx, header in enumerate(headers):
            worksheet.write(0, col_idx, header, header_fmt)
            if col_idx >= 5:
                worksheet.set_column(col_idx, col_idx, 16)

        row_idx = 1
        sorted_slips = self.slip_ids.sorted(key=lambda s: s.employee_id.name or s.name or '')
        for slip in sorted_slips:
            employee = slip.employee_id
            contract = slip.contract_id

            input_values = {}
            if hasattr(slip, 'formula_input_values') and slip.formula_input_values:
                try:
                    input_values = json.loads(slip.formula_input_values or '{}')
                except Exception:
                    input_values = {}

            def _normalize_key(value):
                return ''.join(ch for ch in str(value).upper() if ch.isalnum())

            def _lookup_input_value(keys):
                for key in keys:
                    if key in input_values:
                        return input_values.get(key)
                normalized_map = {_normalize_key(k): k for k in input_values.keys()}
                for key in keys:
                    normalized_key = _normalize_key(key)
                    if normalized_key in normalized_map:
                        return input_values.get(normalized_map[normalized_key])
                return None

            values_by_key = {}
            for line in slip.line_ids:
                if 'report_visible' in line._fields and not line.report_visible:
                    continue
                key = _line_key(line)
                if not key[1]:
                    continue
                values_by_key[key] = values_by_key.get(key, 0.0) + (line.total or 0.0)

            string_values_by_key = {}
            if hasattr(slip, 'report_visible_string_payload') and slip.report_visible_string_payload:
                try:
                    payload_items = json.loads(slip.report_visible_string_payload or '[]')
                except Exception:
                    payload_items = []
                for item in payload_items:
                    value = item.get('value') if isinstance(item, dict) else None
                    if value in (None, ''):
                        continue
                    code = (item.get('code') or '').strip().upper() if isinstance(item, dict) else ''
                    name = (item.get('name') or '').strip().upper() if isinstance(item, dict) else ''
                    if code:
                        string_values_by_key[('code', code)] = value
                    if name:
                        string_values_by_key[('name', name)] = value

            msnv = _lookup_input_value(['MSNV'])
            if not msnv:
                msnv = employee.employee_id or employee.barcode or employee.identification_id
            if not msnv:
                msnv = values_by_key.get(('code', 'MSNV')) or values_by_key.get(('name', 'MSNV'))
            msnv = _normalize_msnv(msnv)
            full_name = _lookup_input_value(['FULLNAME', 'FULL NAME'])
            if not full_name:
                full_name = employee.full_name_vn or employee.name or ''
            unit = _lookup_input_value(['UNIT'])
            if not unit:
                unit = getattr(employee, 'division', False) or employee.department_id.name or employee.location or ''

            labor_type = _lookup_input_value(['TYPEOFLABORCONTRACT', 'TYPE OF LABOR CONTRACT']) or ''
            if contract:
                if hasattr(contract, 'vietnam_contract_type') and contract.vietnam_contract_type:
                    labor_type = dict(contract._fields['vietnam_contract_type'].selection).get(contract.vietnam_contract_type, '')
                elif contract.type_id:
                    labor_type = contract.type_id.name or ''

            subjects_overtime = _lookup_input_value(['SUBJECTSARECOUNTEDASWORKINGOVERTIME', 'SUBJECTS ARE COUNTED AS WORKING OVERTIME']) or ''
            if contract:
                if hasattr(contract, 'subjects_are_counted_as_working_overtime'):
                    subjects_overtime = contract.subjects_are_counted_as_working_overtime or ''
                if not subjects_overtime:
                    for fname in contract._fields:
                        if 'subject' in fname and 'overtime' in fname:
                            subjects_overtime = getattr(contract, fname) or ''
                            break

            row_values = [msnv, full_name, unit, labor_type, subjects_overtime]

            for key, _header in component_columns:
                numeric_value = values_by_key.get(key, 0.0)
                string_value = string_values_by_key.get(key)
                if (numeric_value is None or abs(numeric_value) < 1e-9) and string_value not in (None, ''):
                    row_values.append(string_value)
                else:
                    row_values.append(numeric_value)

            for col_idx, value in enumerate(row_values):
                if col_idx == 0:
                    worksheet.write_string(row_idx, col_idx, value or '', text_fmt)
                elif col_idx < 5:
                    worksheet.write_string(row_idx, col_idx, str(value) if value else '', text_fmt)
                else:
                    if isinstance(value, str):
                        worksheet.write_string(row_idx, col_idx, value, text_fmt)
                    else:
                        worksheet.write_number(row_idx, col_idx, value or 0.0, num_fmt)

            row_idx += 1

        workbook.close()
        output.seek(0)

        filename = 'Payslip_Batch_%s.xlsx' % (self.name or 'Report')
        attachment = self.env['ir.attachment'].create({
            'name': filename,
            'datas': base64.b64encode(output.getvalue()),
            'type': 'binary',
            'mimetype': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        })

        return {
            'type': 'ir.actions.act_url',
            'url': '/web/content/%s?download=true' % attachment.id,
            'target': 'self',
        }

    def export_payslip_lines_xlsx(self):
        self.ensure_one()
        return self.env.ref('om_hr_payroll.action_report_payslip_lines_xlsx').report_action(self)

    def action_send_email_all(self):
        for record in self:
            for payslip in record.slip_ids:
                payslip.action_send_email_backend()




class PayslipLinesXlsx(models.Model):
    _name = 'report.om_hr_payroll.payslip_lines_xlsx'
    _inherit = 'report.report_xlsx.abstract'
    _description = 'Payslip Lines XLSX Report'
 
    
    
    def generate_xlsx_report(self, workbook, data, payslip_run):       
        """
        for obj in payslip_run:
            report_name = obj.name
            # One sheet by partner
            sheet = workbook.add_worksheet(report_name[:31])
            bold = workbook.add_format({'bold': True})
            sheet.write(0, 0, obj.name, bold)
        """

        if not payslip_run.slip_ids:
            raise UserError(_("No payslips found in this batch."))

        # Create formats
        bold = workbook.add_format({'bold': True, 'border': 1, 'align': 'center', 'valign': 'vcenter'})
        normal = workbook.add_format({'border': 1, 'align': 'left', 'valign': 'vcenter'})
        header_style = workbook.add_format({'bold': True, 'align': 'center', 'bg_color': '#D9E1F2'})

        sheet = workbook.add_worksheet('Payslip Lines')

        # Set column widths (adjust as needed)
        sheet.set_column('A:A', 20)  # For Employee column
        sheet.set_column('B:Z', 15)  # Adjust 'Z' to accommodate the number of line_ids

        # Write headers (dynamically from line_ids.name)
        headers = ['Employee'] + [line.name for line in payslip_run.slip_ids[0].line_ids]  # Assuming all payslips have the same lines
        for col_num, header in enumerate(headers):
            sheet.write(0, col_num, header, header_style)

        row_num = 1
        for payslip in payslip_run.slip_ids:
            col_num = 1  # Start from the second column (after Employee)
            sheet.write(row_num, 0, payslip.employee_id.name, normal)  # Employee name
            for line in payslip.line_ids:
                sheet.write(row_num, col_num, line.amount, normal)
                col_num += 1
            row_num += 1


#Biztinct - Added BOKEH dashboard using bokeh charts



class SalesDashboard(models.TransientModel):
    _name = 'sales.dashboard'
    _description = 'Sales Dashboard'

    from_date = fields.Date(string="From Date")
    to_date = fields.Date(string="To Date")
    bokeh_chart = fields.Text(string='Bokeh Chart', compute='_compute_bokeh_chart')
    bokeh_chart_worked_days = fields.Text(string="Worked Days Chart", compute='_compute_bokeh_chart_worked_days')
    employee_id = fields.Many2one('hr.employee', string="Employee")

    def _compute_bokeh_chart(self):
        for rec in self:
            sales_data = rec._get_sales_data()
            
            # Prepare data for the chart
            labels = list(sales_data.keys())
            values = list(sales_data.values())

            # Create a ColumnDataSource
            source = ColumnDataSource(data=dict(labels=labels, values=values))

            # Create a Bokeh figure
            p = figure(x_range=labels, height=350, title="Sales Data", toolbar_location=None, tools="")
            p.vbar(x='labels', top='values', width=0.9, source=source)

            # Add labels on top of the bars
            labels = LabelSet(x='labels', y='values', text='values', level='glyph',
                             x_offset=0, y_offset=5, source=source, text_align='center')
            p.add_layout(labels)

            # Styling
            p.xgrid.grid_line_color = None
            p.y_range.start = 0

            # Embed the plot components
            script, div = components(p, wrap_script=False)
            rec.bokeh_chart = json.dumps({"div": div, "script": script})

    def _get_sales_data(self):
        # Fetch and aggregate sales data (replace with your actual logic)
        # Example:
        self.env.cr.execute("""
            SELECT DATE(date_order) AS sales_date, SUM(amount_total) AS total_amount
            FROM sale_order
            WHERE date_order >= %s AND date_order <= %s
            GROUP BY sales_date
        """, (self.from_date or '1900-01-01', self.to_date or '2100-01-01'))  # Default dates if no filter
        data = self.env.cr.dictfetchall()
        return {row['sales_date'].strftime('%Y-%m-%d'): row['total_amount'] for row in data}


    def generate_dashboard(self):
        # This method is still needed if you want to keep the date filters
        self.ensure_one()
        self._compute_bokeh_chart()  # Recompute the chart with the new dates
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'sales.dashboard',
            'view_mode': 'form',
            'res_id': self.id,
            'target': 'current',
        }
    
    def _compute_bokeh_chart_worked_days(self):
        for rec in self:
            worked_days_data = rec._get_worked_days_data()

            # Prepare data for the chart
            labels = list(worked_days_data.keys())
            values = list(worked_days_data.values())

            if not labels or not values:  # Handle the case where there's no data
                rec.bokeh_chart_worked_days = False
                return

            # Create a ColumnDataSource
            source = ColumnDataSource(data=dict(labels=labels, values=values, colors=Category20c[len(labels)]))

            # Create a Bokeh figure (pie chart)
            p = figure(height=350, title="Worked Days Distribution", toolbar_location=None,
                       tools="hover", tooltips="@labels: @values hours")

            p.wedge(x=0, y=1, radius=0.4,
                    start_angle=cumsum('values', include_zero=True), end_angle=cumsum('values'),
                    line_color="white", fill_color='colors', legend_field='labels', source=source)

            p.axis.axis_label = None
            p.axis.visible = False
            p.grid.grid_line_color = None

            # Embed the plot components
            script, div = components(p, wrap_script=False)
            rec.bokeh_chart_worked_days = json.dumps({"div": div, "script": script})

    def _get_worked_days_data(self):
        """
        Fetch and aggregate worked days data for the selected employee.
        """
        self.ensure_one()

        domain = []
        if self.employee_id:
            domain.append(('employee_id', '=', self.employee_id.id))

        worked_days = self.env['hr.payslip.worked_days'].search(domain)

        data = {}
        for worked_day in worked_days:
            name = worked_day.name
            if name not in data:
                data[name] = 0
            data[name] += worked_day.number_of_hours
        return data
