# -*- coding: utf-8 -*-

from odoo import fields, models


class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    division = fields.Char(string='Division')
    position_name = fields.Char(string='Position')
    job_title_text = fields.Char(string='Job Title')
    date_of_joining = fields.Date(string='Date of Joining')
