# -*- coding: utf-8 -*-
"""The Vietnam payroll facts that belong to the PERSON, not to the month.

Every field here answers a question the pay scheme used to ask a spreadsheet
once a month: are they a local employee, are they in the insurance scheme, do
they pay union dues, are they tax resident. None of those changes between two
pay runs of the same person, and a value that does not change should not be
re-typed — that is the whole argument for this module.

THEY ARE BOOLEANS AND THE SCHEME'S COLUMNS SAY "(1 = yes)". That is not a
mismatch. `excel_semantics.coerce_number` maps True to 1.0 and False to 0.0 the
way Excel does, so `IF(ISUNION=1, …)` keeps reading exactly what it read before,
while the person maintaining the record gets a tick box instead of a digit.
"""

from odoo import fields, models

from .vn_profile import EMPLOYEE_FIELDS


_HELP = {name: help_text for name, _t, _l, help_text in EMPLOYEE_FIELDS}


class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    pb_vn_is_local = fields.Boolean(
        string='Local employee', default=True, tracking=True, help=_HELP['pb_vn_is_local'])
    pb_vn_in_insurance = fields.Boolean(
        string='In the statutory insurance scheme', default=True, tracking=True, help=_HELP['pb_vn_in_insurance'])
    pb_vn_union_member = fields.Boolean(
        string='Union member', tracking=True, help=_HELP['pb_vn_union_member'])
    pb_vn_tax_resident = fields.Boolean(
        string='Tax resident', default=True, tracking=True, help=_HELP['pb_vn_tax_resident'])
    pb_vn_tax_commitment = fields.Boolean(
        string='Signed the single-employer tax commitment', tracking=True, help=_HELP['pb_vn_tax_commitment'])
    pb_vn_enrol_family_health = fields.Boolean(
        string='Enrolled in family health cover', tracking=True, help=_HELP['pb_vn_enrol_family_health'])
    pb_vn_enrol_private_health = fields.Boolean(
        string='Enrolled in private health cover', tracking=True, help=_HELP['pb_vn_enrol_private_health'])
    pb_vn_enrol_dep_health = fields.Boolean(
        string='Dependants on private health cover', tracking=True, help=_HELP['pb_vn_enrol_dep_health'])
