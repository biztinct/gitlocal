# -*- coding: utf-8 -*-
"""The one column this module puts on an employment.

`pb_person_id` is the whole of the person link. Everything else a segment
needs it reads through it. `ondelete='set null'` on purpose: archiving or
deleting a person must never take an employment with it — the employment is
the record payroll runs on.
"""

from odoo import fields, models


class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    pb_person_id = fields.Many2one(
        'pb.person', string='Person', index=True, ondelete='set null',
        help="The human being behind this employment. One person can hold "
             "employments in several companies and is counted once.")

    def pb_person(self):
        """The person behind this employment, made on demand if missing."""
        self.ensure_one()
        return self.env['pb.person'].for_employee(self)
