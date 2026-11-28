# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models, fields


class User(models.Model):
    _name = 'res.users'
    _inherit = ['res.users']

    vehicle = fields.Char(related="employee_id.vehicle")

    @property
    def SELF_READABLE_FIELDS(self):
        return super().SELF_READABLE_FIELDS + ['vehicle']
