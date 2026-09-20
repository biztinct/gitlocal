# Part of Payobook. See LICENSE file for full copyright and licensing details.
"""Add the generic field-change audit mixin to hr.employee.

Which fields are actually watched is DATA (biz.audit.rule, see
data/audit_rule_data.xml): department_id, job_title, parent_id, company_id,
active. The bank master fields keep their OWN dedicated history
(pb.employee.bank.history) and are deliberately NOT audited here — the timeline
reads that log separately, so auditing them too would double-log.
"""

from odoo import models


class HrEmployee(models.Model):
    _name = 'hr.employee'
    _inherit = ['hr.employee', 'biz.audit.mixin']
