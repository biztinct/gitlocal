# Part of Payobook. See LICENSE file for full copyright and licensing details.
"""Add the generic field-change audit mixin to hr.version.

In Odoo 19 an employee's position attributes — ``department_id`` and
``job_title`` — are NON-STORED related fields on hr.employee
(``related='version_id.department_id'`` / ``version_id.job_title``): a write to
``employee.department_id`` routes THROUGH to the current ``hr.version`` record
(verified live: the version is updated in place, its id unchanged). So the
old→new evidence lives on hr.version, not hr.employee — this is where those two
fields are watched (DATA: audit_rule_hr_version). The employee-level rule keeps
the fields that ARE stored on hr.employee (parent_id, company_id, active).

The timeline maps hr.version entries back onto the employee via
hr.version.employee_id (pb.employee.timeline._audit_items).
"""

from odoo import models


class HrVersion(models.Model):
    _name = 'hr.version'
    _inherit = ['hr.version', 'biz.audit.mixin']
