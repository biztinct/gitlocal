# -*- coding: utf-8 -*-

from odoo import fields, models


class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    division = fields.Char(string='Division')
    position_name = fields.Char(string='Position')
    job_title_text = fields.Char(string='Job Title')
    date_of_joining = fields.Date(string='Date of Joining')
    overtime_status = fields.Char(string='Overtime Status', default='')
    fire_prevention_officer = fields.Char(string='Fire Prevention Officer', default='')
    tham_gia_bhxh = fields.Char(string='Tham gia BHXH', default='')
