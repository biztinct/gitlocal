# Part of Payobook. See LICENSE file for full copyright and licensing details.
"""Add the generic field-change audit mixin to hr.contract.

Watched fields (DATA): wage, state, date_start, date_end, struct_id,
structure_type_id. The wage entries are the salary-adjustment audit foundation
(handover §3, feature #20). A rule listing a field that does not exist on this
install is harmless — a non-field can never appear in a write's vals, so the
mixin simply never sees it.
"""

from odoo import models


class HrContract(models.Model):
    _name = 'hr.contract'
    _inherit = ['hr.contract', 'biz.audit.mixin']
