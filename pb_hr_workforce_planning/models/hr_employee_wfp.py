# -*- coding: utf-8 -*-

from odoo import api, fields, models, _


class HrEmployeeWfp(models.Model):
    """Extend hr.employee with WFP performance rating field."""
    _inherit = 'hr.employee'

    wfp_performance_rating = fields.Selection([
        ('1', '1 — Needs Improvement'),
        ('2', '2 — Partially Meets'),
        ('3', '3 — Meets Expectations'),
        ('4', '4 — Exceeds Expectations'),
        ('5', '5 — Outstanding'),
    ], string='Performance Rating',
        help="Latest annual performance rating (1-5 scale).",
        tracking=True,
        groups="hr.group_hr_user",
    )

    wfp_flight_risk = fields.Selection([
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
    ], string='Flight Risk',
        help="Estimated attrition risk level.",
        tracking=True,
        groups="hr.group_hr_user",
    )

    wfp_potential = fields.Selection([
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
    ], string='Growth Potential',
        help="Leadership/growth potential assessment.",
        tracking=True,
        groups="hr.group_hr_user",
    )
