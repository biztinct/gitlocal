# Part of Payobook. See LICENSE file for full copyright and licensing details.
"""WORKFLOW-2 P5c (owner decision D31): employee documents declare their
expiry timetable.

The daily "document expiry check" job (`employee_document._cron_expiry_check`)
already gives HR one to-do per document that is about to expire. Documents had
no Workflow Studio contract at all, so this is a minimal, read-only one: no
stages are declared (Studio discovers them, as for any record type without a
contract), no actions, nothing a workflow may set — only what already happens,
so Studio lists it under "Already happens" and warns a designer before a
workflow started around "Expires" repeats it. Nothing here changes the job.

The number is read from the area's own setting (`pb_employee_vault.
expiry_warn_days`, `_expiry_warn_days()`). Method-only, restart-loaded
(ledger G29); no local named `user`/`uid` in a method that calls `_()` (G12).
"""

from odoo import api, models, _


class EmployeeDocumentWorkflowTimetable(models.Model):
    _inherit = 'pb.employee.document'

    @api.model
    def _workflow_capabilities(self):
        return {'label': _('Employee document'), 'area': _('Employee documents')}

    @api.model
    def _workflow_effects(self, company):
        days = self._expiry_warn_days()
        return [{
            'stage': None, 'kind': 'reminder', 'audience': 'hr', 'owner': _('Employee documents'),
            'text': _('%s days before a document expires, HR gets a to-do on the employee to renew it.', days),
            'timing': {'field': 'expiry_date', 'before_days': days, 'active': True},
        }]
