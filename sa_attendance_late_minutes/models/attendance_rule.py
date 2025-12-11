from odoo import api, fields, models
import calendar

class MsgAttendanceRuleLine(models.Model):
    _name = "sa.attendance.rule.line"
    _description = "Rule Line"

    sequence    = fields.Integer(string='',)
    minutes     = fields.Integer(string='Minutes')
    amount      = fields.Monetary(string='Deduct')
    currency_id = fields.Many2one('res.currency', 'Currency', required=True, default=lambda self: self.env.company.currency_id.id, tracking=True)
    rule_id     = fields.Many2one('sa.attendance.rule',)

class MsgAttendanceRule(models.Model):
    _name = "sa.attendance.rule"
    _description = "Rule"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "id desc"
    
    
    active                  = fields.Boolean(default=True)
    name                    = fields.Char(string='Rule Name', required=True)
    company_id              = fields.Many2one(comodel_name='res.company', required=True, index=True, default=lambda self: self.env.company)
    currency_id             = fields.Many2one('res.currency', 'Currency', related='company_id.currency_id', required=True, tracking=True)
    allowed_minutes         = fields.Integer("Allowed Minutes")
    daily_wage_base         = fields.Selection([('30', 'Average (30 Days)'), ('month_based', 'Month Based')],
                                       help="Select the basis for calculating the daily wage:\n"
                                       "- 'Average (30 Days)': Calculates daily wage based on a 30-day average.\n"
                                       "- 'Month Based': Calculates daily wage by dividing the monthly salary by the actual number of days in the month.")
    time_minutes            = fields.Integer(string='Time(Minutes)')
    line_ids                = fields.One2many('sa.attendance.rule.line', 'rule_id')
    
    deduction_type          = fields.Selection([('wage', 'Based On Wage'),
                                            ('by_minute','Based On Minutes')], required=True)
    
    def _compute_daily_wage(self, employee, date):
        days = 30 if self.daily_wage_base == '30' else int(calendar.monthrange(date.year, date.month)[1])
        daily_wage = (employee.contract_id.wage / days)
        return daily_wage
    
    def _compute_deduction(self, employee, date, minutes):
        if self.deduction_type == 'wage':
            minutes = max(0, minutes - self.allowed_minutes)
            daily_wage = self._compute_daily_wage(employee, date)
            hours_per_day = employee.resource_calendar_id.hours_per_day
            amount = daily_wage / hours_per_day
            return round((minutes / 60) * amount, 3)
        

        if self.deduction_type == 'by_minute':
            to_deduct = self._get_custom_amount(minutes)
            return round(to_deduct, 3)
   

    def _get_custom_amount(self, minutes):
        latency_rule = self.line_ids.search([('rule_id.id', '=', self.id), 
                                                     ('minutes', '>', minutes)], order='minutes', limit=1)
        return latency_rule.amount if latency_rule else 0.0