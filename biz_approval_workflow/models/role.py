# Part of Payobook. See LICENSE file for full copyright and licensing details.
"""The responsibility catalogue — "HR lead", "Finance approver", a seat name.

A role is an organisational responsibility, NOT a permission group. Filling one
grants nobody any access (design §7.1); eligibility is the resolved seat AND an
active account AND the object's own access, checked at every decision.
"""

from odoo import fields, models


class BizApprovalRole(models.Model):
    _name = 'biz.approval.role'
    _description = 'Approval Responsibility'
    _order = 'sequence, name'

    key = fields.Char(required=True, index=True, copy=False)
    name = fields.Char(required=True, translate=True)
    description = fields.Text(translate=True)
    fallback_to_company = fields.Boolean(
        string='Company holder may cover',
        help='When an area has nobody, use the company-wide holder. Off means '
             'each area needs its own person — there is never a silent '
             'fallback to "anyone in HR".')
    is_pool = fields.Boolean(
        string='A group of people',
        help='Several people hold this responsibility together; any one of '
             'them may decide, or all of them for a joint step.')
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)

    _key_uniq = models.Constraint(
        'unique(key)',
        'Another responsibility already uses that identifier.')
