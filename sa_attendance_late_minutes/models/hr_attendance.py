from    odoo import _, api, fields, models
from    odoo.tools  import date_utils


class SaAttendance(models.Model):
    _inherit = "hr.attendance"

    currency_id         = fields.Many2one('res.currency', 'Currency', store=True, related='employee_id.company_id.currency_id', tracking=True)
    waved               = fields.Boolean(default=False, tracking=True)
    late_minutes        = fields.Integer(readonly=False, pre_compute=True,  store=True, compute="_compute_late_minutes", tracking=True)
    deduction_amount    = fields.Monetary(store=True, pre_compute=True, compute="_compute_deduction", readonly=False, tracking=True)
    display_late_minutes= fields.Float(readonly=False, string="Late", pre_compute=True,  store=True, compute="_compute_late_minutes")


    @api.depends("employee_id", "check_in")
    def _compute_late_minutes(self):
        for r in self:
            r.late_minutes              = 0
            r.display_late_minutes      = 0
            
            if not r.employee_id.resource_calendar_id or not r.check_in or not r.employee_id:
                r.late_minutes          = 0
                r.display_late_minutes  = 0
                continue
            
            if not r.employee_id.tz:
                r.late_minutes          = 0
                r.display_late_minutes  = 0
                continue
            
            working_hours   = r.employee_id.resource_calendar_id
            check_in        = date_utils._softatt_localize(r.check_in, r.employee_id.tz)
            current_day     = check_in.weekday()
            result          = working_hours._softatt_get_shift_start_and_end_bot(current_day, check_in)
            if not result:
                r.late_minutes          = 0
                r.display_late_minutes  = 0
                return
            
            shift_start_datetime    = result[0]
            time_difference         = check_in - shift_start_datetime 
            difference_in_minutes   = time_difference.total_seconds() / 60
            r.late_minutes          = difference_in_minutes
            r.display_late_minutes  = (difference_in_minutes / 60) if difference_in_minutes > 0  else 0.0


    @api.model_create_multi
    def create(self, vals_list):
        result = super(SaAttendance, self).create(vals_list)
        result._compute_late_minutes()
        result._compute_deduction()
        return result


    @api.depends("employee_id", "late_minutes")
    def _compute_deduction(self):
        for r in self:
            if not r.employee_id.attendance_rule_id or r.late_minutes == 0:
                r.deduction_amount=0.0
                return
            r.deduction_amount =  r.employee_id.attendance_rule_id._compute_deduction(r.employee_id, r.check_in, r.late_minutes)
            
    def get_compute_deduction(self):
        for r in self:
            r._compute_deduction()
            
    def action_wave_deduction(self):
        for r in self:
            r.waved = True
            
    def action_unwave_deduction(self):
        for r in self:
            r.waved = False